"""Tests for the REPL app."""

from pathlib import Path

import pytest

from writ.app import ReplApp, parse_input
from writ.commands import CommandRegistry
from writ.config import CommandConfig, ReplSettings
from writ.pipeline import PipelineLoader


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


class TestPipelineFork:
    @pytest.fixture
    def app_with_workflows(self, tmp_path: Path) -> ReplApp:
        settings = ReplSettings(mode="open")
        workflows_dir = tmp_path / "workflows"
        workflows_dir.mkdir()
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        app = ReplApp(
            settings=settings,
            config_dir=tmp_path,
            workflows_dir=workflows_dir,
        )
        app._logs_dir = logs_dir
        return app

    def test_fork_rejects_yaml_pipeline(
        self, app_with_workflows: ReplApp, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        wf_dir = tmp_path / "workflows"
        (wf_dir / "deploy.yaml").write_text("name: Deploy\ndescription: deploy\nsteps: []\n")
        app_with_workflows._pipeline_loader = PipelineLoader(wf_dir)
        app_with_workflows._handle_pipeline("fork deploy")
        output = capsys.readouterr().out
        assert "only supported for shell" in output.lower()

    def test_fork_rejects_python_pipeline(
        self, app_with_workflows: ReplApp, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        wf_dir = tmp_path / "workflows"
        (wf_dir / "build.py").write_text("def run(ctx): pass\n")
        app_with_workflows._pipeline_loader = PipelineLoader(wf_dir)
        app_with_workflows._handle_pipeline("fork build")
        output = capsys.readouterr().out
        assert "only supported for shell" in output.lower()

    def test_fork_shell_pipeline(
        self, app_with_workflows: ReplApp, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        wf_dir = tmp_path / "workflows"
        script = wf_dir / "hello.sh"
        script.write_text("#!/bin/sh\necho forked\n")
        script.chmod(0o755)
        app_with_workflows._pipeline_loader = PipelineLoader(wf_dir)
        app_with_workflows._handle_pipeline("fork hello")
        output = capsys.readouterr().out
        assert "Forked" in output
        assert ".log" in output

    def test_fork_unknown_pipeline(
        self, app_with_workflows: ReplApp, capsys: pytest.CaptureFixture[str]
    ) -> None:
        app_with_workflows._handle_pipeline("fork nonexistent")
        output = capsys.readouterr().out
        assert "not found" in output.lower()


class TestPipelineLogs:
    @pytest.fixture
    def app_with_logs(self, tmp_path: Path) -> ReplApp:
        settings = ReplSettings(mode="open")
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        app = ReplApp(
            settings=settings,
            config_dir=tmp_path,
            workflows_dir=tmp_path / "workflows",
        )
        app._logs_dir = logs_dir
        return app

    def test_logs_list_empty(
        self, app_with_logs: ReplApp, capsys: pytest.CaptureFixture[str]
    ) -> None:
        app_with_logs._handle_pipeline("logs list")
        output = capsys.readouterr().out
        assert "No logs found" in output

    def test_logs_list_shows_entries(
        self, app_with_logs: ReplApp, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        logs_dir = tmp_path / "logs"
        log_file = logs_dir / "abc12345-1234-1234-1234-123456789abc.log"
        log_file.write_text(
            "--- FORK: deploy ---\n"
            "Started: 2026-02-22T14:30:00\n"
            "Script: /tmp/deploy.sh\n"
            "PID: 12345\n"
            "Log: /tmp/logs/abc.log\n"
            "---\n"
            "some output\n"
            "\n---\n"
            "Finished: 2026-02-22T14:31:00\n"
            "Exit code: 0\n"
            "Duration: 60.0s\n"
            "---\n"
        )
        app_with_logs._handle_pipeline("logs list")
        output = capsys.readouterr().out
        assert "deploy" in output
        assert "exit 0" in output

    def test_logs_list_shows_running_status(
        self, app_with_logs: ReplApp, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        logs_dir = tmp_path / "logs"
        log_file = logs_dir / "def12345-1234-1234-1234-123456789abc.log"
        log_file.write_text(
            "--- FORK: build ---\n"
            "Started: 2026-02-22T15:00:00\n"
            "Script: /tmp/build.sh\n"
            "PID: 99999\n"
            "Log: /tmp/logs/def.log\n"
            "---\n"
            "still running...\n"
        )
        app_with_logs._handle_pipeline("logs list")
        output = capsys.readouterr().out
        assert "build" in output
        assert "running" in output

    def test_logs_tail_reads_content(
        self, app_with_logs: ReplApp, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        logs_dir = tmp_path / "logs"
        log_file = logs_dir / "aaa11111-2222-3333-4444-555566667777.log"
        log_file.write_text(
            "--- FORK: test ---\n"
            "Started: 2026-02-22T14:30:00\n"
            "---\n"
            "line one\n"
            "line two\n"
            "\n---\n"
            "Finished: 2026-02-22T14:31:00\n"
            "Exit code: 0\n"
            "---\n"
        )
        app_with_logs._logs_tail("aaa11111")
        output = capsys.readouterr().out
        assert "line one" in output
        assert "line two" in output

    def test_logs_tail_partial_uuid_match(
        self, app_with_logs: ReplApp, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        logs_dir = tmp_path / "logs"
        log_file = logs_dir / "bbb22222-3333-4444-5555-666677778888.log"
        log_file.write_text("--- FORK: deploy ---\n---\noutput here\n\n---\nExit code: 0\n---\n")
        app_with_logs._logs_tail("bbb2")
        output = capsys.readouterr().out
        assert "output here" in output

    def test_logs_tail_not_found(
        self, app_with_logs: ReplApp, capsys: pytest.CaptureFixture[str]
    ) -> None:
        app_with_logs._logs_tail("nonexistent")
        output = capsys.readouterr().out
        assert "not found" in output.lower()

    def test_logs_tail_no_id(
        self, app_with_logs: ReplApp, capsys: pytest.CaptureFixture[str]
    ) -> None:
        app_with_logs._logs_tail("")
        output = capsys.readouterr().out
        assert "Usage" in output
