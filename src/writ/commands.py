"""Command registry and resolution."""

from writ.config import CommandConfig
from writ.exceptions import CommandNotFoundError


class CommandRegistry:
    """Registry of available commands with alias resolution."""

    def __init__(self, commands: dict[str, CommandConfig]) -> None:
        self._commands = commands
        self._alias_map: dict[str, str] = {}
        for name, cmd in commands.items():
            for alias in cmd.aliases:
                self._alias_map[alias] = name

    def get(self, name_or_alias: str) -> CommandConfig:
        """Get a command by name or alias."""
        if name_or_alias in self._commands:
            return self._commands[name_or_alias]
        if name_or_alias in self._alias_map:
            return self._commands[self._alias_map[name_or_alias]]
        raise CommandNotFoundError(name_or_alias, available=self.list_names())

    def has(self, name_or_alias: str) -> bool:
        """Check if a command exists by name or alias."""
        return name_or_alias in self._commands or name_or_alias in self._alias_map

    def list_names(self) -> list[str]:
        """Return all command names."""
        return list(self._commands.keys())

    def filter_by_tag(self, tag: str) -> list[CommandConfig]:
        """Return commands matching a tag."""
        return [cmd for cmd in self._commands.values() if tag in cmd.tags]

    def all_tags(self) -> list[str]:
        """Return all unique tags across commands."""
        tags: set[str] = set()
        for cmd in self._commands.values():
            tags.update(cmd.tags)
        return sorted(tags)
