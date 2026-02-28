# Agent Sync - Custom AI Instructions

## Project Overview

Agent Sync is a Python-based dashboard and synchronization tool for managing AI agent configurations across multiple platforms including GitHub Copilot CLI, Claude, Codex, and VS Code.

## Technology Stack

- **Language**: Python 3.11+
- **CLI Framework**: Click
- **UI**: Textual (terminal UI framework)
- **Output**: Rich (formatted console output)
- **Build System**: Hatchling

## Code Organization

```
src/agent_sync/
├── cli.py              # Command-line interface entry point
├── config.py           # Configuration management
├── console.py          # Console utilities and helpers
├── dashboard.py        # Main dashboard UI implementation
├── formatters/         # Output formatting modules
├── log_parser.py       # Log parsing utilities
├── models.py           # Data models and schemas
├── plugin_validator.py # Agent plugin validation logic
├── prober.py           # Agent discovery and probing
├── scanner.py          # Configuration scanning
├── serializers.py      # Data serialization utilities
└── sync_engine.py      # Core synchronization engine
```

## Development Guidelines

### Code Style

- Follow PEP 8 style guidelines
- Use type hints for function parameters and return values
- Write docstrings for all public functions and classes
- Keep functions focused and under 50 lines when possible

### Architecture Patterns

- **Separation of Concerns**: UI (dashboard), business logic (sync_engine), and data (models) are separated
- **Configuration Management**: Centralized in config.py
- **Plugin System**: Extensible validation and scanning capabilities

### Testing

- Tests are located in the `tests/` directory
- Use pytest for testing
- Write unit tests for new features
- Aim for high test coverage on core logic

### Dependencies

- **Required**: click, rich, textual, tomli (Python <3.12), tomli-w
- **Optional (probe)**: github-copilot-sdk, mcp

## Common Tasks

### Adding New Agent Support

1. Update models in `models.py`
2. Add scanning logic in `scanner.py`
3. Implement validation in `plugin_validator.py`
4. Add sync logic to `sync_engine.py`

### Extending the Dashboard

1. Modify `dashboard.py` using Textual widgets
2. Update console output in `console.py` for CLI output
3. Add formatting as needed in `formatters/`

### Configuration Changes

1. Update config schema in `config.py`
2. Handle migration if needed
3. Update documentation

## Important Constraints

- **Python Version**: Must support Python 3.11+
- **Cross-Platform**: Code should work on Windows, macOS, and Linux
- **Terminal UI**: Must work in standard terminal environments
- **No External Services**: Avoid requiring external API calls unless optional

## Error Handling

- Use appropriate exception types
- Provide clear error messages for users
- Log errors appropriately for debugging
- Graceful degradation when optional features are unavailable

## Documentation

- Keep README.md up to date with new features
- Update CONTRIBUTING.md for new development workflows
- Document breaking changes clearly
- Provide examples for new features

## Security

- Never commit API keys or tokens
- Use environment variables for sensitive data
- Validate all user input
- Follow security best practices for file operations
