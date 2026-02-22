"""Pipeline loading, step execution, and conditionals."""

import importlib.util
import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

from writ.commands import CommandRegistry
from writ.exceptions import ConfigError, PipelineError
from writ.executor import Executor
from writ.output import ExecutionResult
from writ.variables import VariableResolver


@dataclass
class PipelineStep:
    """A single step in a YAML pipeline."""

    name: str
    on_failure: str = "abort"
    command: str | None = None
    run: str | None = None
    when: list[dict[str, str]] | None = None


@dataclass
class StepResult:
    """Result of executing a pipeline step."""

    step_name: str
    succeeded: bool
    skipped: bool = False
    execution_result: ExecutionResult | None = None


@dataclass
class YamlPipeline:
    """A parsed YAML pipeline."""

    title: str
    description: str
    variables: dict[str, str]
    steps: list[PipelineStep]


@dataclass
class PipelineInfo:
    """Metadata about a discovered pipeline."""

    name: str
    path: Path
    pipeline_type: str  # "yaml", "python", "shell"
    title: str = ""
    description: str = ""


class PipelineContext:
    """Context passed to Python pipeline scripts."""

    def __init__(
        self,
        executor: Executor,
        resolver: VariableResolver,
        registry: CommandRegistry,
    ) -> None:
        self._executor = executor
        self._resolver = resolver
        self._registry = registry
        self.logs: list[str] = []

    def run(self, command: str) -> ExecutionResult:
        """Execute a raw shell command."""
        resolved = self._resolver.resolve(command)
        return self._executor.run(resolved)

    def execute(self, command_name: str) -> ExecutionResult:
        """Execute a named command from the registry."""
        cmd = self._registry.get(command_name)
        resolved = self._resolver.resolve(cmd.command)
        return self._executor.run(resolved, env=cmd.env)

    def log(self, message: str) -> None:
        """Log a message."""
        self.logs.append(message)
        print(f"  [log] {message}")


class PipelineLoader:
    """Discovers and loads pipelines from a directory."""

    EXTENSIONS = {".yaml": "yaml", ".yml": "yaml", ".py": "python", ".sh": "shell"}

    def __init__(self, workflows_dir: Path) -> None:
        self._dir = workflows_dir

    def discover(self) -> list[PipelineInfo]:
        """Scan the workflows directory and return pipeline metadata."""
        if not self._dir.exists():
            return []

        pipelines: list[PipelineInfo] = []
        for path in sorted(self._dir.iterdir()):
            if path.suffix not in self.EXTENSIONS:
                continue
            if path.name.startswith(".") or path.name.startswith("__"):
                continue

            ptype = self.EXTENSIONS[path.suffix]
            name = path.stem
            title = name
            description = ""

            if ptype == "yaml":
                try:
                    with open(path) as f:
                        data = yaml.safe_load(f)
                    if isinstance(data, dict):
                        title = data.get("name", name)
                        description = data.get("description", "")
                except yaml.YAMLError:
                    pass

            pipelines.append(
                PipelineInfo(
                    name=name,
                    path=path,
                    pipeline_type=ptype,
                    title=title,
                    description=description,
                )
            )
        return pipelines

    def load_yaml(self, path: Path) -> YamlPipeline:
        """Parse a YAML pipeline file."""
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid pipeline YAML: {e}") from e

        if not isinstance(data, dict):
            raise ConfigError(f"Pipeline must be a mapping: {path}")

        steps: list[PipelineStep] = []
        for step_data in data.get("steps", []):
            steps.append(
                PipelineStep(
                    name=step_data.get("name", "unnamed"),
                    command=step_data.get("command"),
                    run=step_data.get("run"),
                    on_failure=step_data.get("on_failure", "abort"),
                    when=step_data.get("when"),
                )
            )

        return YamlPipeline(
            title=data.get("name", path.stem),
            description=data.get("description", ""),
            variables=data.get("variables", {}),
            steps=steps,
        )


