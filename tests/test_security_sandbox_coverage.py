# ruff: noqa: S108
"""Unit tests for sandbox.py covering SandboxConfig, sandboxed_run,
DockerConfig, and run_in_container — targeting uncovered lines 165-166, 168,
193-224.

No Docker daemon required — subprocess calls are mocked.
"""

from __future__ import annotations

import builtins
import json
import os
import subprocess
from unittest import mock

import pytest

from evalforge.security.sandbox import (
    SANDBOX_ALLOWLIST,
    DockerConfig,
    SandboxConfig,
    run_in_container,
    sandboxed_run,
)


class TestSandboxConfig:
    def test_defaults(self) -> None:
        cfg = SandboxConfig()
        assert cfg.enabled is False
        assert cfg.allowlist == SANDBOX_ALLOWLIST
        assert cfg.timeout_multiplier == 2.0

    def test_custom_enabled_and_multiplier(self) -> None:
        cfg = SandboxConfig(enabled=True, timeout_multiplier=3.0)
        assert cfg.enabled is True
        assert cfg.timeout_multiplier == 3.0

    def test_custom_allowlist(self) -> None:
        custom = {"PATH", "HOME", "MY_VAR"}
        cfg = SandboxConfig(allowlist=custom)
        assert cfg.allowlist == custom

    def test_shared_default_allowlist(self) -> None:
        cfg1 = SandboxConfig()
        cfg2 = SandboxConfig()
        assert cfg1.allowlist == cfg2.allowlist


