"""Tests for the CLI init and config commands."""

from pathlib import Path
from unittest.mock import patch

import yaml

from writ.cli import run_config, run_init


class TestRunInit:
    def test_creates_directory(self, tmp_path: Path) -> None:
        writ_home = tmp_path / ".auto-writ"
        with patch("writ.cli.WRIT_HOME", writ_home):
            run_init()
        assert writ_home.is_dir()

    def test_creates_settings_yaml(self, tmp_path: Path) -> None:
        writ_home = tmp_path / ".auto-writ"
        with patch("writ.cli.WRIT_HOME", writ_home):
            run_init()
        settings_path = writ_home / "settings.yaml"
        assert settings_path.exists()
        data = yaml.safe_load(settings_path.read_text())
        assert isinstance(data, dict)
        assert "writ" in data
        assert data["writ"]["editor"] == "vim"

    def test_creates_commands_yaml(self, tmp_path: Path) -> None:
        writ_home = tmp_path / ".auto-writ"
        with patch("writ.cli.WRIT_HOME", writ_home):
            run_init()
        commands_path = writ_home / "commands.yaml"
        assert commands_path.exists()
        data = yaml.safe_load(commands_path.read_text())
        assert isinstance(data, dict)
        assert "variables" in data
        assert "commands" in data

    def test_idempotent(self, tmp_path: Path) -> None:
        writ_home = tmp_path / ".auto-writ"
        with patch("writ.cli.WRIT_HOME", writ_home):
            run_init()

        settings_path = writ_home / "settings.yaml"
        original_content = settings_path.read_text()

        # Modify file to prove it won't be overwritten
        settings_path.write_text("custom: true\n")

        with patch("writ.cli.WRIT_HOME", writ_home):
            run_init()

        assert settings_path.read_text() == "custom: true\n"
        assert settings_path.read_text() != original_content

    def test_prints_created_paths(self, tmp_path: Path, capsys: object) -> None:
        writ_home = tmp_path / ".auto-writ"
        with patch("writ.cli.WRIT_HOME", writ_home):
            run_init()
        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert str(writ_home) in captured.out
        assert "settings.yaml" in captured.out
        assert "commands.yaml" in captured.out

    def test_creates_logs_directory(self, tmp_path: Path) -> None:
        writ_home = tmp_path / ".auto-writ"
        with patch("writ.cli.WRIT_HOME", writ_home):
            run_init()
        assert (writ_home / "logs").is_dir()

    def test_creates_workflows_directory(self, tmp_path: Path) -> None:
        writ_home = tmp_path / ".auto-writ"
        with patch("writ.cli.WRIT_HOME", writ_home):
            run_init()
        assert (writ_home / "workflows").is_dir()

    def test_logs_dir_idempotent(self, tmp_path: Path) -> None:
        writ_home = tmp_path / ".auto-writ"
        with patch("writ.cli.WRIT_HOME", writ_home):
            run_init()
            run_init()
        assert (writ_home / "logs").is_dir()
        assert (writ_home / "workflows").is_dir()

    def test_prints_already_initialized(self, tmp_path: Path, capsys: object) -> None:
        writ_home = tmp_path / ".auto-writ"
        with patch("writ.cli.WRIT_HOME", writ_home):
            run_init()
            run_init()
        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "Already initialized" in captured.out


class TestRunConfig:
    def test_opens_editor(self, tmp_path: Path) -> None:
        writ_home = tmp_path / ".auto-writ"
        writ_home.mkdir()
        (writ_home / "settings.yaml").write_text("writ: {}\n")
        with (
            patch("writ.cli.WRIT_HOME", writ_home),
            patch("writ.cli.subprocess.run") as mock_run,
        ):
            run_config(editor="vim", target="settings")
        mock_run.assert_called_once_with(["vim", str(writ_home / "settings.yaml")])

    def test_opens_commands_yaml(self, tmp_path: Path) -> None:
        writ_home = tmp_path / ".auto-writ"
        writ_home.mkdir()
        (writ_home / "commands.yaml").write_text("commands: {}\n")
        with (
            patch("writ.cli.WRIT_HOME", writ_home),
            patch("writ.cli.subprocess.run") as mock_run,
        ):
            run_config(editor="nano", target="commands")
        mock_run.assert_called_once_with(["nano", str(writ_home / "commands.yaml")])

    def test_requires_init_first(self, tmp_path: Path, capsys: object) -> None:
        writ_home = tmp_path / ".auto-writ"  # Does not exist
        with patch("writ.cli.WRIT_HOME", writ_home):
            run_config(editor="vim")
        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "Config directory not found" in captured.out
        assert "writ init" in captured.out

    def test_validates_editor(self, tmp_path: Path, capsys: object) -> None:
        writ_home = tmp_path / ".auto-writ"
        writ_home.mkdir()
        (writ_home / "settings.yaml").write_text("writ: {}\n")
        with patch("writ.cli.WRIT_HOME", writ_home):
            run_config(editor="notepad")
        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "Unknown editor: notepad" in captured.out

    def test_config_file_not_found(self, tmp_path: Path, capsys: object) -> None:
        writ_home = tmp_path / ".auto-writ"
        writ_home.mkdir()
        # No settings.yaml created
        with patch("writ.cli.WRIT_HOME", writ_home):
            run_config(editor="vim")
        captured = capsys.readouterr()  # type: ignore[union-attr]
        assert "Config file not found" in captured.out
        assert "writ init" in captured.out
