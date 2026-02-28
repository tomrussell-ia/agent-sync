# Agent Sync - Agent Instructions

## Project Overview

Agent Sync is a Python CLI tool and dashboard for managing and synchronizing AI agent configurations across multiple platforms (GitHub Copilot, Claude, Codex, VS Code).

**Key components:**
- Scanner: Discovers agent configs
- Sync Engine: Detects drift and generates fixes  
- Dashboard: Interactive TUI (Textual)
- Console: Rich terminal output

## Setup Commands

```bash
# Install globally (recommended)
uv tool install --editable .

# After global install, use these commands:
agent-sync           # Launch dashboard
async               # Short alias
agent-sync check    # Check drift
agent-sync fix      # Apply fixes

# Or run from source during development
uv run agent-sync

# Run tests
uv run pytest

# Lint and format
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Type check
uv run mypy src/
```

## Code Style

- **Python 3.11+** with type hints
- Follow **ruff** lint rules (configured in pyproject.toml)
- Use **dataclasses** for models
- Rich/Textual for UI
- Synchronous code only (no async)

## File Organization

```
src/agent_sync/
├── models.py        # Dataclass models
├── scanner.py       # Config discovery
├── sync_engine.py   # Drift detection
├── dashboard.py     # Textual TUI
├── console.py       # Rich CLI output
├── formatters/      # Config generators
└── prober.py        # Validation only
```

## Testing

- Write **pytest** tests for new features
- Use **AAA pattern** (Arrange, Act, Assert)
- Mock filesystem with `tmp_path` fixture
- Keep coverage **>80%**

## Boundaries

- **Never modify** `uv.lock` manually
- **Don't commit** secrets or API keys
- **Don't modify** installed agent binaries
- **File operations** within workspace only
- **Prober**: Validation only, no network calls
