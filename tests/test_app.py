"""Tests for the REPL app."""

from pathlib import Path

import pytest

from writ.app import ReplApp, parse_input
from writ.commands import CommandRegistry
from writ.config import CommandConfig, ReplSettings


class TestParseInput:
    def test_parses_simple_command(self) -> None:
        cmd, args = parse_input("lint")
        assert cmd == "lint"
        assert args == ""

    def test_parses_command_with_args(self) -> None:
        cmd, args = parse_input("help --tag deploy")
        assert cmd == "help"
        assert args == "--tag deploy"

    def test_detects_shell_escape(self) -> None:
        cmd, args = parse_input("!docker ps")
        assert cmd == "!"
        assert args == "docker ps"

    def test_handles_empty_input(self) -> None:
        cmd, args = parse_input("")
        assert cmd == ""
        assert args == ""

    def test_strips_whitespace(self) -> None:
        cmd, args = parse_input("  test  -v  ")
        assert cmd == "test"
        assert args == "-v"

    def test_parses_pipeline_subcommand(self) -> None:
        cmd, args = parse_input("pipeline run deploy-staging")
        assert cmd == "pipeline"
        assert args == "run deploy-staging"

    def test_parses_last_with_number(self) -> None:
        cmd, args = parse_input("last 3")
        assert cmd == "last"
        assert args == "3"

    def test_parses_mode_switch(self) -> None:
        cmd, args = parse_input("mode strict")
        assert cmd == "mode"
        assert args == "strict"


class TestReplApp:
    @pytest.fixture
    def settings(self) -> ReplSettings:
        return ReplSettings(mode="open")

    @pytest.fixture
    def registry(self) -> CommandRegistry:
        return CommandRegistry(
            {
                "lint": CommandConfig(
                    name="lint",
                    description="Run linter",
                    command="echo lint",
                    aliases=["l"],
                    tags=["quality"],
                ),
            }
        )

    def test_is_builtin_recognizes_builtins(self, settings: ReplSettings) -> None:
        app = ReplApp(settings=settings, config_dir=Path("."), workflows_dir=Path("."))
        assert app.is_builtin("help") is True
        assert app.is_builtin("commands") is True
        assert app.is_builtin("pipeline") is True
        assert app.is_builtin("last") is True
        assert app.is_builtin("history") is True
        assert app.is_builtin("vars") is True
        assert app.is_builtin("reload") is True
        assert app.is_builtin("mode") is True
        assert app.is_builtin("init") is True
        assert app.is_builtin("config") is True
        assert app.is_builtin("exit") is True
        assert app.is_builtin("quit") is True
        assert app.is_builtin("lint") is False

    def test_rejects_shell_escape_in_strict_mode(self) -> None:
        settings = ReplSettings(mode="strict")
        app = ReplApp(settings=settings, config_dir=Path("."), workflows_dir=Path("."))
        assert app.allow_shell_escape() is False

    def test_allows_shell_escape_in_open_mode(self) -> None:
        settings = ReplSettings(mode="open")
        app = ReplApp(settings=settings, config_dir=Path("."), workflows_dir=Path("."))
        assert app.allow_shell_escape() is True

    def test_completions_include_builtins_and_commands(
        self, settings: ReplSettings, registry: CommandRegistry
    ) -> None:
        app = ReplApp(settings=settings, config_dir=Path("."), workflows_dir=Path("."))
        app._registry = registry
        completions = app.get_completions()
        assert "help" in completions
        assert "lint" in completions
        assert "l" in completions

    def test_handle_commands_lists_configured_commands(
        self, settings: ReplSettings, registry: CommandRegistry, capsys: pytest.CaptureFixture[str]
    ) -> None:
        app = ReplApp(settings=settings, config_dir=Path("."), workflows_dir=Path("."))
        app._registry = registry
        app._handle_commands()
        output = capsys.readouterr().out
        assert "lint" in output
        assert "Run linter" in output
        assert "quality" in output

    def test_handle_commands_empty_registry(
        self, settings: ReplSettings, capsys: pytest.CaptureFixture[str]
    ) -> None:
        app = ReplApp(settings=settings, config_dir=Path("."), workflows_dir=Path("."))
        app._handle_commands()
        output = capsys.readouterr().out
        assert "No commands configured" in output
