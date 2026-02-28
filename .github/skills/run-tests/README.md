# Run Tests Skill

## Purpose

Automatically run pytest tests for Agent Sync and interpret the results, providing actionable feedback.

## Triggers

This skill activates when you use phrases like:
- "run tests"
- "execute tests"
- "test the code"
- "run pytest"
- "check if tests pass"

## Usage Examples

### Run all tests
```
@copilot run tests
```

### Run with coverage
```
@copilot run tests with coverage
```

### Run specific test file
```
@copilot run tests in tests/test_scanner.py
```

### Run tests matching a pattern
```
@copilot run tests matching "sync"
```

## What It Does

1. **Verifies pytest is installed** - Checks that pytest is available
2. **Executes tests** - Runs pytest with appropriate options
3. **Interprets results** - Analyzes test output for pass/fail status
4. **Provides summary** - Reports results in human-readable format

## Output Format

### Success
```
✓ All tests passed
23 tests passed in 2.4 seconds
Coverage: 87%
```

### Failure
```
✗ Tests failed
Failed tests:
  - test_scanner_discovers_configs: FileNotFoundError
  - test_sync_engine_applies_fix: AssertionError

Next steps:
  - Fix test_scanner_discovers_configs by checking file path
  - Review test_sync_engine_applies_fix assertion
```

## Options

- `-v` - Verbose output
- `--cov` - Coverage report
- `-k PATTERN` - Run tests matching pattern
- `-x` - Stop on first failure
- `--lf` - Run last failed tests

## Requirements

- pytest installed (`pip install pytest`)
- Agent Sync installed (`pip install -e .`)
