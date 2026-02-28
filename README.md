# Agent Sync

Dashboard and sync tool for AI agent configurations across Copilot CLI, Claude, Codex, and VS Code.

## Overview

Agent Sync provides a unified interface to manage and synchronize agent configurations across multiple AI development tools. It helps developers maintain consistency in their AI tooling setup across different platforms and environments.

## Features

- 🔄 Sync agent configurations across multiple platforms
- 📊 Dashboard view of all configured agents
- ✅ Validation of agent configurations
- 🔍 Scan and discover agent configurations
- 📝 Rich console output with formatting

## Installation

### Global Installation (Recommended)

Install globally using [uv](https://docs.astral.sh/uv/) tool:

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh  # Unix
# or
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"  # Windows

# Install agent-sync globally
git clone https://github.com/tomrussell-ia/agent-sync.git
cd agent-sync
uv tool install --editable .
```

This installs two global commands:
- `agent-sync` - Full command name
- `async` - Short alias for convenience

**Troubleshooting:** If commands aren't recognized or throw `ModuleNotFoundError`:

**Issue 1: Command not found**
- Restart your terminal to pick up PATH changes
- Or add to PATH manually (see below)

**Issue 2: ModuleNotFoundError (conflicting pip installation)**
If you see `ModuleNotFoundError: No module named 'agent_sync'`, uninstall any old pip installation:
```powershell
# Windows
python -m pip uninstall agent-sync -y

# Unix/macOS
pip uninstall agent-sync -y
```

**Windows PATH:**
```powershell
# Restart your terminal, or add to PATH manually if needed:
$env:PATH += ";$env:USERPROFILE\.local\bin"

# Or add permanently:
[Environment]::SetEnvironmentVariable("PATH", "$env:PATH;$env:USERPROFILE\.local\bin", "User")
```

**Unix/macOS PATH:**
```bash
# Restart your terminal, or add to shell config if needed:
export PATH="$HOME/.local/bin:$PATH"

# Add to ~/.bashrc, ~/.zshrc, or ~/.profile:
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

Verify installation:
```bash
agent-sync --version
async --version
```

### Local Development Installation

Using [uv](https://docs.astral.sh/uv/) (recommended):

```bash
# Clone and install for development
git clone https://github.com/tomrussell-ia/agent-sync.git
cd agent-sync
uv sync --all-extras  # Installs all dependencies including dev tools
```

Using pip:

```bash
# From source
git clone https://github.com/tomrussell-ia/agent-sync.git
cd agent-sync
pip install -e ".[dev]"
```

## Usage

After global installation:

```bash
# Launch the dashboard (either command works)
agent-sync
async

# Check configuration drift
agent-sync check

# Apply fixes
agent-sync fix --dry-run  # Preview changes
agent-sync fix            # Apply changes

# Validate runtime connectivity
agent-sync probe

# View help
agent-sync --help
```

During local development:

```bash
# Run from source with uv
uv run agent-sync
```

## Requirements

- Python 3.11+ (3.14 recommended)
- [uv](https://docs.astral.sh/uv/) package manager (recommended) or pip
- Core dependencies: click, rich, textual, tomli-w
- Development: pytest, ruff, mypy, pre-commit

## Project Structure

```
src/agent_sync/
├── cli.py              # Command-line interface
├── config.py           # Configuration management
├── console.py          # Console utilities
├── dashboard.py        # Dashboard UI
├── formatters/         # Output formatting
├── log_parser.py       # Log parsing utilities
├── models.py           # Data models
├── plugin_validator.py # Plugin validation
├── prober.py           # Configuration validation
├── scanner.py          # Configuration scanner
├── serializers.py      # Data serialization
└── sync_engine.py      # Sync orchestration
```

## Development

### Setup Development Environment

Using uv (recommended):

```bash
# Clone the repository
git clone https://github.com/tomrussell-ia/agent-sync.git
cd agent-sync

# Install all dependencies (syncs from uv.lock)
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install
```

Using pip:

```bash
# Install with all dependencies
pip install -e ".[dev,probe]"

# Install pre-commit hooks
pre-commit install
```
pre-commit install
```

The pre-commit hooks will automatically run linting, formatting, and validation checks before each commit.

### Running Tests

Using uv:

```bash
uv run pytest
```

Using pip:

```bash
pytest
```

### Code Quality

This project uses:
- **Ruff** for linting and formatting
- **Pre-commit hooks** for automated checks
- **MyPy** for optional type checking

Run checks manually with uv:
```bash
# Lint and format
uv run ruff check src/ --fix
uv run ruff format src/
uv run mypy src/
```

Or directly if tools are installed globally:
```bash
ruff check src/ --fix
ruff format src/
mypy src/
```

# Run pre-commit on all files
pre-commit run --all-files
```

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

See [LICENSE](LICENSE) file for details.

## Support

For issues and questions, please [open an issue](https://github.com/tomrussell-ia/agent-sync/issues).