class TestSandboxedRun:
    def test_non_sandboxed_passthrough(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_run = mock.MagicMock(return_value=subprocess.CompletedProcess(
            args=["echo", "hi"], returncode=0, stdout="hi\n", stderr="",
        ))
        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("MY_SECRET", "xyz")

        config = SandboxConfig(enabled=False)
        result = sandboxed_run(["echo", "hi"], config, timeout=10.0)

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["timeout"] == 10.0
        assert "MY_SECRET" in call_kwargs["env"]
        assert result.returncode == 0

    def test_non_sandboxed_with_cwd_and_input(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_run = mock.MagicMock(return_value=subprocess.CompletedProcess(
            args=["ls"], returncode=0, stdout="", stderr="",
        ))
        monkeypatch.setattr(subprocess, "run", mock_run)

        result = sandboxed_run(
            ["ls"], SandboxConfig(enabled=False), timeout=30.0,
            input="hello", cwd="/tmp"
        )

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["input"] == "hello"
        assert call_kwargs["cwd"] == "/tmp"
        assert result.returncode == 0

    def test_sandboxed_allowlist_filtering(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_run = mock.MagicMock(return_value=subprocess.CompletedProcess(
            args=["cmd"], returncode=0, stdout="", stderr="",
        ))
        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("PATH", "/usr/bin")
        monkeypatch.setenv("HOME", "/home/test")
        monkeypatch.setenv("SECRET_TOKEN", "secret123")
        monkeypatch.setenv("EVALFORGE_SANDBOX", "1")

        sandboxed_run(["cmd"], SandboxConfig(enabled=True), timeout=10.0)

        call_env = mock_run.call_args.kwargs["env"]
        assert "PATH" in call_env
        assert "HOME" in call_env
        assert "SECRET_TOKEN" not in call_env
        assert call_env["EVALFORGE_SANDBOX"] == "1"

    def test_sandboxed_timeout_multiplier(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_run = mock.MagicMock(return_value=subprocess.CompletedProcess(
            args=["cmd"], returncode=0, stdout="", stderr="",
        ))
        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("PATH", "/bin")
        monkeypatch.setenv("HOME", "/root")

        config = SandboxConfig(enabled=True, timeout_multiplier=4.0)
        sandboxed_run(["cmd"], config, timeout=10.0)

        assert mock_run.call_args.kwargs["timeout"] == 40.0

    def test_sandboxed_custom_env_merges_allowlist(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_run = mock.MagicMock(return_value=subprocess.CompletedProcess(
            args=["cmd"], returncode=0, stdout="", stderr="",
        ))
        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("PATH", "/bin")
        monkeypatch.setenv("HOME", "/root")

        custom_env = {"PATH": "/custom/path", "EXTRA": "val"}
        config = SandboxConfig(enabled=True, allowlist={"PATH", "HOME"})
        sandboxed_run(["cmd"], config, env=custom_env, timeout=10.0)

        call_env = mock_run.call_args.kwargs["env"]
        assert call_env["PATH"] == "/custom/path"
        assert call_env["HOME"] == "/root"
        assert "EXTRA" not in call_env

    def test_sandboxed_with_cwd(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_run = mock.MagicMock(return_value=subprocess.CompletedProcess(
            args=["cmd"], returncode=0, stdout="", stderr="",
        ))
        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("PATH", "/bin")

        sandboxed_run(["cmd"], SandboxConfig(enabled=True), cwd="/work", timeout=10.0)
        assert mock_run.call_args.kwargs["cwd"] == "/work"

    def test_sandboxed_with_stdin_input(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_run = mock.MagicMock(return_value=subprocess.CompletedProcess(
            args=["cmd"], returncode=0, stdout="", stderr="",
        ))
        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setenv("PATH", "/bin")

        sandboxed_run(["cmd"], SandboxConfig(enabled=True), input="stdin-data", timeout=10.0)
        assert mock_run.call_args.kwargs["input"] == "stdin-data"


class TestDockerConfig:
    def test_defaults(self) -> None:
        cfg = DockerConfig()
        assert cfg.image == "evalforge-agent-runner"
        assert cfg.network_disabled is True
        assert cfg.read_only_root is True
        assert cfg.memory_limit == "512m"
        assert cfg.cpu_limit == 1.0
        assert cfg.add_host_gateway is False

    def test_custom_image(self) -> None:
        cfg = DockerConfig(image="custom-image:latest")
        assert cfg.image == "custom-image:latest"

    def test_all_fields_custom(self) -> None:
        cfg = DockerConfig(
            image="my-img",
            network_disabled=False,
            read_only_root=False,
            memory_limit="1g",
            cpu_limit=2.0,
            add_host_gateway=True,
        )
        assert cfg.network_disabled is False
        assert cfg.read_only_root is False
        assert cfg.memory_limit == "1g"
        assert cfg.cpu_limit == 2.0
        assert cfg.add_host_gateway is True

    def test_empty_memory_limit(self) -> None:
        cfg = DockerConfig(memory_limit="")
        assert cfg.memory_limit == ""


class TestRunInContainer:
    @pytest.fixture
    def mock_subprocess(self, monkeypatch: pytest.MonkeyPatch) -> mock.MagicMock:
        mock_run = mock.MagicMock(return_value=subprocess.CompletedProcess(
            args=[], returncode=0, stdout="ok", stderr="err",
        ))
        monkeypatch.setattr(subprocess, "run", mock_run)
        return mock_run

    @pytest.fixture
    def base_config(self) -> DockerConfig:
        return DockerConfig(image="test-image:latest")

    def test_basic_docker_args(self, mock_subprocess: mock.MagicMock, base_config: DockerConfig) -> None:  # noqa: E501
        run_in_container(["echo", "hi"], "payload", base_config, timeout=30.0)

        args = mock_subprocess.call_args.args[0]
        assert args[0] == "docker"
        assert "test-image:latest" in args
        assert "echo" in args

    def test_network_disabled(self, mock_subprocess: mock.MagicMock) -> None:
        cfg = DockerConfig(image="img", network_disabled=True)
        run_in_container(["cmd"], "", cfg, timeout=10.0)
        args = mock_subprocess.call_args.args[0]
        assert "--network" in args
        idx = args.index("--network")
        assert args[idx + 1] == "none"

    def test_network_enabled_no_flag(self, mock_subprocess: mock.MagicMock) -> None:
        cfg = DockerConfig(image="img", network_disabled=False)
        run_in_container(["cmd"], "", cfg, timeout=10.0)
        args = mock_subprocess.call_args.args[0]
        assert "--network" not in args

    def test_read_only_root(self, mock_subprocess: mock.MagicMock) -> None:
        cfg = DockerConfig(image="img", read_only_root=True)
        run_in_container(["cmd"], "", cfg, timeout=10.0)
        args = mock_subprocess.call_args.args[0]
        assert "--read-only" in args

    def test_read_only_root_disabled(self, mock_subprocess: mock.MagicMock) -> None:
        cfg = DockerConfig(image="img", read_only_root=False)
        run_in_container(["cmd"], "", cfg, timeout=10.0)
        args = mock_subprocess.call_args.args[0]
        assert "--read-only" not in args

    def test_memory_limit(self, mock_subprocess: mock.MagicMock) -> None:
        cfg = DockerConfig(image="img", memory_limit="256m")
        run_in_container(["cmd"], "", cfg, timeout=10.0)
        args = mock_subprocess.call_args.args[0]
        assert "--memory" in args
        idx = args.index("--memory")
        assert args[idx + 1] == "256m"

    def test_no_memory_limit_omitted(self, mock_subprocess: mock.MagicMock) -> None:
        cfg = DockerConfig(image="img", memory_limit="")
        run_in_container(["cmd"], "", cfg, timeout=10.0)
        args = mock_subprocess.call_args.args[0]
        assert "--memory" not in args

    def test_cpu_limit(self, mock_subprocess: mock.MagicMock) -> None:
        cfg = DockerConfig(image="img", cpu_limit=2.0)
        run_in_container(["cmd"], "", cfg, timeout=10.0)
        args = mock_subprocess.call_args.args[0]
        assert "--cpus" in args
        idx = args.index("--cpus")
        assert args[idx + 1] == "2.0"

    def test_no_cpu_limit_omitted(self, mock_subprocess: mock.MagicMock) -> None:
        cfg = DockerConfig(image="img", cpu_limit=0)
        run_in_container(["cmd"], "", cfg, timeout=10.0)
        args = mock_subprocess.call_args.args[0]
        assert "--cpus" not in args

    def test_tmpfs_always_present(self, mock_subprocess: mock.MagicMock, base_config: DockerConfig) -> None:  # noqa: E501
        run_in_container(["cmd"], "", base_config, timeout=10.0)
        args = mock_subprocess.call_args.args[0]
        assert "--tmpfs" in args

    def test_entrypoint_override(self, mock_subprocess: mock.MagicMock, base_config: DockerConfig) -> None:  # noqa: E501
        run_in_container(["cmd"], "", base_config, timeout=10.0)
        args = mock_subprocess.call_args.args[0]
        assert "--entrypoint" in args
        idx = args.index("--entrypoint")
        assert args[idx + 1] == ""

    def test_payload_passed_as_input(self, mock_subprocess: mock.MagicMock, base_config: DockerConfig) -> None:  # noqa: E501
        run_in_container(["cmd"], "stdin-payload", base_config, timeout=30.0)
        assert mock_subprocess.call_args.kwargs["input"] == "stdin-payload"

    def test_timeout_passed_through(self, mock_subprocess: mock.MagicMock, base_config: DockerConfig) -> None:  # noqa: E501
        run_in_container(["cmd"], "", base_config, timeout=42.0)
        assert mock_subprocess.call_args.kwargs["timeout"] == 42.0

    # ---- Uncovered line 168: add_host_gateway on Linux ----
    def test_add_host_gateway_on_linux(
        self, mock_subprocess: mock.MagicMock, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("platform.system", lambda: "Linux")
        cfg = DockerConfig(image="img", add_host_gateway=True)
        run_in_container(["cmd"], "", cfg, timeout=10.0)
        args = mock_subprocess.call_args.args[0]
        assert "--add-host" in args
        idx = args.index("--add-host")
        assert args[idx + 1] == "host.docker.internal:host-gateway"

    def test_add_host_gateway_on_non_linux(
        self, mock_subprocess: mock.MagicMock, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("platform.system", lambda: "Darwin")
        cfg = DockerConfig(image="img", add_host_gateway=True)
        run_in_container(["cmd"], "", cfg, timeout=10.0)
        args = mock_subprocess.call_args.args[0]
        assert "--add-host" not in args

    def test_add_host_gateway_disabled_no_flag(
        self, mock_subprocess: mock.MagicMock, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("platform.system", lambda: "Linux")
        cfg = DockerConfig(image="img", add_host_gateway=False)
        run_in_container(["cmd"], "", cfg, timeout=10.0)
        args = mock_subprocess.call_args.args[0]
        assert "--add-host" not in args

    # ---- Uncovered lines 165-166: platform import failure ----
    def test_platform_import_failure(
        self, mock_subprocess: mock.MagicMock, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _orig_import = builtins.__import__

        def _fail_platform(name, *args, **kwargs):  # type: ignore[no-untyped-def]
            if name == "platform":
                raise ImportError("simulated platform import failure")
            return _orig_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _fail_platform)
        cfg = DockerConfig(image="img", add_host_gateway=True)
        run_in_container(["cmd"], "", cfg, timeout=10.0)
        args = mock_subprocess.call_args.args[0]
        assert "--add-host" not in args

    # ---- Uncovered lines 193-224: docker logging ----
    def test_logging_dir_creates_files(
        self, mock_subprocess: mock.MagicMock, base_config: DockerConfig,
        monkeypatch: pytest.MonkeyPatch, tmp_path: str,
    ) -> None:
        log_dir = os.path.join(tmp_path, "docker-logs")
        monkeypatch.setenv("EVALFORGE_DOCKER_LOG_DIR", log_dir)

        run_in_container(["echo", "hello"], "the-payload", base_config, timeout=30.0)

        entries = os.listdir(log_dir)
        assert len(entries) == 1
        entry_dir = os.path.join(log_dir, entries[0])

        # stdout.txt
        with open(os.path.join(entry_dir, "stdout.txt"), encoding="utf-8") as f:
            assert f.read() == "ok"
        # stderr.txt
        with open(os.path.join(entry_dir, "stderr.txt"), encoding="utf-8") as f:
            assert f.read() == "err"
        # meta.json
        with open(os.path.join(entry_dir, "meta.json"), encoding="utf-8") as f:
            meta = json.load(f)
        assert meta["agent_cmd"] == ["echo", "hello"]
        assert meta["payload_len"] == len("the-payload")
        assert meta["returncode"] == 0
        assert "started_ts" in meta
        assert "finished_ts" in meta
        assert "duration_sec" in meta
        assert meta["config"]["image"] == "test-image:latest"

    def test_logging_handles_none_stdout_stderr(
        self, base_config: DockerConfig,
        monkeypatch: pytest.MonkeyPatch, tmp_path: str,
    ) -> None:
        """Cover lines 193-224 when result.stdout/result.stderr are None."""
        log_dir = os.path.join(tmp_path, "docker-logs-none")
        monkeypatch.setenv("EVALFORGE_DOCKER_LOG_DIR", log_dir)

        mock_run = mock.MagicMock(return_value=subprocess.CompletedProcess(
            args=[], returncode=1, stdout=None, stderr=None,
        ))
        monkeypatch.setattr(subprocess, "run", mock_run)

        run_in_container(["cmd"], "", base_config, timeout=10.0)

        entries = os.listdir(log_dir)
        entry_dir = os.path.join(log_dir, entries[0])
        with open(os.path.join(entry_dir, "stdout.txt"), encoding="utf-8") as f:
            assert f.read() == ""
        with open(os.path.join(entry_dir, "stderr.txt"), encoding="utf-8") as f:
            assert f.read() == ""

    # ---- Uncovered lines 222-224: logging exception swallowed ----
    def test_logging_exception_swallowed(
        self, base_config: DockerConfig,
        monkeypatch: pytest.MonkeyPatch, tmp_path: str,
    ) -> None:
        """Cover lines 222-224: when logging raises, execution continues."""
        log_dir = os.path.join(tmp_path, "docker-logs-err")
        monkeypatch.setenv("EVALFORGE_DOCKER_LOG_DIR", log_dir)

        mock_run = mock.MagicMock(return_value=subprocess.CompletedProcess(
            args=[], returncode=0, stdout="out", stderr="err",
        ))
        monkeypatch.setattr(subprocess, "run", mock_run)

        _orig_open = builtins.open

        def _fail_on_stdout(name, *args, **kwargs):  # type: ignore[no-untyped-def]
            if isinstance(name, str) and name.endswith("stdout.txt"):
                raise OSError("simulated write failure")
            return _orig_open(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", _fail_on_stdout)

        result = run_in_container(["cmd"], "p", base_config, timeout=10.0)
        assert result.returncode == 0
        assert result.stdout == "out"

    def test_logging_no_log_dir_skips(
        self, mock_subprocess: mock.MagicMock, base_config: DockerConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("EVALFORGE_DOCKER_LOG_DIR", raising=False)
        assert os.environ.get("EVALFORGE_DOCKER_LOG_DIR") is None
        run_in_container(["cmd"], "", base_config, timeout=10.0)

    def test_logging_empty_log_dir_skips(
        self, mock_subprocess: mock.MagicMock, base_config: DockerConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("EVALFORGE_DOCKER_LOG_DIR", "")
        run_in_container(["cmd"], "", base_config, timeout=10.0)
