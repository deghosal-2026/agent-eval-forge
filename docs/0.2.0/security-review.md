# Security Review — v0.2.0

**Date:** 2026-08-10
**Reviewer:** Internal
**Status:** Complete
**References:** [v0.1.0 Security Review](../0.1.0/security-review.md)

## Scope

This review covers all new features and changes introduced in v0.2.0, including:
- 6 critical bug fixes (#269-#274)
- 15 Phase 2 features (#238-#294)
- 7 new framework adapters (#277-#290)
- Documentation updates (#275, #276, #291)

## v0.1.0 Findings — Remediation Status

All v0.1.0 security findings remain addressed. No regressions identified:

| Finding | v0.1.0 Status | v0.2.0 Status |
|---------|---------------|---------------|
| Sandbox mode (env stripping, isolation) | Addressed | No regression |
| Trust policies (adapter/tool matrix) | Addressed | No regression |
| Audit trail (per-run policy log) | Addressed | No regression |
| API key sanitization | Addressed | No regression |
| `scenario_id` path traversal | Addressed | Verified |
| Audit log rotation/size management | Addressed | No regression |
| Docker sandbox hardening | Addressed | No regression |

## New Feature Security Assessment

### Run Manifest (#238)

- **Risk:** Execution environment details (OS, arch, Python version, dependency tree) could aid reconnaissance.
- **Mitigation:** `--no-manifest` flag for privacy-sensitive environments. Env var names only, never values. Manifest stored locally in `.evalforge/runs/`.
- **Verdict:** Acceptable. No secrets exposure. Controllable via CLI flag.

### AdapterManifest (#251)

- **Risk:** Adapter metadata (capabilities, schemas, required secrets) could expose infrastructure details.
- **Mitigation:** Required secrets are names only, never values. Digest is SHA-256 of metadata only. Manifest is local artifact, not transmitted.
- **Verdict:** Acceptable. Follows same secret-safety pattern as run manifest.

### Plugin Registry (#250)

- **Risk:** Third-party scorer plugins execute arbitrary code.
- **Mitigation:** Plugins are loaded from declared entry points only. Trust boundary is the installed package. No remote plugin loading. Entry-point discovery requires explicit installation.
- **Verdict:** Acceptable with standard Python packaging trust model.

### 7 New Framework Adapters (#277-#290)

- **Risk:** Each new adapter executes third-party framework code and agent code.
- **Mitigation:** All adapters follow the existing sandbox model. Subprocess isolation available for untrusted agents. Trust policies enforced at validate/run. Model provider keys handled via env vars (sanitized in artifacts).
- **Verdict:** Acceptable. No new trust boundaries introduced.

### ToolStub Wiring (#272)

- **Risk:** Fixture mode intercepts tool calls — must not leak fixture data to agents or vice versa.
- **Mitigation:** ToolStub injected via adapter layer, not agent code. Multi-entry selector uses deterministic SHA-256 hash. Fixtures read from sandboxed paths. `verify_consumed()` provides auditability.
- **Verdict:** Acceptable. Fixture isolation maintained.

### Three-Gate Scoring (#239)

- **Risk:** Score dimensions (compatibility, safety, quality) must not be spoofable.
- **Mitigation:** All scorers run server-side within the harness. No agent- or network-injectable scoring data. Dimensions are computed from deterministic + LLM judge results.
- **Verdict:** Acceptable. No new attack surface.

## Path Traversal Verification

The `scenario_id` path traversal fix from v0.1.0 (WBS M8) was re-verified against v0.2.0 code. Path traversal vectors confirmed blocked for:
- Scenario pack loading (`pack_loader.py`)
- Run artifact paths (`cli/run.py`)
- Baseline storage (`baselines/store.py`)
- Adapter output paths (all adapters)

## Docker Sandbox

Docker sandbox hardening from v0.1.0 remains in effect:
- Read-only root filesystem
- Network isolation (default: none)
- Resource limits (CPU, memory)
- No privilege escalation
- Temp directory mounted as tmpfs

## Recommendations

1. **FUTURE:** Consider adding SBOM generation for plugin packages to track supply chain risk.
2. **FUTURE:** Consider signature verification for scenario packs loaded from external sources.
3. **FUTURE:** Evaluate need for per-adapter sandbox profiles as adapter count grows.

## Conclusion

v0.2.0 introduces no new security regressions. All v0.1.0 findings remain addressed. New features follow existing security patterns (env-only secret references, sandbox enforcement, trust policy gates). No blocking security issues identified for v0.2.0 release.
