"""Shared logic for CLI subcommands and REPL builtins."""

import subprocess

from writ.config import LOGS_DIR, VALID_EDITORS, WORKFLOWS_DIR, WRIT_HOME

DEFAULT_SETTINGS_YAML = """\
writ:
  mode: open
  prompt: "writ> "
  history_file: ~/.writ_history
  shell: /bin/zsh
  editor: vim

paths:
  workflows: ./workflows
  config: ~/.auto-writ

output:
  stream: true
  capture: true
  buffer_size: 50

secrets:
  sources:
    - env
    - dotenv
  dotenv_path: .env
  mask_in_output: true
"""

DEFAULT_COMMANDS_YAML = """\
variables: {}

commands: {}
"""


def run_init() -> None:
    """Bootstrap the ~/.auto-writ directory with default config files.

    Creates the directory and writes settings.yaml and commands.yaml
    if they don't already exist. Idempotent: never overwrites existing files.
    """
    home = WRIT_HOME.expanduser()
    created_anything = False

    if not home.exists():
        home.mkdir(parents=True)
        print(f"Created {home}")
        created_anything = True

    for subdir in (LOGS_DIR, WORKFLOWS_DIR):
        subdir_path = home / subdir
        if not subdir_path.exists():
            subdir_path.mkdir()
            print(f"Created {subdir_path}")
            created_anything = True

    settings_path = home / "settings.yaml"
    if not settings_path.exists():
        settings_path.write_text(DEFAULT_SETTINGS_YAML)
        print(f"Created {settings_path}")
        created_anything = True

    commands_path = home / "commands.yaml"
    if not commands_path.exists():
        commands_path.write_text(DEFAULT_COMMANDS_YAML)
        print(f"Created {commands_path}")
        created_anything = True

    if not created_anything:
        print(f"Already initialized: {home}")


def run_config(editor: str, target: str = "settings") -> None:
    """Open a config file in the specified editor.

    Args:
        editor: Editor command to use (must be in VALID_EDITORS).
        target: Which config file to open — "settings" or "commands".
    """
    if editor not in VALID_EDITORS:
        print(f"Unknown editor: {editor}. Must be one of {VALID_EDITORS}")
        return

    home = WRIT_HOME.expanduser()
    if not home.exists():
        print(f"Config directory not found: {home}")
        print("Run 'writ init' first to create it.")
        return

    filename = "commands.yaml" if target == "commands" else "settings.yaml"
    path = home / filename
    if not path.exists():
        print(f"Config file not found: {path}")
        print("Run 'writ init' first to create it.")
        return

    subprocess.run([editor, str(path)])
