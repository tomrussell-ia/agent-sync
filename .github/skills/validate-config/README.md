# Validate Config Skill

## Purpose

Validate agent configuration files for syntax, schema compliance, and best practices.

## Triggers

This skill activates when you use phrases like:
- "validate config"
- "check configuration"
- "validate agent config"
- "lint config files"
- "verify config"

## Usage Examples

### Validate all configs
```
@copilot validate config
```

### Check MCP configuration
```
@copilot validate mcp config
```

### Validate specific file
```
@copilot validate .github/agents/code-reviewer/agent.json
```

## What It Does

1. **Discovers config files** - Scans workspace for agent configurations
2. **Parses syntax** - Validates JSON/YAML/TOML syntax
3. **Checks schema** - Verifies required fields and types
4. **Validates references** - Ensures referenced files exist
5. **Security scan** - Looks for exposed secrets or tokens
6. **Reports findings** - Provides detailed error/warning report

## Validated Config Types

### MCP Configuration
- File: `.vscode/mcp.json`
- Checks: server definitions, command/url presence, env vars

### Copilot Instructions
- File: `.github/copilot-instructions.md`
- Checks: file exists, contains guidelines, no secrets

### Agent Definitions
- Files: `.github/agents/*/agent.json`
- Checks: valid JSON, required fields, capabilities array

### Skills
- Files: `.github/skills/*/skill.json`
- Checks: valid JSON, triggers defined, steps present

## Output Format

### All Valid
```
✓ All configs valid
12 config files validated successfully

Validated:
  - .vscode/mcp.json
  - .github/copilot-instructions.md
  - .github/agents/code-reviewer/agent.json
  - .github/agents/doc-writer/agent.json
  ...
```

### Errors Found
```
✗ Validation errors found

Errors:
  📄 .vscode/mcp.json
  ❌ ERROR: Missing required field "command" in server "github"
  💡 Add command or url field to server definition

  📄 .github/agents/test-agent/agent.json
  ⚠️  WARNING: Referenced file "missing.md" does not exist
  💡 Create the file or update the reference
```

## Severity Levels

- **ERROR** ❌ - Must be fixed, config will not work
- **WARNING** ⚠️ - Should be fixed, may cause issues
- **INFO** ℹ️ - Optional improvement suggestion

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Syntax error | Invalid JSON/YAML | Use linter to fix syntax |
| Missing field | Required field not present | Add required fields |
| Broken reference | File doesn't exist | Update path or create file |
| Exposed secret | API key in config | Move to environment variable |

## Requirements

- Python 3.11+
- Valid JSON/YAML/TOML syntax
