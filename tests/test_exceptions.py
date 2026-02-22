"""Tests for custom exception hierarchy."""

from writ.exceptions import (
    CommandNotFoundError,
    ConfigError,
    ExecutionError,
    PipelineError,
    ReplError,
    VariableError,
)


def test_repl_error_is_base_exception() -> None:
    err = ReplError("base error")
    assert isinstance(err, Exception)
    assert str(err) == "base error"


def test_config_error_inherits_repl_error() -> None:
    err = ConfigError("bad config")
    assert isinstance(err, ReplError)


def test_command_not_found_stores_name_and_available() -> None:
    err = CommandNotFoundError("foo", available=["bar", "baz"])
    assert err.command_name == "foo"
    assert err.available == ["bar", "baz"]
    assert "foo" in str(err)


def test_variable_error_inherits_repl_error() -> None:
    err = VariableError("missing var")
    assert isinstance(err, ReplError)


def test_execution_error_stores_returncode() -> None:
    err = ExecutionError("failed", returncode=1)
    assert err.returncode == 1
    assert isinstance(err, ReplError)


def test_pipeline_error_stores_step_name() -> None:
    err = PipelineError("step failed", step_name="lint")
    assert err.step_name == "lint"
    assert isinstance(err, ReplError)
