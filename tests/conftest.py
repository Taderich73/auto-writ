"""Shared test fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def tmp_config(tmp_path: Path) -> Path:
    """Create a temporary config directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def tmp_workflows(tmp_path: Path) -> Path:
    """Create a temporary workflows directory."""
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir()
    return wf_dir
