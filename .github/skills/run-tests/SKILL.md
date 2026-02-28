---
name: run-tests
description: Run pytest tests and interpret results for Agent Sync
---

# Run Tests Skill

This skill runs pytest tests and provides actionable feedback on results.

## Usage Steps

1. **Verify pytest installed** - Check pytest is available
2. **Run tests** - Execute pytest with specified options
3. **Interpret results** - Parse pass/fail status, identify failures
4. **Provide summary** - Actionable next steps for failures

## Running Tests

### All tests
```bash
uv run pytest
```

### With coverage
```bash
uv run pytest --cov=agent_sync --cov-report=term
```

### Specific test file
```bash
uv run pytest tests/test_scanner.py -v
```

### Specific test pattern
```bash
uv run pytest -k "test_mcp"
```

## Interpreting Results

### Success Output
```
✓ All tests passed
77 tests passed in 0.43s
Coverage: 85%
```

### Failure Output
```
✗ Tests failed

Failed tests:
- test_scanner.py::test_missing_file
  Error: FileNotFoundError

Next steps:
1. Check if test expects file that doesn't exist
2. Review test fixtures
3. Verify test data setup
```

## Common Test Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Import error | Missing dependency | Run `uv sync` |
| Fixture not found | Missing conftest.py | Check fixture definition |
| File not found | Test data missing | Create fixture files |
| Assertion failed | Logic change | Update test or fix code |
