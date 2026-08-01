# Security Review: agent-eval-forge v0.1

## Scope

- API key and credential handling in logs/artifacts
- Subprocess execution sandboxing
- Audit trail for evaluation runs
- Scenario pack trust boundaries
- CI/CD pipeline security

## Findings

### 1. API Key Sanitization

- **Mechanism**: Dual-layer: key-name filtering (`_sanitize_agent` in `adapters/base.py:219`) strips known secret keys (`api_key`, `token`, `secret`, `password`) from config dicts before they reach the run index and artifacts, then regex pattern redaction (`sanitize_config` in `security/sanitize.py:31`) deep-scans nested dicts and string values for OpenAI-style (`sk-...`), Anthropic-style (`sk-ant-...`), and GitHub token (`ghp_...`, `gho_...`) patterns, replacing them with `[REDACTED]`.
- **Verified**: Keys are stripped from run index (`runner.py:191` calling `_sanitize_agent`), from artifacts (`runner.py:146` in parallel error paths), and from audit logs (`cli/run.py:221` calling `sanitize_config` before `audit.record`).
- **Coverage**: String pattern redaction handles false positives (non-key strings matching the regex) gracefully — the `[REDACTED]` replacement is safe for any match. Depth limit (`_depth > 10` at `sanitize.py:33`) prevents infinite recursion.
- **Gaps**: None at this layer. The `SANITIZE_KEYS` set in `sanitize.py:13` is slightly broader than the set in `base.py:225` (adding `credential`, `auth_token`), but both are supersets of the actual credential keys — `sanitize_config` catches anything `_sanitize_agent` misses. The regex patterns could be extended to cover more key formats (e.g., AWS `AKIA...`, GCP service account JSON) but cover the primary CI/CD agent services.

### 2. Subprocess Sandbox

- **Mechanism**: `SandboxConfig` (dataclass) with `enabled`, `allowlist`, and `timeout_multiplier`. When enabled, `sandboxed_run` (`security/sandbox.py:31`) strips all environment variables except the allowlist: `PATH`, `HOME`, `TMPDIR`, `USER`, `EVALFORGE_SANDBOX`, `EVALFORGE_FIXTURES_DIR`. The `EVALFORGE_SANDBOX=1` marker is injected so child processes can detect sandbox mode. Timeout is doubled (`timeout * config.timeout_multiplier`) to prevent DoS-by-slow-agent.
- **Activation**: Via `--sandbox` CLI flag (`cli/run.py:161-164`), stored in `agent_config["sandbox"]` and passed through to `SubprocessAdapter._invoke` (`subprocess.py:39-41`), which constructs a `SandboxConfig(enabled=True)`.
- **Verified**: All env vars except the allowlist are stripped. `force=False` is the default — sandbox does not force-enable when a process opts out.
- **Gaps**: No OS-level resource limits — the sandbox is purely an environment-level restriction. No filesystem isolation (no tmpfs, no read-only root, no seccomp). A malicious agent process in sandbox mode still has full access to the filesystem, network, and OS resources. The timeout multiplier is a weak DoS mitigation (2x just doubles the window). For production use against untrusted packs, OS-level sandboxing (cgroups, Firejail, or Docker) should be added.

### 3. Audit Trail

- **Mechanism**: Append-only JSON log at `.evalforge/audit/audit.log` via `AuditTrail` class (`security/audit.py:16`). Events recorded: `run_start` (with sanitized agent config, pack path, sandbox flag, CI flag), `sandbox_active` (with allowlist), and `run_complete` (with exit code, pass/fail counts, safety violations).
- **Recorded at**: `cli/run.py:218-228` (start and sandbox events) and `cli/run.py:330-336` (completion event).
- **Integrity**: Append-only by design — each event is a newline-delimited JSON line. No existing mechanism prevents tampering of past entries.
- **Gaps**: No log rotation — the single `audit.log` file grows unbounded. `get_events` reads the entire file into memory (`security/audit.py:49`), which will become slow and memory-heavy over time. No log signing or integrity verification. No retention policy.

### 4. Scenario Trust Boundaries

