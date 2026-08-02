# External Benchmark Connectors

EvalForge can import external benchmark datasets and convert them to native
scenario packs for evaluation. This allows running established benchmarks
(SWE-bench, WebArena) through the same runner, scoring, and regression pipeline
as native scenario packs.

## Architecture

```
External dataset → BenchmarkTask[] → convert_to_pack() → ScenarioPack
                                        ↓
                                  export_pack() → portable .yaml
```

The connector layer lives at `src/evalforge/benchmarks/`. It is a format
translation boundary — it never modifies the core runner or scoring engine.

## Built-in Connectors

### SWE-bench

Loads SWE-bench JSONL files and produces coding scenarios.

**Format expectation:** JSONL with fields `instance_id`, `repo`, `base_commit`,
`problem_statement` (or `issue`), `patch`, `FAIL_TO_PASS`, `PASS_TO_PASS`,
and optionally `hints_text`.

**Tools injected:** `read_file`, `write_file`, `execute_command`.

**Scoring metrics:** `output_correctness` (0.4), `tool_correctness` (0.3),
`task_completion` (0.3).

### WebArena

Loads WebArena JSON task lists and produces web-navigation scenarios.

**Format expectation:** JSON array with objects containing `task_id`, `intent`,
`sites`, `start_urls`, and `expected`.

**Tools injected:** `navigate`, `click`, `type`, `extract`.

**Scoring metrics:** `task_completion` (0.5), `tool_correctness` (0.2),
`navigation_efficiency` (0.3).

## Usage

```python
from evalforge.benchmarks import BenchmarkLoader, BenchmarkRegistry

loader = BenchmarkLoader()
tasks = loader.load_swe_bench("path/to/swe-bench.jsonl")

# Convert to an in-memory ScenarioPack
pack = loader.convert_to_pack(tasks, "swe-bench-sample")

# Or export as a portable YAML file
loader.export_pack(tasks, "scenarios/swe-bench-sample.yaml", "swe-bench-sample")
```

## Custom Connectors

Register your own format via `BenchmarkRegistry`:

```python
def my_loader(dataset_path: str) -> list[BenchmarkTask]:
    ...

registry = BenchmarkRegistry()
registry.register("my-format", my_loader)
tasks = registry.load("my-format", "path/to/dataset.json")
```

The loader function receives a file path and must return
`list[BenchmarkTask]`. Each task must have:
- `task_id` — unique identifier
- `category` — e.g. "swe-bench", "webarena", "custom"
- `prompt` — the input text for the agent
- `expected` — dict with evaluation expectations
- `tools` — list of dicts with `name` and `description`
- `reference_output` — optional expected answer string