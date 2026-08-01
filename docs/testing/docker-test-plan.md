# Docker Container Test Plan

## 1. Purpose

Validate that agent-eval-forge's Docker container runtime (`run_in_container` in `security/sandbox.py`) works correctly for sandboxed agent execution. Docker is the strongest isolation level — it provides network blocking, filesystem read-only, resource limits, and process namespace isolation that the env-level `--sandbox` cannot.

These tests live outside the field test suite because they test the *infrastructure* (Docker integration), not real agents.

## 2. Architecture

```
evalforge run --sandbox --container-runtime docker
        │
        ▼
  security/sandbox.py
  ┌─────────────────────────────────────────┐
  │ run_in_container(agent_cmd, payload,    │
  │                  DockerConfig, timeout)  │
  │                                         │
  │  docker run --rm                         │
  │    --network none                        │
  │    --read-only                           │
  │    --memory 512m                         │
  │    --cpus 1.0                            │
  │    --tmpfs /tmp:noexec,nosuid,size=64m   │
  │    evalforge-agent-runner                │
  │      <agent command>                     │
  └─────────────────────────────────────────┘
```

The `evalforge-agent-runner` Docker image is built from the project `Dockerfile` which includes all dependencies (langgraph, pydantic-ai, judge SDKs, scenario packs) for a self-contained image. A setup script handles the full lifecycle: remove old image → build new image → run tests.

## 3. Docker Config Schema

```python
@dataclass
class DockerConfig:
    image: str = "evalforge-agent-runner"   # Docker image tag
    network_disabled: bool = True            # --network none
    read_only_root: bool = True              # --read-only
    memory_limit: str = "512m"               # --memory
    cpu_limit: float = 1.0                   # --cpus
```

Users can override via `evalforge run --container-runtime docker --docker-memory 1g --docker-cpus 2`.

## 4. Test Cases

### 4.1 Basic Container Execution

**Purpose:** Verify a simple echo agent runs inside the container and produces expected output.

**Setup:** Build the Docker image, run `echo hello` inside it.

**Assertion:** stdout contains "hello", exit code 0.

### 4.2 Network Isolation

**Purpose:** Verify `--network none` actually blocks outbound network access.

**Setup:** Run a Python one-liner that tries to connect to `8.8.8.8:53` (Google DNS).

**Assertion:** The connection attempt raises an exception (ConnectionRefusedError or OSError), not a successful connection.

### 4.3 Read-Only Filesystem

**Purpose:** Verify `--read-only` prevents the container from writing to the host filesystem outside of tmpfs.

**Setup:** Run a Python one-liner that tries `os.makedirs('/host_test', exist_ok=True)`.

**Assertion:** The write attempt raises PermissionError or similar.

### 4.4 Resource Limits

**Purpose:** Verify `--cpus` and `--memory` flags are correctly forwarded. Validates by reading cgroup limits from inside the container.

**Setup:** Run a Python one-liner that reads CPU quota from `/sys/fs/cgroup/cpu.max` and memory limit from `/sys/fs/cgroup/memory.max`.

**Assertion:** The cgroup limits match the configured values (e.g., `--cpus 1.0` → CPU quota = 100000, `--memory 512m` → memory max approx 512MB).

### 4.5 Startup Failure

**Purpose:** Verify that running a nonexistent command produces a clear error.

**Setup:** Run `nonexistent_command_xyz` inside the container.

**Assertion:** `run_in_container` raises `AdapterError` with a message containing "container exited with code".

### 4.6 Timeout

**Purpose:** Verify that a long-running agent is killed when it exceeds the timeout.

**Setup:** Run `sleep 60` with a 5-second timeout.

**Assertion:** The `subprocess.run` raises `subprocess.TimeoutExpired`.

## 5. Test File Structure

```
tests/test_security_container_integration.py
```

Guard:
```python
pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(not shutil.which("docker"), reason="docker not available"),
    pytest.mark.skipif(sys.platform != "linux", reason="Docker isolation tests require Linux"),
]
```

A setup script (`scripts/docker-test-setup.sh`) handles the full lifecycle:
1. `docker rmi evalforge-agent-runner --force` (remove old image)
2. `docker build -t evalforge-agent-runner -f Dockerfile .` (build fresh image)
3. `uv run pytest tests/test_security_container_integration.py -m docker -v` (run tests)

## 6. CI Integration

The CI job `.github/workflows/ci.yml` (docker-sandbox job):
- Runs on `ubuntu-latest` only
- Executes: `bash scripts/docker-test-setup.sh`
- Separate job (not part of the main test matrix) because Docker setup takes ~2 minutes
- Scenario packs and test data are embedded in the Docker image for a fully self-contained test

## 7. Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Image lifecycle | Automated script: remove old → build → test | Always fresh, matches current code, no GHCR dependency |
| Resource validation | Read actual cgroup limits | Validates real enforcement, not just flag acceptance |
| Image contents | Single image with all extras | Simpler to maintain, one build per CI run |
| Platform | Linux-only | Docker on macOS uses VM; isolation behavior differs |
| Test data | Embedded in image | Self-contained, no volume mount dependency |

## 8. Success Criteria

- All 6 test cases pass in CI on Linux (docker-sandbox job)
- Tests skip on non-Linux platforms
- Total docker-sandbox CI job completes under 3 minutes
- No test leaks Docker containers or images (cleanup via `--rm`)
- Test failures produce actionable error messages