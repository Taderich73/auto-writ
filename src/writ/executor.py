"""Shell command execution with streaming and capture."""

import os
import subprocess
import threading
import time
from typing import IO

from writ.output import ExecutionResult
from writ.variables import SecretStore


class Executor:
    """Executes shell commands with streaming output and capture."""

    def __init__(
        self,
        shell: str = "/bin/zsh",
        secrets: SecretStore | None = None,
        stream_output: bool = True,
    ) -> None:
        self._shell = shell
        self._secrets = secrets or SecretStore()
        self._stream_output = stream_output

    def run(
        self,
        command: str,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> ExecutionResult:
        """Execute a command and return the result."""
        run_env = os.environ.copy()
        run_env.update(self._secrets.as_env_dict())
        if env:
            run_env.update(env)

        start = time.monotonic()
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        try:
            proc = subprocess.Popen(
                [self._shell, "-c", command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=run_env,
                text=True,
            )

            stdout_thread = threading.Thread(
                target=self._read_stream,
                args=(proc.stdout, stdout_lines, True),
            )
            stderr_thread = threading.Thread(
                target=self._read_stream,
                args=(proc.stderr, stderr_lines, False),
            )
            stdout_thread.start()
            stderr_thread.start()

            proc.wait(timeout=timeout)
            stdout_thread.join(timeout=5)
            stderr_thread.join(timeout=5)

            returncode = proc.returncode
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            stdout_thread.join(timeout=5)
            stderr_thread.join(timeout=5)
            returncode = -9
        finally:
            duration = time.monotonic() - start

        stdout_text = self._secrets.mask("".join(stdout_lines))
        stderr_text = self._secrets.mask("".join(stderr_lines))

        return ExecutionResult(
            command=command,
            returncode=returncode,
            stdout=stdout_text,
            stderr=stderr_text,
            duration=duration,
        )

    def _read_stream(self, stream: IO[str] | None, lines: list[str], is_stdout: bool) -> None:
        """Read a stream line-by-line, optionally printing to console."""
        if stream is None:
            return
        for line in stream:
            masked = self._secrets.mask(line)
            lines.append(masked)
            if self._stream_output and is_stdout:
                print(masked, end="", flush=True)
        stream.close()
