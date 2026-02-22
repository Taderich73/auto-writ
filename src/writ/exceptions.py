"""Custom exception hierarchy for the REPL."""


class ReplError(Exception):
    """Base exception for all REPL errors."""


class ConfigError(ReplError):
    """Raised when config loading or validation fails."""


class CommandNotFoundError(ReplError):
    """Raised when a command is not found in the registry."""

    def __init__(self, command_name: str, available: list[str] | None = None) -> None:
        self.command_name = command_name
        self.available = available or []
        suggestions = ""
        if self.available:
            suggestions = f" Available: {', '.join(self.available)}"
        super().__init__(f"Command not found: {command_name}.{suggestions}")


class VariableError(ReplError):
    """Raised when variable resolution fails."""


class ExecutionError(ReplError):
    """Raised when command execution fails."""

    def __init__(self, message: str, returncode: int = -1) -> None:
        self.returncode = returncode
        super().__init__(message)


class PipelineError(ReplError):
    """Raised when pipeline execution fails."""

    def __init__(self, message: str, step_name: str = "") -> None:
        self.step_name = step_name
        super().__init__(message)
