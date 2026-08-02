Field Test Workspace

This directory is the local workspace for field tests.

- agents/: git-cloned third-party agent repositories (ignored by git)
- results/: local run artifacts, logs, and reports (ignored by git)

Notes
- Do not vendor or commit third-party code here. Repos are cloned at pinned SHAs per field.json.
- Secrets must not be written to disk. Sanitizers should mask API keys in any saved prompts/completions/logs.
- This folder is intentionally ignored by git (see .gitignore entries for field/agents/ and field/results/).