- **Status**: Not implemented. The spec (`docs/spec.md:2407`) mentions "scenario trust boundaries" as a requirement, and the WBS (`docs/wbs.md:527`) lists them as a deferred M8 item ("Scenario trust boundaries (built-in/local/external)"). Currently, all packs are treated equally regardless of origin.
- **Risk**: A malicious scenario pack could craft scenario definitions that exploit the eval runner — e.g., scenario metadata that triggers path traversal in artifact paths, or prompt injections that cause the LLM judge to emit arbitrary scores. Since `scenario_id` is used directly in artifact filenames (`runner.py:179`: `f"{artifact.scenario_id}.json"`), a pack with a crafted `scenario_id` like `../../etc/passwd` could write outside the expected artifact directory.
- **Specific attack surface**: `runner.py:179` uses `artifact.scenario_id` unsanitized in a file path. While `run_dir` is always under the controlled `.evalforge/runs/<run_id>/` directory, a path traversal in `scenario_id` could escape. The `scenario_id` should be validated against a strict pattern (e.g., `^[a-zA-Z0-9_-]+$`) before use in file paths.

### 5. CI/CD Pipeline

- **Mechanism**: CI integration is documented in `docs/ci.md` with `--ci` flag support for structured exit codes, JSON output, and GitHub Actions annotations. A `.github/workflows/` directory does not exist yet — the docs reference a template at `.github/workflows/ci-evalforge.yml` that has not been created.
- **Secrets handling**: The CI doc explicitly notes "pass them as CI secrets via environment variables" and "EvalForge passes environment through to the agent process." In sandbox mode, all secrets are stripped from the subprocess environment (findings #1 and #2). Outside sandbox mode, secrets flow through to the agent process but are sanitized before persisting to run index, artifacts, or audit logs.
- **Dependency security**: `pyproject.toml` uses `uv` for fast dependency resolution; no Dependabot configuration was found. No SCA (Software Composition Analysis) tooling is configured.
- **Gaps**: No Software Bill of Materials (SBOM) generation. No Dependabot config for automated vulnerability alerts. The referenced GitHub Actions workflow template does not exist yet. No signing of release artifacts.

## Recommendations

1. **Validate `scenario_id` against a strict pattern** before using it in file paths at `runner.py:179`. This closes the path traversal vector from malicious packs — a high-priority fix that is cheap to implement.

2. **Implement scenario trust boundaries** (WBS M8 item at `docs/wbs.md:527`): assign trust levels (built-in, local, external) to packs and restrict tool access (file I/O, network, environment) for external packs. This is the most significant remaining security gap.

3. **Add audit log rotation** (or a size cap) before production use. A simple approach is to rotate at 10 MB and keep 5 rotated files, or switch to a database-backed audit store with built-in rotation.

4. **Consider OS-level sandbox** (cgroups, Firejail, or Docker) for untrusted pack execution. The current env-only sandbox prevents credential leakage but does not restrict filesystem or network access. This is a medium-term investment but necessary if the tool runs third-party scenario packs.

5. **Add Dependabot configuration** (`.github/dependabot.yml`) for automated vulnerability scanning of Python dependencies, and consider adding a `pip-audit` or `safety` step to the CI pipeline.

6. **Create the referenced GitHub Actions workflow** at `.github/workflows/ci-evalforge.yml` to give users a concrete starting point with security best practices baked in.

## Assessment

The security model covers the primary attack surface (credential leakage in artifacts/logs) with defense-in-depth: key-name filtering at the adapter layer, regex pattern redaction at the sanitization layer, and environment stripping at the subprocess layer. The audit trail provides non-repudiation for run events, though it lacks rotation and integrity verification.

The critical gap is the absence of input validation on `scenario_id` at `runner.py:179`, which creates a path traversal vulnerability from malicious packs. The broader gap of scenario trust boundaries is acknowledged and deferred in the WBS.

**Overall**: Acceptable for the current prototype/alpha stage. For a v1.0 or production deployment, recommendations #1, #2, and #3 should be completed before releasing to untrusted users.