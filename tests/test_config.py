"""Tests for config loading and validation."""

from pathlib import Path

import pytest
import yaml

from writ.config import (
    CommandConfig,
    CommandsConfig,
    ReplSettings,
    load_commands_config,
    load_settings,
)
from writ.exceptions import ConfigError


@pytest.fixture
def valid_settings_path(fixtures_dir: Path) -> Path:
    return fixtures_dir / "valid_settings.yaml"


@pytest.fixture
def valid_commands_path(fixtures_dir: Path) -> Path:
    return fixtures_dir / "valid_commands.yaml"


class TestLoadSettings:
    def test_loads_valid_settings(self, valid_settings_path: Path) -> None:
        settings = load_settings(valid_settings_path)
        assert isinstance(settings, ReplSettings)
        assert settings.mode == "open"
        assert settings.prompt == "test> "
        assert settings.shell == "/bin/sh"
        assert settings.buffer_size == 10

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="not found"):
            load_settings(tmp_path / "nonexistent.yaml")

    def test_raises_on_invalid_yaml(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(": : :\n  invalid")
        with pytest.raises(ConfigError):
            load_settings(bad)

    def test_raises_on_invalid_mode(self, tmp_path: Path) -> None:
        cfg = tmp_path / "settings.yaml"
        cfg.write_text(yaml.dump({"writ": {"mode": "invalid"}}))
        with pytest.raises(ConfigError, match="mode"):
            load_settings(cfg)

    def test_defaults_for_missing_optional_fields(self, tmp_path: Path) -> None:
        cfg = tmp_path / "settings.yaml"
        cfg.write_text(yaml.dump({"writ": {"mode": "strict"}}))
        settings = load_settings(cfg)
        assert settings.mode == "strict"
        assert settings.prompt == "writ> "
        assert settings.buffer_size == 50


class TestLoadCommandsConfig:
    def test_loads_valid_commands(self, valid_commands_path: Path) -> None:
        config = load_commands_config(valid_commands_path)
        assert isinstance(config, CommandsConfig)
        assert "lint" in config.commands
        assert config.variables["project"] == "testapp"

    def test_command_has_correct_fields(self, valid_commands_path: Path) -> None:
        config = load_commands_config(valid_commands_path)
        lint = config.commands["lint"]
        assert isinstance(lint, CommandConfig)
        assert lint.description == "Run linter"
        assert lint.command == "echo lint ${project}"
        assert lint.aliases == ["l"]
        assert lint.tags == ["quality"]
        assert lint.confirm is False

    def test_command_with_confirm_and_timeout(self, valid_commands_path: Path) -> None:
        config = load_commands_config(valid_commands_path)
        deploy = config.commands["deploy"]
        assert deploy.confirm is True
        assert deploy.timeout == 30

    def test_command_with_env_overrides(self, valid_commands_path: Path) -> None:
        config = load_commands_config(valid_commands_path)
        test_cmd = config.commands["test"]
        assert test_cmd.env == {"PYTHONPATH": "src"}

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="not found"):
            load_commands_config(tmp_path / "nonexistent.yaml")

    def test_empty_commands_is_valid(self, tmp_path: Path) -> None:
        cfg = tmp_path / "commands.yaml"
        cfg.write_text(yaml.dump({"variables": {}, "commands": {}}))
        config = load_commands_config(cfg)
        assert config.commands == {}
