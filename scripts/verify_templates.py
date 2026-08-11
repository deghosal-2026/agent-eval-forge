"""Verify project templates and structure. Used by CI template-verify job."""

from __future__ import annotations

import os
import sys
import tomllib


def check_template(path: str) -> None:
    try:
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict), f"{path}: not a dict"
        assert "jobs" in data, f"{path}: missing 'jobs'"
        print(f"{os.path.basename(path)}: valid")
    except Exception as e:
        print(f"{os.path.basename(path)}: invalid - {e}")
        sys.exit(1)


def check_pyproject(path: str = "pyproject.toml") -> None:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    for key in ("project", "build-system", "tool"):
        assert key in data, f"{path}: missing [{key}]"
    print(f"{os.path.basename(path)}: valid structure")


if __name__ == "__main__":
    ci_evalforge = os.path.join(".github", "workflows", "ci-evalforge.yml")
    if os.path.exists(ci_evalforge):
        check_template(ci_evalforge)
    check_pyproject()
    print("All templates valid")
