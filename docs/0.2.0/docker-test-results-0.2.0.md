# Docker Test Results — v0.2.0 (dev-0.2.0)

**Date:** 2026-08-11  
**Branch:** `dev-0.2.0`  
**Commit:** `86de788 feat: add Phase 3 adapters (smolagents, AutoGen, LlamaIndex, Claude SDK, Google ADK) + field roster cleanup`  
**Docker Image:** `evalforge-agent-runner:latest` (built from `Dockerfile`)  
**Host OS:** macOS 15 (arm64) — Docker Desktop  
**Docker Daemon:** Running  
**Command:** `pytest -m docker`

---

## Summary

| Test File | Tests | Passed | Failed | Duration |
|-----------|-------|--------|--------|----------|
| `test_docker.py` — CLI in container (help/version/validate) | 4 | 4 | 0 | ~30s |
| `test_security_container_integration.py` | 6 | 6 | 0 | ~4s |
| `test_security_docker_llm.py` | 1 | 1 | 0 | ~3s |
| **Total** | **11** | **11** | **0** | **39s** |

---

## test_docker.py — CLI in Container

| Test | Status | Notes |
|------|--------|-------|
| `test_help` | ✅ PASS | `docker run <img> --help` prints EvalForge usage |
| `test_version` | ✅ PASS | `docker run <img> version` matches installed version |
| `test_validate_pack` | ✅ PASS | `docker run <img> validate --pack scenarios/core-launch.yaml` succeeds |
| `test_validate_pack_strict` | ✅ PASS | Strict validation of the launch pack passes |

## test_security_container_integration.py — Container Isolation

| Test | Status | Notes |
|------|--------|-------|
| `test_echo_agent_in_container` | ✅ PASS | Basic echo command runs inside container |
| `test_network_isolation` | ✅ PASS | `--network none` blocks outbound connectivity |
| `test_readonly_filesystem` | ✅ PASS | `--read-only` prevents writes to root FS |
| `test_resource_limits` | ✅ PASS | CPU quota (0.5 → 50000) and memory limit (64m → 67108864) enforced |
| `test_startup_failure` | ✅ PASS | Nonexistent command exits non-zero |
| `test_timeout` | ✅ PASS | Container killed when exceeding `timeout=2.0` |

## test_security_docker_llm.py — LLM from Container

| Test | Status | Notes |
|------|--------|-------|
| `test_omlx_chat_completion_in_container` | ✅ PASS | OMLX reachable via `host.docker.internal:8000`, non-blank completion returned |

---

## Bugs Fixed During Testing

1. **Dockerfile: `CMD` overridden by CLI args broke `test_docker.py`**  
   The Dockerfile used `CMD ["evalforge", "--help"]` with no `ENTRYPOINT`. Passing any CLI arg (e.g. `--help`, `version`, `validate`) overrode `CMD` entirely, so the container tried to exec the arg as a program (`exec: "--help": executable file not found`). The `test_docker.py` suite expects `evalforge` to be the entrypoint so trailing args are consumed as subcommands.  
   **Fix:** `CMD ["evalforge", "--help"]` → `ENTRYPOINT ["evalforge"]` + `CMD ["--help"]`.  
   **File:** `Dockerfile`

2. **`test_security_docker_llm.py` referenced non-existent virtualenv path**  
   Changed `/app/.venv/bin/python` → `python`. The Dockerfile uses `uv pip install --system`, so packages are installed in the system Python, not a `.venv`.  
   **File:** `tests/test_security_docker_llm.py`

---

## Pre-Release Gates Status

| Gate | Status |
|------|--------|
| Docker CLI (help/version/validate) | ✅ 4/4 tests pass |
| Docker sandbox isolation | ✅ 6/6 tests pass |
| Docker + LLM integration | ✅ 1/1 test passes |
