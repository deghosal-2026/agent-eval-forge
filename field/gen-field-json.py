#!/usr/bin/env python3
"""Generate best-effort field.json configs for cloned field-test agents.

Scans each cloned repo under field/agents/ for a runnable entry point using
ranked heuristics, then writes field/config/<slug>.json. Configs are stubs —
curate them after generation.

Usage:
  python field/gen-field-json.py [--file field/list1.txt] [--force] [--dry-run]
  python field/gen-field-json.py --file field/list2.txt --file field/list3.txt
  python field/gen-field-json.py --agent lg-pdf-chatbot,pa-deepagents

Heuristics (ranked):
  1. langgraph.json  -> adapter langgraph, module:function from "graphs"
  2. create_react_agent / StateGraph -> adapter langgraph
  3. pydantic_ai Agent -> adapter pydantic-ai
  4. FastAPI app -> adapter http
  5. [project.scripts] in pyproject.toml -> adapter subprocess
  6. fallback: list-file adapter, no adapter_config
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIELD = ROOT / "field"
AGENTS_DIR = FIELD / "agents"
CONFIG_DIR = FIELD / "config"
LISTS = ["field/list1.txt", "field/list2.txt", "field/list3.txt"]


# ── list file parsing ────────────────────────────────────────────────────
def parse_list(file: Path) -> list[dict]:
    agents = []
    for line in file.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split("|")
        slug = parts[0]
        agents.append({
            "slug": slug,
            "repo": parts[1] if len(parts) > 1 else "",
            "commit": parts[2] if len(parts) > 2 else "TODO",
            "adapter": parts[3] if len(parts) > 3 else "",
            "setup_cmd": parts[4] if len(parts) > 4 else "",
        })
    return agents


# ── repo scanning helpers ────────────────────────────────────────────────
SKIP_DIRS = {
    ".venv", "venv", "env", "site-packages", "node_modules", ".git",
    "__pycache__", "dist", "build", ".tox", ".nox", "egg-info", "migrations",
    "alembic", "tests", "test", "testing", "examples", "docs", "doc",
    "frontend", "web", "ui", "static", "assets", "scripts", "docker", "deploy",
}


def is_skip_dir(name: str) -> bool:
    return name in SKIP_DIRS or name.startswith(".")


def repo_files(repo: Path) -> list[Path]:
    """Python files, excluding vendored/test/build dirs and hidden dirs."""
    files = []
    for p in repo.rglob("*.py"):
        rel = p.relative_to(repo)
        if any(is_skip_dir(part) for part in rel.parts[:-1]):
            continue
        if p.name.startswith("test_") or p.name.endswith("_test") or p.name == "tests.py":
            continue
        files.append(p)
    return files


def first_import(text: str, *mods: str) -> bool:
    return any(re.search(rf"^\s*(?:from|import)\s+{re.escape(m)}\b", text, re.M) for m in mods)


def pyproject_scripts(repo: Path) -> list[str]:
    cfg = repo / "pyproject.toml"
    if not cfg.exists():
        return []
    text = cfg.read_text(errors="ignore")
    m = re.search(r"\[project\.scripts\]\s*\n(.*?)(?:\n\[|\Z)", text, re.S)
    if not m:
        return []
    return [
        line.strip()
        for line in m.group(1).splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def langgraph_json_entry(repo: Path) -> tuple[str, str] | None:
    lg = repo / "langgraph.json"
    if not lg.exists():
        return None
    try:
        data = json.loads(lg.read_text())
        graphs = data.get("graphs", {})
        for name, spec in graphs.items():
            if ":" in spec:
                return spec.split(":", 1)[0], spec.split(":", 1)[1]
    except Exception:
        pass
    return None


def module_of(f: Path, repo: Path) -> str:
    """Convert a file path to a dotted module path relative to the repo root."""
    return str(f.relative_to(repo).with_suffix("")).replace("/", ".")


def _agent_builder_names(text: str) -> set[str]:
    """Names that look like agent/graph builder functions or compiled graphs."""
    names = set()
    for m in re.finditer(r"(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)\b", text):
        name = m.group(1)
        lower = name.lower()
        if lower in {
            "build_agent", "build_graph", "build_workflow", "create_agent",
            "create_react_agent", "create_workflow", "make_agent", "get_agent",
            "create_graph", "compile_graph", "agent_graph", "workflow",
            "graph", "app", "agent", "assistant",
        } or any(tok in lower for tok in ("agent", "graph", "workflow", "assistant", "app")):
            names.add(name)
    return names


def _pick_best_name(names: set[str]) -> str:
    preferred = (
        "build_agent", "build_graph", "create_agent", "create_graph",
        "create_react_agent", "create_workflow", "build_workflow",
        "make_agent", "get_agent", "compile_graph",
    )
    name_list = sorted(names)
    for exact in preferred:
        if exact in names:
            return exact
    for name in name_list:
        lower = name.lower()
        if lower.startswith(("build_", "create_", "make_", "get_")):
            return name
    for name in name_list:
        if "graph" in name.lower():
            return name
    for name in name_list:
        if "agent" in name.lower() or "assistant" in name.lower():
            return name
    return name_list[0]


def detect_langgraph(repo: Path, files: list[Path]) -> dict | None:
    entry = langgraph_json_entry(repo)
    if entry:
        module, function = entry
        return {"module": module, "function": function}

    # Prefer src/ modules over root modules; each file must import langgraph
    # and define a builder/compiled-graph name.
    candidates = []
    for f in files:
        text = f.read_text(errors="ignore")
        if not first_import(text, "langgraph"):
            continue
        names = _agent_builder_names(text)
        if not names:
            continue
        rel = f.relative_to(repo)
        depth = len(rel.parts) - 1  # root-level files rank highest
        src_bonus = 0 if rel.parts[0] in ("src", "app", "agent", "agents", "services") else 1
        candidates.append((depth + src_bonus, f, names))

    if not candidates:
        return None
    # rank: lowest depth + src_bonus wins; prefer files with create_react_agent/StateGraph
    candidates.sort(key=lambda c: (c[0], 0 if "StateGraph" in c[2] else 1))
    _, best, names = candidates[0]
    function = _pick_best_name(names)
    return {"module": module_of(best, repo), "function": function}


def detect_pydantic_ai(repo: Path, files: list[Path]) -> dict | None:
    candidates = []
    for f in files:
        text = f.read_text(errors="ignore")
        if "Agent(" not in text or not first_import(text, "pydantic_ai"):
            continue
        names = _agent_builder_names(text)
        if not names:
            continue
        rel = f.relative_to(repo)
        depth = len(rel.parts) - 1
        src_bonus = 0 if rel.parts[0] in ("src", "app", "agent", "agents", "services") else 1
        candidates.append((depth + src_bonus, f, names))

    if not candidates:
        return None
    candidates.sort(key=lambda c: c[0])
    _, best, names = candidates[0]
    function = _pick_best_name(names)
    return {"module": module_of(best, repo), "function": function}


def detect_fastapi(repo: Path, files: list[Path]) -> dict | None:
    for f in files:
        text = f.read_text(errors="ignore")
        if "FastAPI(" in text and first_import(text, "fastapi"):
            return {"url": "http://localhost:8000/agent"}
    return None


def detect_subprocess(repo: Path) -> dict | None:
    scripts = pyproject_scripts(repo)
    if scripts:
        first = scripts[0]
        func = first.split("=", 1)[0].strip() if "=" in first else first
        return {"command": func}
    return None


def detect_entry(repo: Path, list_adapter: str) -> tuple[str, dict | None, list[str]]:
    """Return (adapter_type, adapter_config|None, notes)."""
    files = repo_files(repo)
    notes: list[str] = []

    lg = detect_langgraph(repo, files)
    if lg:
        return "langgraph", lg, notes

    pa = detect_pydantic_ai(repo, files)
    if pa:
        return "pydantic-ai", pa, notes

    if detect_langgraph_json_only := langgraph_json_entry(repo):
        notes.append(f"langgraph.json graphs present ({detect_langgraph_json_only})")

    http = detect_fastapi(repo, files)
    if http:
        return "http", http, notes

    sp = detect_subprocess(repo)
    if sp:
        return "subprocess", sp, notes

    if list_adapter in ("langgraph", "pydantic-ai", "http", "subprocess", "python"):
        return list_adapter, None, notes + ["no entry point detected; using list-file adapter"]
    return "python", None, notes + ["no entry point detected; defaulting to python"]


# ── config generation ────────────────────────────────────────────────────
def pick_pack(adapter: str) -> list[str]:
    if adapter == "pydantic-ai":
        return ["scenarios/pydantic-ai-core.yaml"]
    return ["scenarios/langgraph-core.yaml"]


def _verify_entry(repo: Path, adapter_type: str, adapter_config: dict) -> list[str]:
    """Try to import the detected module+function. Returns problems (empty = ok).

    Runs the agent's own python/uv if present so per-repo deps resolve.
    """
    if adapter_type not in ("langgraph", "pydantic-ai", "python"):
        return []  # http/subprocess not importable at gen time
    module = adapter_config.get("module", "")
    function = adapter_config.get("function", "build_agent")
    if not module:
        return ["no module to import"]

    code = (
        f"import importlib; m=importlib.import_module('{module}'); "
        f"getattr(m, '{function}')"
    )
    for py in ("uv run python", "python", "python3"):
        try:
            r = subprocess.run(
                f"{py} -c \"{code}\"", shell=True, cwd=repo,
                capture_output=True, text=True, timeout=60,
            )
        except Exception as exc:
            continue
        if r.returncode == 0:
            return []
        # try the next interpreter
    return [f"import failed (tried uv/python/python3): {r.stderr.strip()[:200]}"]


def generate(slug: str, list_agent: dict) -> dict:
    repo = AGENTS_DIR / slug
    adapter_type, adapter_config, notes = detect_entry(repo, list_agent.get("adapter", ""))

    problems = []
    if adapter_config:
        problems = _verify_entry(repo, adapter_type, adapter_config)
    if problems:
        notes.extend(problems)

    return {
        "agent_id": slug,
        "name": slug.replace("-", " ").title(),
        "repo": list_agent.get("repo", ""),
        "commit": list_agent.get("commit", "TODO"),
        "adapter_type": adapter_type,
        "adapter_config": adapter_config or {},
        "setup_commands": [c for c in [list_agent.get("setup_cmd", "")] if c and c != "none"],
        "scenario_packs": pick_pack(adapter_type),
        "acceptance": {
            "minimum_pass_rate": 0.5,
            "required_metrics": [],
        },
        "tags": [adapter_type],
        "quarantined": False,
        "_notes": notes,
    }


# ── main ─────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", action="append", help="agent list file (repeatable; default: all three)")
    ap.add_argument("--agent", help="comma-separated slugs to generate (default: all cloned)")
    ap.add_argument("--force", action="store_true", help="overwrite existing configs")
    ap.add_argument("--dry-run", action="store_true", help="print what would be written")
    args = ap.parse_args()

    files = [ROOT / f for f in (args.file or LISTS)]
    agents: dict[str, dict] = {}
    for f in files:
        for a in parse_list(f):
            agents.setdefault(a["slug"], a)

    wanted = None
    if args.agent:
        wanted = set(args.agent.split(","))
        agents = {k: v for k, v in agents.items() if k in wanted}

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    generated, skipped, missing = 0, 0, 0
    unresolved: list[str] = []
    for slug, list_agent in sorted(agents.items()):
        if not (AGENTS_DIR / slug).is_dir():
            print(f"[skip]   {slug}: not cloned")
            missing += 1
            continue
        out = CONFIG_DIR / f"{slug}.json"
        if out.exists() and not args.force:
            print(f"[skip]   {slug}: config exists ({out.name}); use --force to overwrite")
            skipped += 1
            continue
        cfg = generate(slug, list_agent)
        if not cfg["adapter_config"]:
            unresolved.append(slug)
        if args.dry_run:
            print(f"[dry]    {slug}: adapter={cfg['adapter_type']} config={json.dumps(cfg['adapter_config'])}")
        else:
            out.write_text(json.dumps(cfg, indent=2) + "\n")
            print(f"[write]  {slug}: adapter={cfg['adapter_type']} -> {out.name}")
        generated += 1

    print()
    print(f"Generated: {generated} | Skipped: {skipped} | Not cloned: {missing}")
    if unresolved:
        print(f"Unresolved entry points ({len(unresolved)}) — need manual config:")
        for s in unresolved:
            print(f"  - {s}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
