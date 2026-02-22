"""Tests for shell command execution."""

import pytest

from writ.executor import Executor
from writ.output import ExecutionResult
from writ.variables import SecretStore


class TestExecutor:
    @pytest.fixture
    def executor(self) -> Executor:
        return Executor(shell="/bin/sh")

    def test_executes_simple_command(self, executor: Executor) -> None:
        result = executor.run("echo hello")
        assert isinstance(result, ExecutionResult)
        assert result.returncode == 0
        assert result.stdout.strip() == "hello"

    def test_captures_stderr(self, executor: Executor) -> None:
        result = executor.run("echo error >&2")
        assert result.returncode == 0
        assert result.stderr.strip() == "error"

    def test_returns_nonzero_exit_code(self, executor: Executor) -> None:
        result = executor.run("exit 42")
        assert result.returncode == 42
        assert result.succeeded is False

    def test_records_duration(self, executor: Executor) -> None:
        result = executor.run("sleep 0.1")
        assert result.duration >= 0.05

    def test_passes_env_overrides(self, executor: Executor) -> None:
        result = executor.run("echo $MY_VAR", env={"MY_VAR": "injected"})
        assert result.stdout.strip() == "injected"

    def test_masks_secrets_in_captured_output(self) -> None:
        secrets = SecretStore()
        secrets.add("TOKEN", "supersecret")
        executor = Executor(shell="/bin/sh", secrets=secrets)
        result = executor.run("echo supersecret")
        assert "supersecret" not in result.stdout
        assert "***" in result.stdout

    def test_timeout_kills_long_command(self, executor: Executor) -> None:
        result = executor.run("sleep 10", timeout=1)
        assert result.returncode != 0

    def test_stores_original_command(self, executor: Executor) -> None:
        result = executor.run("echo test")
        assert result.command == "echo test"
