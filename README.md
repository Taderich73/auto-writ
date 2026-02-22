# writ

A CLI tool for issuing formal commands to infrastructure systems. Define named commands with variables, organize them with tags and aliases, chain them into pipelines, and control shell access through security modes — all from an interactive REPL.

## Features

- **Named commands** with aliases, tags, confirmation prompts, and timeouts
- **Variable substitution** (`${VAR}`) with layered resolution: pipeline > config > secrets > environment
- **Pipelines** — sequential workflows in YAML, Python, or shell scripts with conditional execution and failure policies
- **Secret management** — dotenv loading, env vars, automatic output masking
- **Security modes** — `open` (shell escapes allowed) or `strict` (locked down)
- **Output capture** — ring buffer with replay via `last`

## Requirements

- Python 3.13+
- Poetry

## Installation

```bash
git clone https://github.com/Taderich73/auto-writ.git
cd auto-writ
make dev
```

## Usage

```bash
# Initialize user config directory
writ init

# Start the REPL
writ

# Edit settings in your preferred editor
writ config
writ config --editor nano
writ config commands
```

### Defining commands

Edit `~/.auto-writ/commands.yaml` (or `config/commands.yaml` for project-local):

```yaml
variables:
  project: myapp
  env: staging

commands:
  lint:
    description: "Run linter"
    command: "ruff check src/${project}"
    aliases: [l]
    tags: [quality]

  deploy:
    description: "Deploy to target environment"
    command: "deploy.sh --env ${env}"
    confirm: true
    timeout: 30
    tags: [deploy]
```

### Built-in commands

| Command | Description |
|---|---|
| `help [--tag TAG]` | List commands, optionally filtered by tag |
| `pipeline list\|show\|run NAME` | Manage and run pipelines |
| `last [N]` | Replay Nth previous output |
| `history` | Browse command history |
| `vars` | Show variables and secrets |
| `reload` | Reload configuration |
| `mode [strict\|open]` | Switch security mode |
| `init` | Bootstrap `~/.auto-writ/` config directory |
| `config [commands]` | Open settings (or commands) in editor |
| `!command` | Shell escape (open mode only) |

### Pipelines

Place pipeline files in the `workflows/` directory. Supported formats: `.yaml`, `.py`, `.sh`.

**YAML pipeline** with conditionals:

```yaml
name: Deploy Pipeline
description: Build and deploy with checks

variables:
  target: staging

steps:
  - name: check
    run: "echo checking"
    on_failure: abort

  - name: deploy
    run: "echo deploying to ${target}"
    when:
      - prev_step: succeeded
    on_failure: abort

  - name: notify
    run: "echo notifying"
    when:
      - target: staging
    on_failure: continue
```

**Python pipeline:**

```python
def run(ctx):
    ctx.log("starting")
    result = ctx.run("echo hello")
    return result
```

### Configuration

Run `writ init` to create `~/.auto-writ/` with default config files. Settings are loaded from `~/.auto-writ/settings.yaml`, falling back to `./config/settings.yaml`, then built-in defaults.

```yaml
writ:
  mode: open
  prompt: "writ> "
  history_file: ~/.writ_history
  shell: /bin/zsh
  editor: vim

secrets:
  sources: [env, dotenv]
  dotenv_path: .env
  mask_in_output: true
```

## Development

```bash
make test       # Run tests
make lint       # Ruff + pylint
make mypy       # Type checking
make format     # Auto-format
make coverage   # Tests with 80% minimum coverage
make all        # All quality checks
```

## License

MIT