class PipelineRunner:
    """Executes pipelines sequentially with conditional logic."""

    def __init__(
        self,
        executor: Executor,
        resolver: VariableResolver,
        registry: CommandRegistry | None = None,
    ) -> None:
        self._executor = executor
        self._resolver = resolver
        self._registry = registry or CommandRegistry({})

    def run_yaml(self, pipeline: YamlPipeline) -> list[StepResult]:
        """Execute a YAML pipeline and return step results."""
        # Merge pipeline variables into resolver
        if pipeline.variables:
            self._resolver = VariableResolver(
                config_vars={**self._resolver._config_vars, **pipeline.variables},
                pipeline_vars=pipeline.variables,
                secrets=self._resolver._secrets,
            )

        results: list[StepResult] = []
        for step in pipeline.steps:
            # Evaluate conditions
            if step.when and not self._evaluate_conditions(step.when, results):
                results.append(StepResult(step_name=step.name, succeeded=True, skipped=True))
                continue

            # Resolve and execute
            exec_result = self._execute_step(step)
            step_result = StepResult(
                step_name=step.name,
                succeeded=exec_result.succeeded,
                execution_result=exec_result,
            )
            results.append(step_result)

            # Handle failure
            if not exec_result.succeeded:
                if step.on_failure == "abort":
                    break
                if step.on_failure == "skip_remaining":
                    break

        return results

    def run_shell(self, path: Path) -> ExecutionResult:
        """Execute a shell pipeline script."""
        return self._executor.run(f"bash {path}")

    def run_python(self, path: Path) -> PipelineContext:
        """Execute a Python pipeline script."""
        ctx = PipelineContext(
            executor=self._executor,
            resolver=self._resolver,
            registry=self._registry,
        )
        spec = importlib.util.spec_from_file_location("workflow", path)
        if spec is None or spec.loader is None:
            raise PipelineError(f"Cannot load Python pipeline: {path}", step_name="")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if not hasattr(module, "run"):
            raise PipelineError(f"Python pipeline missing run(ctx) function: {path}", step_name="")
        module.run(ctx)
        return ctx

    def fork_shell(self, path: Path, log_dir: Path) -> tuple[str, Path]:
        """Fork a shell script into the background with log capture.

        Args:
            path: Path to the shell script.
            log_dir: Directory to write the log file.

        Returns:
            Tuple of (uuid string, log file path).
        """
        fork_id = str(uuid.uuid4())
        log_path = log_dir / f"{fork_id}.log"
        log_file = open(log_path, "w")  # noqa: SIM115 -- closed by daemon thread

        start_time = datetime.now()
        header = (
            f"--- FORK: {path.stem} ---\n"
            f"Started: {start_time.isoformat(timespec='seconds')}\n"
            f"Script: {path}\n"
        )
        log_file.write(header)
        log_file.flush()

        run_env = os.environ.copy()
        run_env.update(self._executor._secrets.as_env_dict())

        try:
            proc = subprocess.Popen(
                [self._executor._shell, str(path)],
                stdout=log_file,
                stderr=log_file,
                env=run_env,
            )
        except OSError:
            log_file.close()
            raise

        # NOTE: PID/Log lines written after Popen; fast scripts may interleave
        # output before these lines. Acceptable trade-off — PID is only
        # available after the process starts.
        log_file.write(f"PID: {proc.pid}\n")
        log_file.write(f"Log: {log_path}\n")
        log_file.write("---\n")
        log_file.flush()

        start_mono = time.monotonic()

        def _wait_and_write_trailer() -> None:
            proc.wait()
            duration = time.monotonic() - start_mono
            end_time = datetime.now()
            log_file.write(
                f"\n---\n"
                f"Finished: {end_time.isoformat(timespec='seconds')}\n"
                f"Exit code: {proc.returncode}\n"
                f"Duration: {duration:.1f}s\n"
                f"---\n"
            )
            log_file.close()

        thread = threading.Thread(target=_wait_and_write_trailer, daemon=True)
        thread.start()

        return fork_id, log_path

    def _execute_step(self, step: PipelineStep) -> ExecutionResult:
        """Execute a single pipeline step."""
        if step.command:
            cmd = self._registry.get(step.command)
            resolved = self._resolver.resolve(cmd.command)
            return self._executor.run(resolved, env=cmd.env)
        if step.run:
            resolved = self._resolver.resolve(step.run)
            return self._executor.run(resolved)
        raise PipelineError(
            f"Step '{step.name}' has neither 'command' nor 'run'", step_name=step.name
        )

    def _evaluate_conditions(
        self, conditions: list[dict[str, str]], results: list[StepResult]
    ) -> bool:
        """Evaluate all conditions (AND logic). Return True if all pass."""
        for condition in conditions:
            for key, expected in condition.items():
                if key == "prev_step":
                    if not results:
                        return False
                    prev = results[-1]
                    if expected == "succeeded" and not prev.succeeded:
                        return False
                    if expected == "failed" and prev.succeeded:
                        return False
                elif key.startswith("step."):
                    step_name = key[5:]
                    step_result = next((r for r in results if r.step_name == step_name), None)
                    if step_result is None:
                        return False
                    if expected == "succeeded" and not step_result.succeeded:
                        return False
                    if expected == "failed" and step_result.succeeded:
                        return False
                else:
                    # Variable check
                    try:
                        actual = self._resolver.resolve(f"${{{key}}}")
                        if actual != expected:
                            return False
                    except Exception:
                        return False
        return True
