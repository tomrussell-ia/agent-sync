---
name: generate-template
description: Generate configuration templates for agents, skills, and MCP servers
---

# Generate Template Skill

This skill scaffolds configuration files for agents, skills, and other agent configs.

## Template Types

### 1. Agent Template (`.agent.md`)
Creates a custom agent definition in `.github/agents/`

**Includes:**
- YAML frontmatter (name, description)
- Instructions section
- Guidelines
- Boundaries

**Use when:** Creating a specialized AI agent for your project

### 2. Skill Template (`SKILL.md`)  
Creates a reusable skill in `.github/skills/{name}/`

**Includes:**
- YAML frontmatter (name, description)
- Usage instructions
- Examples
- Common issues

**Use when:** Creating a reusable skill for common tasks

### 3. MCP Server Config
Adds MCP server to `.vscode/mcp.json`

**Includes:**
- Server name and command
- Environment variables
- Arguments

**Use when:** Adding a new MCP server

## Usage Steps

1. **Validate inputs** - Check template type and name
2. **Load template** - Get base structure
3. **Customize** - Fill in specific details
4. **Generate files** - Create config file(s)
5. **Validate** - Check generated config is valid

## Examples

### Generate agent template
```bash
# Creates .github/agents/my-agent.agent.md
agent-sync generate agent my-agent
```

### Generate skill template
```bash
# Creates .github/skills/my-skill/SKILL.md
agent-sync generate skill my-skill
```

### Add MCP server
```bash
# Adds to .vscode/mcp.json
agent-sync generate mcp-server filesystem
```

## After Generation

1. Edit generated file to add specific details
2. Validate configuration with `agent-sync check`
3. Test agent/skill activation
4. Document usage in README if needed
