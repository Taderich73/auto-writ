"""Tests for command registry and resolution."""

import pytest

from writ.commands import CommandRegistry
from writ.config import CommandConfig
from writ.exceptions import CommandNotFoundError


@pytest.fixture
def registry() -> CommandRegistry:
    commands = {
        "lint": CommandConfig(
            name="lint",
            description="Run linter",
            command="echo lint",
            aliases=["l"],
            tags=["quality"],
        ),
        "test": CommandConfig(
            name="test",
            description="Run tests",
            command="echo test",
            aliases=["t"],
            tags=["quality", "test"],
        ),
        "deploy": CommandConfig(
            name="deploy",
            description="Deploy",
            command="echo deploy",
            aliases=[],
            tags=["deploy"],
            confirm=True,
        ),
    }
    return CommandRegistry(commands)


class TestCommandRegistry:
    def test_get_by_name(self, registry: CommandRegistry) -> None:
        cmd = registry.get("lint")
        assert cmd.name == "lint"

    def test_get_by_alias(self, registry: CommandRegistry) -> None:
        cmd = registry.get("l")
        assert cmd.name == "lint"

    def test_raises_command_not_found(self, registry: CommandRegistry) -> None:
        with pytest.raises(CommandNotFoundError) as exc_info:
            registry.get("nonexistent")
        assert "nonexistent" in str(exc_info.value)
        assert "lint" in exc_info.value.available

    def test_list_all_commands(self, registry: CommandRegistry) -> None:
        names = registry.list_names()
        assert sorted(names) == ["deploy", "lint", "test"]

    def test_filter_by_tag(self, registry: CommandRegistry) -> None:
        quality = registry.filter_by_tag("quality")
        assert sorted([c.name for c in quality]) == ["lint", "test"]

    def test_filter_by_tag_returns_empty_for_unknown(self, registry: CommandRegistry) -> None:
        result = registry.filter_by_tag("unknown")
        assert result == []

    def test_has_command(self, registry: CommandRegistry) -> None:
        assert registry.has("lint") is True
        assert registry.has("l") is True
        assert registry.has("nope") is False

    def test_all_tags(self, registry: CommandRegistry) -> None:
        tags = registry.all_tags()
        assert sorted(tags) == ["deploy", "quality", "test"]
