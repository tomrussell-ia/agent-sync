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

```bash
# Install dependencies
pip install -e ".[probe]"

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
