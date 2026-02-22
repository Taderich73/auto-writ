"""Integration tests for the full REPL stack."""

from pathlib import Path

import yaml

from writ.app import ReplApp
from writ.commands import CommandRegistry
from writ.config import ReplSettings, load_commands_config
from writ.executor import Executor
from writ.pipeline import PipelineLoader, PipelineRunner
from writ.variables import SecretStore, VariableResolver


class TestFullStack:
    def test_config_to_execution(self, tmp_path: Path) -> None:
        """Load config, resolve variables, execute command."""
        commands_yaml = tmp_path / "commands.yaml"
        commands_yaml.write_text(
            yaml.dump(
                {
                    "variables": {"greeting": "hello"},
                    "commands": {
                        "greet": {
                            "description": "Say hello",
                            "command": "echo ${greeting} world",
                            "aliases": ["g"],
                            "tags": ["test"],
                        }
                    },
                }
            )
        )

        config = load_commands_config(commands_yaml)
        registry = CommandRegistry(config.commands)
        resolver = VariableResolver(config_vars=config.variables)
        executor = Executor(shell="/bin/sh", stream_output=False)

        cmd = registry.get("g")  # by alias
        resolved = resolver.resolve(cmd.command)
        result = executor.run(resolved)

        assert result.succeeded
        assert "hello world" in result.stdout

    def test_yaml_pipeline_end_to_end(self, tmp_path: Path) -> None:
        """Load and run a YAML pipeline from disk."""
        wf_dir = tmp_path / "workflows"
        wf_dir.mkdir()
        pipeline_file = wf_dir / "test-pipeline.yaml"
        pipeline_file.write_text(
            yaml.dump(
                {
                    "name": "Test Pipeline",
                    "description": "Integration test",
                    "variables": {"msg": "integration"},
                    "steps": [
                        {"name": "step1", "run": "echo ${msg}", "on_failure": "abort"},
                        {
                            "name": "step2",
                            "run": "echo done",
                            "on_failure": "abort",
                            "when": [{"prev_step": "succeeded"}],
                        },
                    ],
                }
            )
        )

        loader = PipelineLoader(wf_dir)
        pipelines = loader.discover()
        assert len(pipelines) == 1
        assert pipelines[0].name == "test-pipeline"

        pipeline = loader.load_yaml(pipeline_file)
        executor = Executor(shell="/bin/sh", stream_output=False)
        resolver = VariableResolver(config_vars={})
        runner = PipelineRunner(executor=executor, resolver=resolver)

        results = runner.run_yaml(pipeline)
        assert len(results) == 2
        assert all(r.succeeded for r in results)
        assert "integration" in results[0].execution_result.stdout

    def test_shell_pipeline_end_to_end(self, tmp_path: Path) -> None:
        """Run a shell script pipeline."""
        wf_dir = tmp_path / "workflows"
        wf_dir.mkdir()
        script = wf_dir / "test.sh"
        script.write_text("#!/usr/bin/env bash\necho shell_ok\n")
        script.chmod(0o755)

        loader = PipelineLoader(wf_dir)
        pipelines = loader.discover()
        assert any(p.name == "test" and p.pipeline_type == "shell" for p in pipelines)

        executor = Executor(shell="/bin/sh", stream_output=False)
        resolver = VariableResolver(config_vars={})
        runner = PipelineRunner(executor=executor, resolver=resolver)

        result = runner.run_shell(script)
        assert result.succeeded
        assert "shell_ok" in result.stdout

    def test_secret_masking_in_pipeline(self, tmp_path: Path) -> None:
        """Secrets are masked in pipeline output."""
        secrets = SecretStore()
        secrets.add("API_KEY", "topsecret123")
        executor = Executor(shell="/bin/sh", secrets=secrets, stream_output=False)
        resolver = VariableResolver(config_vars={}, secrets=secrets)
        runner = PipelineRunner(executor=executor, resolver=resolver)

        from writ.pipeline import PipelineStep, YamlPipeline

        pipeline = YamlPipeline(
            title="Secret Test",
            description="",
            variables={},
            steps=[
                PipelineStep(name="leak", run="echo ${API_KEY}", on_failure="abort"),
            ],
        )
        results = runner.run_yaml(pipeline)
        assert results[0].succeeded
        assert "topsecret123" not in results[0].execution_result.stdout
        assert "***" in results[0].execution_result.stdout

    def test_repl_app_loads_and_completes(self, tmp_path: Path) -> None:
        """ReplApp loads config and provides completions."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        wf_dir = tmp_path / "workflows"
        wf_dir.mkdir()

        (config_dir / "commands.yaml").write_text(
            yaml.dump(
                {
                    "variables": {},
                    "commands": {
                        "build": {
                            "description": "Build project",
                            "command": "echo build",
                            "aliases": ["b"],
                            "tags": [],
                        }
                    },
                }
            )
        )

        settings = ReplSettings(mode="strict")
        app = ReplApp(settings=settings, config_dir=config_dir, workflows_dir=wf_dir)
        app.load_config()

        completions = app.get_completions()
        assert "build" in completions
        assert "b" in completions
        assert "help" in completions
        assert app.allow_shell_escape() is False
