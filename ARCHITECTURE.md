# Architecture Guide

## Overview

Agent Sync is a Python-based CLI tool that provides a unified interface for managing AI agent configurations across multiple platforms (GitHub Copilot CLI, Claude, Codex, and VS Code). The architecture follows a modular design with clear separation of concerns between scanning, synchronization, presentation, and configuration management.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI Layer                           │
│                    (cli.py + Click)                         │
└──────────────┬──────────────────────────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
┌──────▼──────┐  ┌──────▼──────────┐
│  Dashboard  │  │  Console Check  │
│  (Textual)  │  │     (Rich)      │
└──────┬──────┘  └──────┬──────────┘
       │                │
       └────────┬───────┘
                │
        ┌───────▼────────┐
        │  Sync Engine   │
        │ (Orchestrator) │
        └───┬────────┬───┘
            │        │
    ┌───────▼──┐  ┌─▼──────────┐
    │ Scanner  │  │ Formatters │
    │          │  │            │
    └────┬─────┘  └─────┬──────┘
         │              │
    ┌────▼────────┐  ┌──▼──────────┐
    │   Models    │  │ Serializers │
    │  (Domain)   │  │  (I/O)      │
    └─────────────┘  └─────────────┘
```

## Core Components

### 1. CLI Layer (`cli.py`)

**Responsibility**: Entry point and command routing

**Key Features**:
- Click-based command structure
- Commands: `dashboard`, `check`, `fix`, `probe`
- Global flags: `--json`, `--quiet`, `--tool`, `--type`
- Error handling and exit codes

**Design Decision**: Used Click for its decorator-based API and automatic help generation. Provides both interactive (dashboard) and non-interactive (check/fix) modes for different use cases.

### 2. Scanner (`scanner.py`)

**Responsibility**: Discover and parse agent configurations from filesystem

**Process**:
1. Locate config directories (`.copilot/`, `.claude/`, `.vscode/`, etc.)
2. Parse configuration files (JSON, TOML, YAML)
3. Extract MCP servers, skills, commands, prompts
4. Build canonical state representation

**Key Functions**:
- `scan_workspace()` - Main entry point
- `find_config_files()` - Filesystem traversal
- `parse_config()` - Format-specific parsing

**Design Decision**: Scanner is read-only and stateless. It builds an immutable snapshot of the current state, making it safe to run repeatedly and enabling diff-based synchronization.

### 3. Sync Engine (`sync_engine.py`)

**Responsibility**: Compare configurations and orchestrate synchronization

**Core Logic**:
```
CanonicalState = Scanner.scan()
ToolConfigs = {tool: load_config(tool) for tool in TOOLS}

For each tool:
    Diff = compare(CanonicalState, ToolConfigs[tool])
    if Diff.has_changes:
        SyncReport.add_item(Diff)
        if fix_mode:
            apply_fix(Diff)
```

**Fix Operations**:
- Generate missing config files
- Update MCP server definitions
- Sync skills and commands
- Create/update symlinks

**Design Decision**: Sync engine is the only component that modifies files. It operates in two modes: report-only (default) and fix mode (explicit). This prevents accidental changes and makes the tool safe for CI/CD use.

### 4. Models (`models.py`)

**Responsibility**: Type-safe domain objects

**Key Models**:
- `CanonicalState` - Source of truth for all configs
- `SyncItem` - Individual sync operation
- `SyncReport` - Collection of sync items with metadata
- `FixAction` - Concrete file operation to apply

**Design Decision**: Uses dataclasses for simplicity and runtime type checking. Models are immutable where possible to prevent accidental state mutation.

### 5. Dashboard (`dashboard.py`)

**Responsibility**: Interactive terminal UI

**Technology**: Textual (modern TUI framework)

**Features**:
- Live config status display
- Interactive sync operations
- Filterable views (by tool, by status)
- Rich formatting with colors and symbols

**Design Decision**: Separate UI layer allows for multiple presentation modes. Dashboard imports sync engine but not vice versa, maintaining clean separation.

### 6. Console (`console.py`)

**Responsibility**: Non-interactive rich console output

**Technology**: Rich library

**Use Cases**:
- CI/CD reporting
- Quick status checks
- JSON output for scripting
- Quiet mode for exit codes only

### 7. Formatters (`formatters/`)

**Responsibility**: Tool-specific config generation

**Structure**:
```
formatters/
├── mcp.py       # MCP server configurations
├── skills.py    # Skills/agents
├── commands.py  # Custom commands/prompts
└── vscode.py    # VS Code settings
```

**Design Decision**: Each tool has its own formatter module to isolate platform-specific logic. Formatters are pure functions that take canonical state and return tool-specific config.

### 8. Serializers (`serializers.py`)

**Responsibility**: Read/write config files in various formats

**Supported Formats**:
- JSON - Most tools
- TOML - pyproject.toml, some configs
- YAML - Some tools

**Design Decision**: Centralized serialization prevents format-specific bugs from spreading. Uses tomli/tomli-w for TOML to support Python 3.11+.

### 9. Validator (`plugin_validator.py`)

**Responsibility**: Validate agent plugins and configurations

**Checks**:
- Schema validation
- Required fields presence
- Type correctness
- Cross-references

### 10. Prober (`prober.py`)

**Responsibility**: Runtime validation of MCP servers and tools

**Features**:
- Test MCP server connectivity
- Verify tool capabilities
- Check API availability

**Design Decision**: Optional feature requiring `probe` dependencies. Isolated from core functionality to keep base installation lightweight.

## Data Flow

### Scan → Sync → Fix Flow

```
1. User runs command
   ↓
