"""REPL loop with prompt_toolkit integration."""

from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory

from writ.cli import run_config, run_init
from writ.commands import CommandRegistry
from writ.config import (
    LOGS_DIR,
    WRIT_HOME,
    CommandsConfig,
    ReplSettings,
    load_commands_config,
)
from writ.exceptions import CommandNotFoundError, PipelineError, ReplError
from writ.executor import Executor
from writ.output import OutputBuffer
from writ.pipeline import PipelineLoader, PipelineRunner
from writ.variables import SecretStore, VariableResolver

BUILTINS = {
    "help",
    "commands",
    "pipeline",
    "last",
    "history",
    "vars",
    "reload",
    "mode",
    "init",
    "config",
    "exit",
    "quit",
}


def parse_input(text: str) -> tuple[str, str]:
    """Parse user input into command and arguments."""
    text = text.strip()
    if not text:
        return "", ""
    if text.startswith("!"):
        return "!", text[1:].strip()
    parts = text.split(None, 1)
    cmd = parts[0]
    args = parts[1].strip() if len(parts) > 1 else ""
    return cmd, args


class ReplApp:
    """Main REPL application."""

    def __init__(
        self,
        settings: ReplSettings,
        config_dir: Path,
        workflows_dir: Path,
    ) -> None:
        self._settings = settings
        self._config_dir = config_dir
        self._workflows_dir = workflows_dir
        self._registry = CommandRegistry({})
        self._commands_config = CommandsConfig(variables={}, commands={})
        self._secrets = SecretStore()
        self._output_buffer = OutputBuffer(max_size=settings.buffer_size)
        self._executor = Executor(
            shell=settings.shell,
            secrets=self._secrets,
            stream_output=settings.stream,
        )
        self._pipeline_loader = PipelineLoader(workflows_dir)
        self._logs_dir = WRIT_HOME.expanduser() / LOGS_DIR

    def is_builtin(self, cmd: str) -> bool:
        """Check if a command is a built-in."""
        return cmd in BUILTINS

    def allow_shell_escape(self) -> bool:
        """Check if shell escape (!) is allowed."""
        return self._settings.mode == "open"

    def get_completions(self) -> list[str]:
        """Get all completable words for the prompt."""
        words = list(BUILTINS)
        words.extend(self._registry.list_names())
        for cmd in self._registry._commands.values():
            words.extend(cmd.aliases)
        return sorted(set(words))

    def load_config(self) -> None:
        """Load or reload configuration."""
        commands_path = self._config_dir / "commands.yaml"
        if commands_path.exists():
            self._commands_config = load_commands_config(commands_path)
            self._registry = CommandRegistry(self._commands_config.commands)

        # Load secrets
        if "dotenv" in self._settings.secret_sources:
            dotenv_path = Path(self._settings.dotenv_path).expanduser()
            self._secrets.load_dotenv(dotenv_path)

    def _make_resolver(self, pipeline_vars: dict[str, str] | None = None) -> VariableResolver:
        """Create a variable resolver with current state."""
        return VariableResolver(
            config_vars=self._commands_config.variables,
            pipeline_vars=pipeline_vars,
            secrets=self._secrets,
        )

    def _handle_commands(self) -> None:
        """List configured commands from commands.yaml."""
        names = self._registry.list_names()
        if not names:
            print("No commands configured.")
            return
        for name in names:
            cmd = self._registry.get(name)
            aliases = f" ({', '.join(cmd.aliases)})" if cmd.aliases else ""
            tags = f"  [{', '.join(cmd.tags)}]" if cmd.tags else ""
            print(f"  {name}{aliases}{tags}  -- {cmd.description}")

    def _handle_help(self, args: str) -> None:
        """Handle the help command."""
        if args.startswith("--tag "):
            tag = args[6:].strip()
            commands = self._registry.filter_by_tag(tag)
            if not commands:
                print(f"No commands with tag '{tag}'")
                return
            for cmd in commands:
                aliases = f" ({', '.join(cmd.aliases)})" if cmd.aliases else ""
                print(f"  {cmd.name}{aliases}  -- {cmd.description}")
        elif args:
            try:
                cmd = self._registry.get(args)
                print(f"  {cmd.name}: {cmd.description}")
                print(f"  Command: {cmd.command}")
                if cmd.aliases:
                    print(f"  Aliases: {', '.join(cmd.aliases)}")
                if cmd.tags:
                    print(f"  Tags: {', '.join(cmd.tags)}")
                if cmd.confirm:
                    print("  Requires confirmation")
                if cmd.timeout:
                    print(f"  Timeout: {cmd.timeout}s")
            except CommandNotFoundError:
                print(f"Unknown command: {args}")
        else:
            print("Built-in commands:")
            for name in sorted(BUILTINS):
                print(f"  {name}")
            print("\nConfigured commands:")
            for name in self._registry.list_names():
                cmd = self._registry.get(name)
                aliases = f" ({', '.join(cmd.aliases)})" if cmd.aliases else ""
                print(f"  {name}{aliases}  -- {cmd.description}")
            tags = self._registry.all_tags()
            if tags:
                print(f"\nTags: {', '.join(tags)}")
                print("Use 'help --tag <tag>' to filter")

    def _handle_pipeline(self, args: str) -> None:
        """Handle pipeline subcommands."""
        parts = args.split(None, 1)
        subcmd = parts[0] if parts else ""
        subargs = parts[1].strip() if len(parts) > 1 else ""

        if subcmd == "list":
            pipelines = self._pipeline_loader.discover()
            if not pipelines:
                print("No pipelines found.")
                return
            for p in pipelines:
                print(f"  {p.name} [{p.pipeline_type}]  -- {p.description or p.title}")

        elif subcmd == "show":
            self._show_pipeline(subargs)

        elif subcmd == "run":
            self._run_pipeline(subargs)

        elif subcmd == "fork":
            self._fork_pipeline(subargs)

        elif subcmd == "logs":
            self._handle_logs(subargs)

        else:
            print(
                "Usage: pipeline list | show <name> | run <name> | fork <name>"
                " | logs list | logs tail <id>"
            )

    def _show_pipeline(self, name: str) -> None:
        """Display pipeline steps without running."""
        pipelines = self._pipeline_loader.discover()
        match = next((p for p in pipelines if p.name == name), None)
        if not match:
            print(f"Pipeline not found: {name}")
            return

        if match.pipeline_type == "yaml":
            pipeline = self._pipeline_loader.load_yaml(match.path)
            print(f"Pipeline: {pipeline.title}")
            print(f"Description: {pipeline.description}")
            if pipeline.variables:
                print(f"Variables: {pipeline.variables}")
            print("Steps:")
            for i, step in enumerate(pipeline.steps, 1):
                cmd = step.command or step.run or "?"
                print(f"  {i}. {step.name}: {cmd} (on_failure={step.on_failure})")
                if step.when:
                    print(f"     when: {step.when}")
        else:
            print(f"Pipeline: {name} [{match.pipeline_type}]")
            print(f"Path: {match.path}")

    def _run_pipeline(self, name: str) -> None:
        """Execute a pipeline by name."""
        pipelines = self._pipeline_loader.discover()
        match = next((p for p in pipelines if p.name == name), None)
        if not match:
            print(f"Pipeline not found: {name}")
            return

        resolver = self._make_resolver()
        runner = PipelineRunner(
            executor=self._executor,
            resolver=resolver,
            registry=self._registry,
        )

        print(f'Running pipeline "{match.title or match.name}"...\n')

        if match.pipeline_type == "yaml":
            pipeline = self._pipeline_loader.load_yaml(match.path)
            results = runner.run_yaml(pipeline)
            print()
            for r in results:
                status = "SKIP" if r.skipped else ("OK" if r.succeeded else "FAIL")
                print(f"  [{status}] {r.step_name}")
            succeeded = all(r.succeeded or r.skipped for r in results)
            print(f'\nPipeline {"completed successfully" if succeeded else "FAILED"}.')

        elif match.pipeline_type == "shell":
            result = runner.run_shell(match.path)
            self._output_buffer.add(result)
            status = "completed" if result.succeeded else "FAILED"
            print(f"\nShell pipeline {status} (exit code {result.returncode}).")

        elif match.pipeline_type == "python":
            try:
                runner.run_python(match.path)
                print("\nPython pipeline completed.")
            except PipelineError as e:
                print(f"\nPython pipeline FAILED: {e}")

    def _fork_pipeline(self, name: str) -> None:
        """Fork a shell pipeline into the background."""
        if not name:
            print("Usage: pipeline fork <name>")
            return

        pipelines = self._pipeline_loader.discover()
        match = next((p for p in pipelines if p.name == name), None)
        if not match:
            print(f"Pipeline not found: {name}")
            return

        if match.pipeline_type != "shell":
            print(f"Fork is only supported for shell pipelines, not {match.pipeline_type}.")
            return

        self._logs_dir.mkdir(parents=True, exist_ok=True)

        resolver = self._make_resolver()
        runner = PipelineRunner(
            executor=self._executor,
            resolver=resolver,
            registry=self._registry,
        )
        fork_id, log_path = runner.fork_shell(match.path, self._logs_dir)
        print(f'Forked "{match.title or match.name}" \u2192 {log_path}')

    def _handle_logs(self, args: str) -> None:
        """Handle pipeline logs subcommands."""
        parts = args.split(None, 1)
        subcmd = parts[0] if parts else ""
        subargs = parts[1].strip() if len(parts) > 1 else ""

        if subcmd == "list":
            self._logs_list()
        elif subcmd == "tail":
            self._logs_tail(subargs)
        else:
            print("Usage: pipeline logs list | pipeline logs tail <id>")

    def _logs_list(self) -> None:
        """List fork log files with metadata."""
        if not self._logs_dir.exists():
            print("No logs found.")
            return

        log_files = sorted(
            self._logs_dir.glob("*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not log_files:
            print("No logs found.")
            return

        for log_path in log_files:
            fork_id = log_path.stem
            name = "unknown"
            started = "?"
            status = "running"

            try:
                content = log_path.read_text()
                for line in content.splitlines():
                    if line.startswith("--- FORK: "):
                        name = line[10:].rstrip(" -")
                    elif line.startswith("Started: "):
                        started = line[9:]
                    elif line.startswith("Exit code: "):
                        status = f"exit {line[11:]}"
            except OSError:
                pass

            print(f"  {fork_id}  {name}  {started}  {status}")

    def _logs_tail(self, id_prefix: str) -> None:
        """Live-follow a fork log file. Ctrl+C to stop."""
        if not id_prefix:
            print("Usage: pipeline logs tail <id>")
            return

        if not self._logs_dir.exists():
            print(f"Log not found: {id_prefix}")
            return

        matches = [p for p in self._logs_dir.glob("*.log") if p.stem.startswith(id_prefix)]
        if not matches:
            print(f"Log not found: {id_prefix}")
            return
        if len(matches) > 1:
            print(f"Ambiguous prefix '{id_prefix}', matches {len(matches)} logs.")
            return

        log_path = matches[0]
        try:
            with open(log_path) as f:
                # Print existing content
                while True:
                    line = f.readline()
                    if not line:
                        break
                    print(line, end="")

                # Check if process is done (trailer present)
                content = log_path.read_text()
                if "\n---\nFinished:" in content or "\n---\nExit code:" in content:
                    return

                # Live follow
                import time

                print("\n(following -- Ctrl+C to stop)\n")
                while True:
                    line = f.readline()
                    if line:
                        print(line, end="", flush=True)
                        # Check if trailer appeared
                        if "Exit code:" in line:
                            # Drain remaining lines
                            for remaining in f:
                                print(remaining, end="", flush=True)
                            return
                    else:
                        time.sleep(0.2)
        except KeyboardInterrupt:
            print("\n")

    def _handle_last(self, args: str) -> None:
        """Replay captured output."""
        n = 0
        if args:
            try:
                n = int(args)
            except ValueError:
                print("Usage: last [N]")
                return

        result = self._output_buffer.last(n)
        if result is None:
            print("No output to replay.")
            return
        print(f"--- Replay: {result.command} (exit {result.returncode}) ---")
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="")

    def _handle_vars(self) -> None:
        """Show current variables."""
        print("Config variables:")
        for k, v in self._commands_config.variables.items():
            print(f"  {k} = {v}")
        print("\nSecrets:")
        for k in sorted(self._secrets._secrets.keys()):
            print(f"  {k} = ***")

    def _handle_mode(self, args: str) -> None:
        """Show or switch mode."""
        if not args:
            print(f"Current mode: {self._settings.mode}")
            return
        if args in ("strict", "open"):
            self._settings.mode = args
            print(f"Mode switched to: {args}")
        else:
            print("Usage: mode [strict|open]")

    def _handle_init(self) -> None:
        """Handle the init builtin."""
        run_init()

    def _handle_config(self, args: str) -> None:
        """Handle the config builtin.

        Args:
            args: Optional target — "commands" to edit commands.yaml,
                  otherwise opens settings.yaml.
        """
        target = "commands" if args == "commands" else "settings"
        run_config(editor=self._settings.editor, target=target)

    def _execute_config_command(self, name_or_alias: str) -> None:
        """Execute a command from the config."""
        try:
            cmd = self._registry.get(name_or_alias)
        except CommandNotFoundError as e:
            print(str(e))
            return

        if cmd.confirm:
            response = input(f"  Run '{cmd.name}'? [y/N] ")
            if response.lower() != "y":
                print("  Cancelled.")
                return

        resolver = self._make_resolver()
        resolved = resolver.resolve(cmd.command)
        result = self._executor.run(resolved, env=cmd.env, timeout=cmd.timeout)
        self._output_buffer.add(result)

        if not result.succeeded:
            print(f"\nCommand failed (exit code {result.returncode})")

    def _execute_shell(self, command: str) -> None:
        """Execute a raw shell command."""
        result = self._executor.run(command)
        self._output_buffer.add(result)
        if not result.succeeded:
            print(f"\nCommand failed (exit code {result.returncode})")

    def run(self) -> int:
        """Run the REPL loop."""
        self.load_config()

        history_path = Path(self._settings.history_file).expanduser()
        history_path.parent.mkdir(parents=True, exist_ok=True)
        session: PromptSession[str] = PromptSession(
            history=FileHistory(str(history_path)),
            completer=WordCompleter(self.get_completions(), ignore_case=True),
        )

        print(f"writ ready (mode: {self._settings.mode}). Type 'help' for commands.\n")

        while True:
            try:
                text = session.prompt(self._settings.prompt)
            except KeyboardInterrupt:
                continue
            except EOFError:
                print("\nBye.")
                return 0

            cmd, args = parse_input(text)
            if not cmd:
                continue

            try:
                if cmd in ("exit", "quit"):
                    print("Bye.")
                    return 0
                elif cmd == "help":
                    self._handle_help(args)
                elif cmd == "commands":
                    self._handle_commands()
                elif cmd == "pipeline":
                    self._handle_pipeline(args)
                elif cmd == "last":
                    self._handle_last(args)
                elif cmd == "history":
                    print("(Use up/down arrows to browse history)")
                elif cmd == "vars":
                    self._handle_vars()
                elif cmd == "reload":
                    self.load_config()
                    self._pipeline_loader = PipelineLoader(self._workflows_dir)
                    print("Config reloaded.")
                elif cmd == "mode":
                    self._handle_mode(args)
                elif cmd == "init":
                    self._handle_init()
                elif cmd == "config":
                    self._handle_config(args)
                elif cmd == "!":
                    if self.allow_shell_escape():
                        self._execute_shell(args)
                    else:
                        print("Shell escape disabled in strict mode.")
                        print("Available commands:")
                        for name in self._registry.list_names():
                            print(f"  {name}")
                elif self._registry.has(cmd):
                    self._execute_config_command(cmd)
                else:
                    if self.allow_shell_escape():
                        # In open mode, try as raw shell
                        self._execute_shell(text)
                    else:
                        print(f"Unknown command: {cmd}")
                        print("Type 'help' for available commands.")
            except ReplError as e:
                print(f"Error: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")

        return 0
