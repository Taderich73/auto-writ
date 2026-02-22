"""Entry point for python -m writ."""

import sys
from pathlib import Path

from writ.app import ReplApp
from writ.config import ReplSettings, load_settings
from writ.exceptions import ConfigError


def resolve_paths(
    config_path: str = "./config",
    workflows_path: str = "./workflows",
) -> tuple[Path, Path]:
    """Resolve config and workflows directory paths."""
    return Path(config_path), Path(workflows_path)


def main() -> int:
    """Run the REPL."""
    config_dir = Path("./config")
    settings_path = config_dir / "settings.yaml"

    try:
        if settings_path.exists():
            settings = load_settings(settings_path)
        else:
            settings = ReplSettings()
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
