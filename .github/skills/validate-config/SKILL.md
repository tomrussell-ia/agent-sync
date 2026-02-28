---
name: validate-config
description: Validate agent configuration files for syntax, schema compliance, and security
---

# Config Validation Skill

This skill validates agent and MCP configuration files across multiple formats.

## What It Validates

### MCP Configuration (`.vscode/mcp.json`)
- Servers object exists and valid
- Each server has command or URL
- Environment variables properly formatted
- No duplicate server names

### Copilot Instructions (`.github/copilot-instructions.md`)
- File exists and readable
- Contains project guidance
- No hardcoded secrets

### Agent Definitions (`.github/agents/*.agent.md`)
- Valid YAML frontmatter
- Required fields present (name, description)
- Referenced files exist

### Skills (`.github/skills/*/SKILL.md`)
- Valid YAML frontmatter
- Name and description present
- Markdown body follows standards

## Usage Steps

1. **Discover config files** - Scan workspace for agent configurations
2. **Parse syntax** - Validate JSON/YAML/Markdown syntax
3. **Check schema** - Verify required fields and types
4. **Validate references** - Ensure referenced files exist
5. **Security scan** - Look for exposed secrets or tokens
6. **Report findings** - Provide structured error/warning report

## Examples

```bash
# Validate all configs in current directory
agent-sync check

# Validate specific config type
agent-sync check --tool copilot

# Get JSON output for scripting
agent-sync check --json
```

## Output

### Success
```
✓ All configs valid
12 files validated successfully
```

### Errors Found
```
✗ Validation errors found

📄 .vscode/mcp.json
❌ ERROR: Missing required field "command"
💡 Add command or url to server definition
```

## Common Issues

| Issue | Fix |
|-------|-----|
| Syntax error | Use JSON/YAML linter |
| Missing field | Add required fields per schema |
| Broken reference | Update path or create missing file |
| Exposed secret | Move to environment variable |
