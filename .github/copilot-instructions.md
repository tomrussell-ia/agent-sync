# GitHub Copilot Instructions

> **Note**: See [AGENTS.md](../AGENTS.md) for core project setup, code style, testing guidelines, and boundaries.

## GitHub Copilot-Specific Guidance

This file contains instructions specific to GitHub Copilot workflows. For general agent instructions, refer to the main AGENTS.md file.

### Common Copilot Tasks

#### Adding New Agent Support

1. Update models in `models.py` (dataclass with type hints)
2. Add scanning logic in `scanner.py` (filesystem discovery)
3. Implement validation in `plugin_validator.py` (schema validation)
4. Add sync logic to `sync_engine.py` (drift detection)

#### Extending the Dashboard

1. Modify `dashboard.py` using Textual widgets
2. Update console output in `console.py` for Rich CLI output
3. Add formatting as needed in `formatters/`

#### Configuration Changes

1. Update config schema in `config.py`
2. Handle migration if breaking change
3. Update documentation (README.md, CONTRIBUTING.md)

### Architecture Notes

- **Separation of Concerns**: UI (dashboard), business logic (sync_engine), data (models)
- **Configuration**: Centralized in config.py, uses TOML format
- **Plugin System**: Extensible validation and scanning capabilities
- **File Operations**: All within workspace, no external modifications

### Technology Stack

- **Language**: Python 3.11+
- **CLI**: Click for argument parsing
- **TUI**: Textual for interactive dashboard
- **Output**: Rich for formatted console output
- **Build**: Hatchling with uv package manager
- **Testing**: pytest with tmp_path fixtures

### Key Modules

```
src/agent_sync/
├── cli.py              # Click command definitions
├── config.py           # TOML config management
├── console.py          # Rich console output
├── dashboard.py        # Textual TUI screens
├── formatters/         # Config generators
├── log_parser.py       # MCP log parsing
├── models.py           # Dataclass schemas
├── plugin_validator.py # JSON schema validation
├── prober.py           # File-based validation
├── scanner.py          # Config discovery
├── serializers.py      # TOML/JSON serialization
└── sync_engine.py      # Drift detection logic
```

### Error Handling Patterns

- Use specific exception types (FileNotFoundError, ValueError, etc.)
- Provide actionable error messages with context
- Log errors with Rich console for debugging
- Graceful degradation when optional features unavailable

### Security Reminders

- Never commit API keys, tokens, or credentials
- Use .env files for sensitive data (excluded in .gitignore)
- Validate all user input and file paths
- Follow principle of least privilege for file operations
