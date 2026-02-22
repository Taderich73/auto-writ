"""Tests for pipeline loading and execution."""

import time
from pathlib import Path

import pytest

from writ.commands import CommandRegistry
from writ.executor import Executor
from writ.pipeline import (
    PipelineContext,
    PipelineLoader,
    PipelineRunner,
    PipelineStep,
    YamlPipeline,
)
from writ.variables import VariableResolver


@pytest.fixture
def executor() -> Executor:
    return Executor(shell="/bin/sh", stream_output=False)


@pytest.fixture
def resolver() -> VariableResolver:
    return VariableResolver(config_vars={"target": "staging"})


@pytest.fixture
def empty_registry() -> CommandRegistry:
    return CommandRegistry({})


class TestPipelineLoader:
    def test_discover_yaml_pipelines(self, fixtures_dir: Path) -> None:
        loader = PipelineLoader(fixtures_dir)
        pipelines = loader.discover()
        names = [p.name for p in pipelines]
        assert "simple_pipeline" in names

    def test_discover_shell_pipelines(self, fixtures_dir: Path) -> None:
        loader = PipelineLoader(fixtures_dir)
        pipelines = loader.discover()
        names = [p.name for p in pipelines]
        assert "sample_workflow" in names

    def test_discover_python_pipelines(self, fixtures_dir: Path) -> None:
        loader = PipelineLoader(fixtures_dir)
        pipelines = loader.discover()
        # Both .py and .sh share name "sample_workflow" but different types
        types = {p.name: p.pipeline_type for p in pipelines}
        assert "sample_workflow" in types

    def test_load_yaml_pipeline(self, fixtures_dir: Path) -> None:
        loader = PipelineLoader(fixtures_dir)
        pipeline = loader.load_yaml(fixtures_dir / "simple_pipeline.yaml")
        assert isinstance(pipeline, YamlPipeline)
        assert pipeline.title == "Simple Pipeline"
        assert len(pipeline.steps) == 2


class TestYamlPipelineExecution:
    def test_runs_simple_pipeline(self, executor: Executor, resolver: VariableResolver) -> None:
        runner = PipelineRunner(executor=executor, resolver=resolver)
        pipeline = YamlPipeline(
            title="Test",
            description="test",
            variables={},
            steps=[
                PipelineStep(name="s1", run="echo hello", on_failure="abort"),
                PipelineStep(name="s2", run="echo world", on_failure="abort"),
            ],
        )
        results = runner.run_yaml(pipeline)
        assert len(results) == 2
        assert all(r.succeeded for r in results)

    def test_aborts_on_failure(self, executor: Executor, resolver: VariableResolver) -> None:
        runner = PipelineRunner(executor=executor, resolver=resolver)
        pipeline = YamlPipeline(
            title="Test",
            description="test",
            variables={},
            steps=[
                PipelineStep(name="s1", run="exit 1", on_failure="abort"),
                PipelineStep(name="s2", run="echo should_not_run", on_failure="abort"),
            ],
        )
        results = runner.run_yaml(pipeline)
        assert len(results) == 1
        assert not results[0].succeeded

    def test_continues_on_failure_when_configured(
        self, executor: Executor, resolver: VariableResolver
    ) -> None:
        runner = PipelineRunner(executor=executor, resolver=resolver)
        pipeline = YamlPipeline(
            title="Test",
            description="test",
            variables={},
            steps=[
                PipelineStep(name="s1", run="exit 1", on_failure="continue"),
                PipelineStep(name="s2", run="echo ran", on_failure="abort"),
            ],
        )
        results = runner.run_yaml(pipeline)
        assert len(results) == 2
        assert not results[0].succeeded
        assert results[1].succeeded

    def test_evaluates_prev_step_condition(
        self, executor: Executor, resolver: VariableResolver
    ) -> None:
        runner = PipelineRunner(executor=executor, resolver=resolver)
        pipeline = YamlPipeline(
            title="Test",
            description="test",
            variables={},
            steps=[
                PipelineStep(name="s1", run="echo ok", on_failure="abort"),
                PipelineStep(
                    name="s2",
                    run="echo conditional",
                    on_failure="abort",
                    when=[{"prev_step": "succeeded"}],
                ),
            ],
        )
        results = runner.run_yaml(pipeline)
        assert len(results) == 2
        assert all(r.succeeded for r in results)

    def test_skips_step_when_condition_fails(
        self, executor: Executor, resolver: VariableResolver
    ) -> None:
        runner = PipelineRunner(executor=executor, resolver=resolver)
        pipeline = YamlPipeline(
            title="Test",
            description="test",
            variables={"target": "staging"},
            steps=[
                PipelineStep(
                    name="s1",
                    run="echo should_skip",
                    on_failure="abort",
                    when=[{"target": "production"}],
                ),
            ],
        )
        results = runner.run_yaml(pipeline)
        assert len(results) == 1
        assert results[0].skipped is True

    def test_resolves_variables_in_run(
        self, executor: Executor, resolver: VariableResolver
    ) -> None:
        runner = PipelineRunner(executor=executor, resolver=resolver)
        pipeline = YamlPipeline(
            title="Test",
            description="test",
            variables={"target": "staging"},
            steps=[
                PipelineStep(name="s1", run="echo ${target}", on_failure="abort"),
            ],
        )
        results = runner.run_yaml(pipeline)
        assert results[0].succeeded
        assert "staging" in results[0].execution_result.stdout


