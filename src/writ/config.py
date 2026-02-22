"""YAML config loading and validation."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from writ.exceptions import ConfigError

WRIT_HOME = Path("~/.auto-writ")
VALID_MODES = ("strict", "open")
VALID_EDITORS = ("vim", "nano", "emacs", "code")


@dataclass
class CommandConfig:
    """Configuration for a single command."""

    name: str
    description: str
    command: str
    aliases: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    confirm: bool = False
    timeout: int | None = None
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class CommandsConfig:
    """Top-level commands configuration."""

    variables: dict[str, str]
    commands: dict[str, CommandConfig]


@dataclass
class ReplSettings:
    """REPL settings from settings.yaml."""

    mode: str = "open"
    prompt: str = "writ> "
    history_file: str = "~/.writ_history"
    shell: str = "/bin/zsh"
    workflows_path: str = "./workflows"
    config_path: str = "./config"
    editor: str = "vim"
    stream: bool = True
    capture: bool = True
    buffer_size: int = 50
    secret_sources: list[str] = field(default_factory=lambda: ["env", "dotenv"])
    dotenv_path: str = ".env"
    mask_in_output: bool = True


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load and parse a YAML file."""
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {path}: {e}") from e
    if not isinstance(data, dict):
        raise ConfigError(f"Expected a mapping in {path}, got {type(data).__name__}")
    return data


def load_settings(path: Path) -> ReplSettings:
    """Load and validate settings.yaml."""
    data = _load_yaml(path)
    repl = data.get("writ", {}) or {}
    paths = data.get("paths", {}) or {}
    output = data.get("output", {}) or {}
    secrets = data.get("secrets", {}) or {}

    mode = repl.get("mode", "open")
    if mode not in VALID_MODES:
        raise ConfigError(f"Invalid mode: {mode}. Must be one of {VALID_MODES}")

    return ReplSettings(
        mode=mode,
        prompt=repl.get("prompt", "writ> "),
        history_file=repl.get("history_file", "~/.writ_history"),
        shell=repl.get("shell", "/bin/zsh"),
        workflows_path=paths.get("workflows", "./workflows"),
        config_path=paths.get("config", "./config"),
        editor=repl.get("editor", "vim"),
        stream=output.get("stream", True),
        capture=output.get("capture", True),
        buffer_size=output.get("buffer_size", 50),
        secret_sources=secrets.get("sources", ["env", "dotenv"]),
        dotenv_path=secrets.get("dotenv_path", ".env"),
        mask_in_output=secrets.get("mask_in_output", True),
    )


def load_commands_config(path: Path) -> CommandsConfig:
    """Load and validate commands.yaml."""
    data = _load_yaml(path)
    variables = data.get("variables", {}) or {}
    raw_commands = data.get("commands", {}) or {}

    commands: dict[str, CommandConfig] = {}
    for name, cmd_data in raw_commands.items():
        if not isinstance(cmd_data, dict):
            raise ConfigError(f"Command '{name}' must be a mapping")
        commands[name] = CommandConfig(
            name=name,
            description=cmd_data.get("description", ""),
            command=cmd_data.get("command", ""),
            aliases=cmd_data.get("aliases", []),
            tags=cmd_data.get("tags", []),
            confirm=cmd_data.get("confirm", False),
            timeout=cmd_data.get("timeout"),
            env=cmd_data.get("env", {}),
        )

    return CommandsConfig(variables=variables, commands=commands)