2. Scanner discovers configs
   ↓
3. Build CanonicalState (source of truth)
   ↓
4. For each tool:
   - Load current config
   - Compare to canonical
   - Generate SyncItem if drift
   ↓
5. Build SyncReport
   ↓
6. Present via Dashboard/Console
   ↓
7. If fix mode:
   - Apply FixActions
   - Update files
   - Report results
```

### Configuration Priority

1. **Canonical State** - Built from `.copilot/` and explicit configs
2. **Tool Configs** - Individual tool configurations
3. **Sync** - Tools are updated to match canonical

**Design Decision**: Unidirectional flow from canonical to tools prevents sync conflicts. There's always a single source of truth.

## Extension Points

### Adding New Tool Support

1. **Scanner**: Add new config location and parser
2. **Models**: Extend `CanonicalState` if needed
3. **Formatter**: Create `formatters/newtool.py`
4. **Sync Engine**: Add tool to comparison logic
5. **Dashboard**: Update UI to show new tool

### Adding New Config Type

1. **Models**: Define new domain object
2. **Scanner**: Add parser for new type
3. **Formatters**: Add generation logic
4. **Serializers**: Support new file format if needed

### Custom Validation Rules

1. **Validator**: Add new check functions
2. **Models**: Define validation results
3. **Console**: Display validation errors

## Design Principles

### 1. Separation of Concerns
Each module has a single, well-defined responsibility. UI doesn't know about serialization; scanner doesn't modify files.

### 2. Immutable State
Models are immutable by default. State changes flow unidirectionally through the system.

### 3. Explicit Operations
Destructive operations (fix mode) require explicit flags. Default behavior is always safe.

### 4. Tool Independence
Core functionality doesn't depend on optional features (probe, specific tools). Base tool works with minimal dependencies.

### 5. Testability
Pure functions and dependency injection make testing straightforward. Scanner can work with mock filesystems; formatters with mock state.

## Performance Considerations

- **Lazy Loading**: Optional dependencies loaded only when needed
- **Caching**: Scanner results cached within a session
- **Minimal I/O**: Only read/write files when necessary
- **Concurrent Scanning**: (Future) Parallel config discovery

## Security

- **No Secrets in Logs**: API keys and tokens never logged
- **Path Validation**: All file operations validate paths
- **Read-Only by Default**: Fix mode is opt-in
- **Sandboxed Operations**: File operations limited to workspace

## Error Handling

- **Validation Errors**: Caught early, user-friendly messages
- **File I/O Errors**: Graceful degradation, continue on error
- **Network Errors**: Only affect probe feature
- **Configuration Errors**: Report and skip invalid configs

## Testing Strategy

- **Unit Tests**: Pure functions (formatters, validators)
- **Integration Tests**: Scanner + filesystem
- **UI Tests**: Dashboard interactions
- **End-to-End**: Full scan → sync → fix flow

## Future Architecture Considerations

### Potential Enhancements

1. **Plugin System**: Allow external plugins to add tool support
2. **Config Profiles**: Multiple canonical states for different contexts
3. **Diff Visualization**: Show detailed config differences
4. **Undo/Rollback**: Revert sync operations
5. **Remote Configs**: Sync with cloud-stored configurations
6. **Watch Mode**: Continuous sync with file watching

### Known Limitations

1. **Single Workspace**: Currently assumes single workspace directory
2. **No Conflict Resolution**: Overwrites tool configs without merge
3. **Limited Undo**: No built-in rollback mechanism
4. **Sync Direction**: Always canonical → tools, not bidirectional

## Glossary

- **Canonical State**: The authoritative configuration that tools should match
- **Sync Item**: A detected difference between canonical and tool config
- **Fix Action**: A concrete file operation to resolve a sync item
- **MCP**: Model Context Protocol - standard for AI tool integration
- **Tool**: External AI platform (Copilot, Claude, Codex, VS Code)
