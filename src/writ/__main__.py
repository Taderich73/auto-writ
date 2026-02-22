"""Entry point for python -m writ."""

import argparse
import sys
from pathlib import Path

from writ.app import ReplApp
from writ.cli import run_config, run_init
from writ.config import WRIT_HOME, ReplSettings, load_settings
from writ.exceptions import ConfigError


def resolve_paths(
    config_path: str = "./config",
    workflows_path: str = "./workflows",
) -> tuple[Path, Path]:
    """Resolve config and workflows directory paths."""
    return Path(config_path), Path(workflows_path)


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(prog="writ", description="auto-writ CLI")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init", help="Initialize ~/.auto-writ config directory")

    config_parser = subparsers.add_parser("config", help="Edit config files")
    config_parser.add_argument(
        "--editor",
        help="Editor to use (default: from settings or vim)",
    )
    config_parser.add_argument(
        "target",
        nargs="?",
        default="settings",
        choices=["settings", "commands"],
        help="Which config file to edit (default: settings)",
    )

    return parser


def _load_repl_settings() -> ReplSettings:
    """Load settings from ~/.auto-writ or fall back to defaults."""
    home_settings = WRIT_HOME.expanduser() / "settings.yaml"
    local_settings = Path("./config/settings.yaml")

    for path in (home_settings, local_settings):
        if path.exists():
            return load_settings(path)

    return ReplSettings()


def main() -> int:
    """Run the CLI or REPL."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "init":
        run_init()
        return 0

    if args.command == "config":
        try:
            settings = _load_repl_settings()
        except ConfigError as e:
            print(f"Config error: {e}", file=sys.stderr)
            return 1
        editor = args.editor or settings.editor
        run_config(editor=editor, target=args.target)
        return 0

    # No subcommand — start REPL
    try:
        settings = _load_repl_settings()
    except ConfigError as e:
        print(f"Config error: {e}", file=sys.stderr)
        return 1

    config_dir, workflows_dir = resolve_paths(
        config_path=settings.config_path,
        workflows_path=settings.workflows_path,
    )

    app = ReplApp(
        settings=settings,
        config_dir=config_dir,
        workflows_dir=workflows_dir,
    )
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
