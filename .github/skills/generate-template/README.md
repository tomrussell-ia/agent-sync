# Generate Template Skill

## Purpose

Quickly scaffold configuration files for agents, skills, MCP servers, and other agent configs.

## Triggers

This skill activates when you use phrases like:
- "generate template"
- "create config template"
- "new agent config"
- "scaffold config"
- "generate agent template"

## Usage Examples

### Generate agent template
```
@copilot generate agent template for logging-analyzer
```

### Create skill template
```
@copilot create skill template for format-code
```

### Add MCP server config
```
@copilot generate mcp-server template for filesystem
```

### Generate Copilot instructions
```
@copilot create copilot-instructions template
```

## Template Types

### 1. Agent Template
**Path**: `.github/agents/{name}/agent.json`

Creates a complete agent definition with:
- Name and description
- Capabilities list
- Context files and scope
- Instructions and boundaries
- Quality checklist

**Use when**: Creating a new specialized AI agent for your project

### 2. Skill Template
**Path**: `.github/skills/{name}/`

Creates:
- `skill.json` - Skill definition
- `README.md` - Usage documentation

Includes:
- Trigger phrases
- Input definitions
- Execution steps
- Examples and output format

**Use when**: Creating a reusable skill for common tasks

### 3. MCP Server Template
**Path**: `.vscode/mcp.json` (addition)

Adds MCP server configuration with:
- Server name
- Command/URL connection
- Environment variables
- Arguments

**Use when**: Adding a new MCP server to your config

### 4. Copilot Instructions Template
**Path**: `.github/copilot-instructions.md`

Creates structured instructions with sections:
- Project Overview
- Technology Stack
- Code Organization
- Development Guidelines
- And more...

**Use when**: Setting up Copilot instructions for the first time

### 5. Pre-commit Config Template
**Path**: `.pre-commit-config.yaml`

Creates pre-commit configuration with common hooks

**Use when**: Setting up pre-commit hooks

## What It Does

1. **Validates inputs** - Checks template type and name
2. **Loads template** - Gets base structure for type
3. **Customizes** - Optionally fills in details interactively
4. **Generates files** - Creates config file(s)
5. **Validates** - Ensures generated config is correct
6. **Guides next steps** - Tells you what to do next

## Output Format

```
✓ Template generated

Files created:
  - .github/agents/logging-analyzer/agent.json

Next steps:
  1. Edit agent.json to add specific capabilities
  2. Define instructions and boundaries
  3. Add context files relevant to agent's purpose
  4. Test agent with example scenarios
```

## Interactive Customization

When generating with customization, you'll be prompted:

**For agents**:
- What is the agent's primary purpose?
- What capabilities should it have?
- What files should be in its context?
- Any specific boundaries or constraints?

**For skills**:
- What trigger phrases should activate this skill?
- What inputs does the skill need?
- What are the execution steps?
- Can you provide usage examples?

## After Generation

The skill automatically:
- Validates the generated config
- Checks syntax and required fields
- Reports any issues found
- Provides guidance on next steps

## Requirements

- Write access to repository
- Understanding of config structure (or use interactive mode)