class TestPipelineContext:
    def test_run_executes_shell_command(self, executor: Executor) -> None:
        ctx = PipelineContext(
            executor=executor,
            resolver=VariableResolver(config_vars={}),
            registry=CommandRegistry({}),
        )
        result = ctx.run("echo from_ctx")
        assert result.returncode == 0
        assert "from_ctx" in result.stdout

    def test_log_stores_messages(self, executor: Executor) -> None:
        ctx = PipelineContext(
            executor=executor,
            resolver=VariableResolver(config_vars={}),
            registry=CommandRegistry({}),
        )
        ctx.log("test message")
        assert "test message" in ctx.logs


class TestForkShell:
    def test_fork_returns_uuid_and_log_path(
        self, tmp_path: Path, executor: Executor, resolver: VariableResolver
    ) -> None:
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        script = tmp_path / "test.sh"
        script.write_text("#!/bin/sh\necho hello from fork\n")
        script.chmod(0o755)

        runner = PipelineRunner(executor=executor, resolver=resolver)
        fork_id, log_path = runner.fork_shell(script, log_dir)

        assert len(fork_id) == 36  # UUID4 format
        assert log_path.exists()
        assert log_path.parent == log_dir
        assert log_path.name == f"{fork_id}.log"

    def test_fork_writes_metadata_header(
        self, tmp_path: Path, executor: Executor, resolver: VariableResolver
    ) -> None:
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        script = tmp_path / "test.sh"
        script.write_text("#!/bin/sh\necho hello\n")
        script.chmod(0o755)

        runner = PipelineRunner(executor=executor, resolver=resolver)
        fork_id, log_path = runner.fork_shell(script, log_dir)

        # Give the process a moment to start
        time.sleep(0.1)
        content = log_path.read_text()
        assert "--- FORK:" in content
        assert "Started:" in content
        assert "Script:" in content
        assert str(script) in content

    def test_fork_captures_output_and_trailer(
        self, tmp_path: Path, executor: Executor, resolver: VariableResolver
    ) -> None:
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        script = tmp_path / "test.sh"
        script.write_text("#!/bin/sh\necho hello from fork\n")
        script.chmod(0o755)

        runner = PipelineRunner(executor=executor, resolver=resolver)
        fork_id, log_path = runner.fork_shell(script, log_dir)

        # Wait for process to finish and trailer to be written
        time.sleep(1.0)
        content = log_path.read_text()
        assert "hello from fork" in content
        assert "Finished:" in content
        assert "Exit code: 0" in content
        assert "Duration:" in content

    def test_fork_captures_nonzero_exit(
        self, tmp_path: Path, executor: Executor, resolver: VariableResolver
    ) -> None:
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        script = tmp_path / "fail.sh"
        script.write_text("#!/bin/sh\nexit 42\n")
        script.chmod(0o755)

        runner = PipelineRunner(executor=executor, resolver=resolver)
        fork_id, log_path = runner.fork_shell(script, log_dir)

        time.sleep(1.0)
        content = log_path.read_text()
        assert "Exit code: 42" in content
