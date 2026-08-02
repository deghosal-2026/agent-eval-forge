# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| 0.1.x | ✅ |

## Reporting a Vulnerability

Do NOT open a public issue. Email the maintainers directly. Include:

- Description of the vulnerability
- Steps to reproduce
- Affected versions
- Potential impact

We will acknowledge within 48 hours and provide a timeline for remediation.

## Security Design

EvalForge is a test framework — it runs agent code, not production services. Key security properties:

- **Sandbox mode** isolates agent execution (env stripping, timeout multiplier)
- **API keys are redacted** from all artifacts, logs, and reports
- **Trust policies** enforce adapter/tool restrictions per pack trust level
- **Secrets scanning** (trufflehog) runs in CI on every push
- **SBOM** generated per release for dependency transparency
