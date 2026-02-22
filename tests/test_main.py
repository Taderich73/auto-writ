"""Tests for the entry point."""

from pathlib import Path

from writ.__main__ import resolve_paths


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
