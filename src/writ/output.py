"""Output capture, formatting, and replay buffer."""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ExecutionResult:
    """Result of a command execution."""

    command: str
    returncode: int
    stdout: str
    stderr: str
    duration: float
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def succeeded(self) -> bool:
        """Whether the command exited with code 0."""
        return self.returncode == 0


class OutputBuffer:
    """Ring buffer for storing command execution results."""

    def __init__(self, max_size: int = 50) -> None:
        self._buffer: deque[ExecutionResult] = deque(maxlen=max_size)

    def add(self, result: ExecutionResult) -> None:
        """Add a result to the buffer."""
        self._buffer.append(result)

    def last(self, n: int = 0) -> ExecutionResult | None:
        """Get the Nth most recent result. 0 = most recent."""
        idx = len(self._buffer) - 1 - n
        if idx < 0 or idx >= len(self._buffer):
            return None
        return self._buffer[idx]
