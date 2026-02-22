"""Tests for the entry point."""

from pathlib import Path
from unittest.mock import patch

from writ.__main__ import _build_parser, _load_repl_settings, main, resolve_paths
from writ.config import ReplSettings


def test_resolve_paths_defaults() -> None:
    config_dir, workflows_dir = resolve_paths()
    assert config_dir == Path("./config")
    assert workflows_dir == Path("./workflows")


def test_resolve_paths_from_settings() -> None:
    config_dir, workflows_dir = resolve_paths(
        config_path="/tmp/myconfig", workflows_path="/tmp/mywf"
    )
    assert config_dir == Path("/tmp/myconfig")
    assert workflows_dir == Path("/tmp/mywf")


class TestBuildParser:
    def test_parses_init(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["init"])
        assert args.command == "init"

    def test_parses_config_defaults(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["config"])
        assert args.command == "config"
        assert args.target == "settings"
        assert args.editor is None

    def test_parses_config_with_target(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["config", "commands"])
        assert args.command == "config"
        assert args.target == "commands"

    def test_parses_config_with_editor(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["config", "--editor", "nano"])
        assert args.editor == "nano"

    def test_no_args_gives_no_command(self) -> None:
        parser = _build_parser()
        args = parser.parse_args([])
        assert args.command is None


class TestMainInit:
    def test_init_calls_run_init(self) -> None:
        with (
            patch("sys.argv", ["writ", "init"]),
            patch("writ.__main__.run_init") as mock_init,
        ):
            result = main()
        mock_init.assert_called_once()
        assert result == 0


class TestMainConfig:
    def test_config_calls_run_config(self) -> None:
        with (
            patch("sys.argv", ["writ", "config", "--editor", "nano"]),
            patch("writ.__main__.run_config") as mock_config,
            patch("writ.__main__._load_repl_settings", return_value=ReplSettings()),
        ):
            result = main()
        mock_config.assert_called_once_with(editor="nano", target="settings")
        assert result == 0

    def test_config_uses_settings_editor(self) -> None:
        settings = ReplSettings(editor="emacs")
        with (
            patch("sys.argv", ["writ", "config"]),
            patch("writ.__main__.run_config") as mock_config,
            patch("writ.__main__._load_repl_settings", return_value=settings),
        ):
            result = main()
        mock_config.assert_called_once_with(editor="emacs", target="settings")
        assert result == 0


class TestLoadReplSettings:
    def test_loads_from_home(self, tmp_path: Path) -> None:
        settings_content = (
            "writ:\n  mode: strict\n  editor: nano\npaths:\n" "  config: /tmp\n  workflows: /tmp\n"
        )
        home_dir = tmp_path / "home-auto-writ"
        home_dir.mkdir()
        (home_dir / "settings.yaml").write_text(settings_content)

        with patch("writ.__main__.WRIT_HOME", home_dir):
            settings = _load_repl_settings()
        assert settings.mode == "strict"
        assert settings.editor == "nano"

    def test_falls_back_to_defaults(self, tmp_path: Path) -> None:
        empty_home = tmp_path / "empty-home"
        empty_home.mkdir()
        # No settings.yaml in home dir or local ./config/
        with patch("writ.__main__.WRIT_HOME", empty_home):
            settings = _load_repl_settings()
        assert settings.editor == "vim"
        assert settings.mode == "open"
