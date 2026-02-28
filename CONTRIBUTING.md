# Contributing to Agent Sync

Thank you for your interest in contributing to Agent Sync! This document provides guidelines and instructions for contributing.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/agent-sync.git`
3. Create a new branch: `git checkout -b feature/your-feature-name`
4. Make your changes
5. Test your changes
6. Commit your changes: `git commit -m "Add your commit message"`
7. Push to your fork: `git push origin feature/your-feature-name`
8. Create a Pull Request

## Development Setup

Using uv (recommended):

```bash
# Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh  # Unix
# or
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"  # Windows

# Install all dependencies including dev tools
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install

# Run tests
uv run pytest

# Run linting
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

Using pip:

```bash
# Install dependencies
pip install -e ".[dev,probe]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest
```

## Code Style

- Follow PEP 8 style guidelines
- Use type hints where appropriate
- Write descriptive docstrings for functions and classes
- Keep functions focused and single-purpose

## Testing

- Write tests for new features
- Ensure all tests pass before submitting a PR
- Aim for good test coverage

## Pull Request Guidelines

- Provide a clear description of the changes
- Reference any related issues
- Keep PRs focused on a single feature or fix
- Ensure all CI checks pass

## Reporting Issues

When reporting issues, please include:

- A clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Python version and environment details
- Relevant error messages or logs

## Questions?

Feel free to open an issue for any questions or discussions.
