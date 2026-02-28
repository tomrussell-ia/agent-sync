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

### From Source

```bash
git clone https://github.com/tomrussell-ia/agent-sync.git
cd agent-sync
pip install -e .
```

### With Optional Dependencies

For probing features (GitHub Copilot SDK and MCP):

```bash
pip install -e ".[probe]"
```

## Usage

```bash
# Launch the dashboard
agent-sync

# View help
agent-sync --help
```

## Requirements

- Python 3.11 or higher
- Dependencies:
  - click >= 8.1
  - rich >= 13.0
  - textual >= 1.0

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
├── prober.py           # Agent probing
├── scanner.py          # Configuration scanner
├── serializers.py      # Data serialization
└── sync_engine.py      # Sync orchestration
```

## Development

### Setup Development Environment

```bash
# Install dependencies
pip install -e ".[probe]"

# Install pre-commit hooks (recommended)
pip install pre-commit
pre-commit install
```

The pre-commit hooks will automatically run linting, formatting, and validation checks before each commit.

### Running Tests

```bash
pytest
```

### Code Quality

This project uses:
- **Ruff** for linting and formatting
- **Pre-commit hooks** for automated checks
- **MyPy** for optional type checking

Run checks manually:
```bash
# Lint and format
ruff check src/ --fix
ruff format src/

# Run pre-commit on all files
pre-commit run --all-files
```

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

See [LICENSE](LICENSE) file for details.

## Support

For issues and questions, please [open an issue](https://github.com/tomrussell-ia/agent-sync/issues).
