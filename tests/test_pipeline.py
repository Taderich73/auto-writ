"""Tests for pipeline loading and execution."""

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
