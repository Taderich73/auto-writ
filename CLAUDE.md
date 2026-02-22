# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**auto-writ** — CLI tool for issuing formal commands to infrastructure systems. Provides a REPL with variable substitution, pipeline orchestration, secret management, and shell escape control.

- Python >=3.13, built with Poetry
- Entry point: `writ = "writ.__main__:main"`

## Build & Development Commands

```bash
make install          # Install dependencies (poetry install)
make dev              # Full dev environment setup (install + pre-commit hooks)
make format           # Auto-format with black + ruff
make lint             # Ruff + pylint
make mypy             # Type checking (strict mode)
make bandit           # Security scanning
make test             # Run tests via tox
make coverage         # Tests with coverage (80% minimum threshold)
make all              # All quality checks
```

### Running individual tests

```bash
# Single test file
poetry run pytest tests/test_app.py

# Single test
poetry run pytest tests/test_app.py::TestParseInput::test_simple_command -v

# Via tox
tox -e py3
```

### Tox environments

`py3`, `format`, `format-check`, `lint`, `mypy`, `bandit`, `coverage`, `all`, `clean`, `dev`, `watch`

## Architecture

```
User Input → parse_input() → CommandRegistry lookup → VariableResolver → Executor → OutputBuffer
```

### Core modules (`src/writ/`)

| Module | Purpose |
|---|---|
| `app.py` | `ReplApp` — main REPL loop, built-in commands, prompt_toolkit integration |
| `commands.py` | `CommandRegistry` — name/alias lookup, tag filtering |
| `cli.py` | `run_init()` + `run_config()` — bootstrap `~/.auto-writ/` and open config in editor |
| `config.py` | `CommandConfig`, `CommandsConfig`, `ReplSettings` dataclasses; YAML loaders; `WRIT_HOME`, `VALID_EDITORS` constants |
| `executor.py` | `Executor` — subprocess execution with streaming, capture, secret masking, threading for parallel stdout/stderr |
| `pipeline.py` | `PipelineLoader` + `PipelineRunner` — YAML/Python/shell pipeline discovery and execution with conditionals |
| `variables.py` | `SecretStore` (masking, dotenv) + `VariableResolver` (`${VAR}` substitution) |
| `output.py` | `ExecutionResult` dataclass + `OutputBuffer` ring buffer |
| `exceptions.py` | Exception hierarchy: `ConfigError`, `CommandNotFoundError`, `VariableError`, `ExecutionError`, `PipelineError` |

### Variable resolution precedence

Pipeline variables → Config variables → Secrets → OS environment

### Configuration

- `~/.auto-writ/settings.yaml` — User-level REPL settings (mode, prompt, shell, editor, paths, output, secrets)
- `~/.auto-writ/commands.yaml` — User-level commands with aliases, tags, confirmation, timeout, env overrides
- `config/settings.yaml` — Project-local fallback settings
- `config/commands.yaml` — Project-local fallback commands
- `workflows/` — Pipeline files (.yaml, .py, .sh)

Settings resolution order: `~/.auto-writ/settings.yaml` → `./config/settings.yaml` → built-in defaults.

### CLI subcommands

- `writ init` — Bootstrap `~/.auto-writ/` with default settings and commands files
- `writ config [--editor EDITOR] [settings|commands]` — Open config file in editor
- `writ` (no args) — Start the REPL

### Security modes

- **open** — shell escapes (`!command`) allowed
- **strict** — shell escapes blocked

## Tool Configuration

- **Black**: 100 char line length
- **Ruff**: rules E, F, I, W; 100 char line length
- **MyPy**: strict mode, Python 3.13
- **Bandit**: skips B404, B603, B604; excludes tests
- **Pylint**: 100 char line length, minimum score 9.0
- **Pytest**: test discovery in `tests/`
