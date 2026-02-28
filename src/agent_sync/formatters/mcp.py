"""MCP configuration format translators.

Reads canonical mcp.json and generates tool-specific config files.
"""

from __future__ import annotations

import json
import sys


if sys.version_info >= (3, 12):
    import tomllib
else:
    try:
        import tomllib  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[import-untyped, no-redef]

import tomli_w

from agent_sync.config import (
    CLAUDE_DESKTOP_CONFIG_JSON,
    CLAUDE_SETTINGS_JSON,
    CODEX_CONFIG_TOML,
    COPILOT_MCP_CONFIG_JSON,
)
from agent_sync.models import McpServer, ToolName


# ---------------------------------------------------------------------------
# Copilot format
# ---------------------------------------------------------------------------


def generate_copilot_mcp(servers: list[McpServer]) -> dict:
    """Build the Copilot mcp-config.json structure from canonical servers."""
    result: dict = {"mcpServers": {}}
    for srv in servers:
        if ToolName.COPILOT not in srv.enabled_for:
            continue
        entry: dict = {"tools": srv.tools, "type": srv.server_type.value}
        if srv.url:
            entry["url"] = srv.url
        if srv.headers:
            entry["headers"] = srv.headers
        if srv.command:
            entry["command"] = srv.command
        if srv.args:
            entry["args"] = srv.args
        result["mcpServers"][srv.name] = entry
    return result


def write_copilot_mcp(servers: list[McpServer], *, dry_run: bool = False) -> str:
    """Write Copilot MCP config, merging with existing servers. Returns description of what was/would be done."""
    target = COPILOT_MCP_CONFIG_JSON
    
    # Read existing config to preserve servers not in canonical
    existing_data = {"mcpServers": {}}
    if target.exists():
        try:
            existing_data = json.loads(target.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            existing_data = {"mcpServers": {}}
    
    # Generate new servers from canonical
    new_data = generate_copilot_mcp(servers)
    
    # Merge: update existing with new servers (preserves servers not in canonical)
    merged_data = existing_data.copy()
    if "mcpServers" not in merged_data:
        merged_data["mcpServers"] = {}
    merged_data["mcpServers"].update(new_data["mcpServers"])
    
    new_text = json.dumps(merged_data, indent=2) + "\n"

    if dry_run:
        return f"Would merge {len(new_data['mcpServers'])} servers into {target} (preserving {len(existing_data.get('mcpServers', {}))} existing)"

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(new_text, encoding="utf-8")
    return f"Merged {len(new_data['mcpServers'])} servers into {target} (total: {len(merged_data['mcpServers'])})"


# ---------------------------------------------------------------------------
# Codex format
# ---------------------------------------------------------------------------


def generate_codex_mcp_sections(servers: list[McpServer]) -> dict[str, dict]:
    """Build TOML section dicts for each MCP server enabled for Codex."""
    sections: dict[str, dict] = {}
    for srv in servers:
        if ToolName.CODEX not in srv.enabled_for:
            continue
        entry: dict = {}
        if srv.url:
            entry["url"] = srv.url
            entry["enabled"] = srv.enabled
        if srv.command:
            entry["command"] = srv.command
        if srv.args:
            entry["args"] = srv.args
        sections[srv.name] = entry
    return sections


def write_codex_mcp(servers: list[McpServer], *, dry_run: bool = False) -> str:
    """Patch MCP sections into Codex config.toml, merging with existing servers."""
    sections = generate_codex_mcp_sections(servers)
    target = CODEX_CONFIG_TOML

    if not target.exists():
        return f"Skipped: {target} does not exist"

    # Parse existing TOML to preserve non-MCP settings
    existing = tomllib.loads(target.read_text(encoding="utf-8"))

    # Merge mcp_servers (preserve existing, update/add from canonical)
    if "mcp_servers" not in existing:
        existing["mcp_servers"] = {}
    existing["mcp_servers"].update(sections)

    new_text = tomli_w.dumps(existing)

    if dry_run:
        return f"Would merge {len(sections)} servers into {target} (total: {len(existing['mcp_servers'])})"

    target.write_text(new_text, encoding="utf-8")
    return f"Wrote {len(sections)} MCP servers to {target}"


# ---------------------------------------------------------------------------
# Claude format
# ---------------------------------------------------------------------------


def generate_claude_mcp_permissions(servers: list[McpServer]) -> list[str]:
    """Generate Claude permission allow-list entries for enabled MCP servers.

    Claude stores MCP servers in the permissions.allow array in settings.json
    using the pattern: mcp__<server_name>__*
    """
    perms: list[str] = []
    for srv in servers:
        if ToolName.CLAUDE not in srv.enabled_for:
            continue
        # Claude uses mcp__<name>__* pattern
        sanitized = srv.name.lower().replace("-", "_").replace(" ", "_")
        perms.append(f"mcp__{sanitized}__*")
    return perms


def write_claude_mcp(servers: list[McpServer], *, dry_run: bool = False) -> str:
    """Write Claude MCP config to both settings.json and Desktop config.

    Updates:
    1. ~/.claude/settings.json - permissions.allow with mcp__<name>__* entries
    2. ~/AppData/Roaming/Claude/claude_desktop_config.json - full server definitions

    Returns description of what was/would be done.
    """
    perms = generate_claude_mcp_permissions(servers)
    
    # Update settings.json (permissions)
    settings_target = CLAUDE_SETTINGS_JSON
    settings_msg = ""
    
    if settings_target.exists():
        try:
            existing = json.loads(settings_target.read_text(encoding="utf-8"))
            
            # Get current permissions, preserving structure
            if "permissions" not in existing:
                existing["permissions"] = {}
            if "allow" not in existing["permissions"]:
                existing["permissions"]["allow"] = []
            
            # Filter out old MCP permissions
            old_allow = existing["permissions"]["allow"]
            non_mcp_perms = [p for p in old_allow if not (isinstance(p, str) and p.startswith("mcp__"))]
            
            # Add new MCP permissions
            existing["permissions"]["allow"] = non_mcp_perms + perms
            
            new_text = json.dumps(existing, indent=2) + "\n"
            
            if not dry_run:
                settings_target.write_text(new_text, encoding="utf-8")
            settings_msg = f"permissions: {len(perms)} entries"
        except (json.JSONDecodeError, OSError) as e:
            settings_msg = f"Error: {e}"
    else:
        settings_msg = "settings.json not found"
    
    # Update claude_desktop_config.json (full server definitions)
    desktop_target = CLAUDE_DESKTOP_CONFIG_JSON
    desktop_msg = ""
    
    if desktop_target.exists():
        try:
            existing = json.loads(desktop_target.read_text(encoding="utf-8"))
            
            # Ensure mcpServers exists
            if "mcpServers" not in existing:
                existing["mcpServers"] = {}
            
            # Merge new servers with existing
            for srv in servers:
                if ToolName.CLAUDE not in srv.enabled_for:
                    continue
                
                entry: dict = {}
                if srv.url:
                    entry["type"] = "http"
                    entry["url"] = srv.url
                    if srv.headers:
                        entry["headers"] = srv.headers
                if srv.command:
                    entry["command"] = srv.command
                if srv.args:
                    entry["args"] = srv.args
                
                existing["mcpServers"][srv.name] = entry
            
            new_text = json.dumps(existing, indent=2) + "\n"
            
            if not dry_run:
                desktop_target.write_text(new_text, encoding="utf-8")
            desktop_msg = f"desktop: {len([s for s in servers if ToolName.CLAUDE in s.enabled_for])} servers"
        except (json.JSONDecodeError, OSError) as e:
            desktop_msg = f"Error: {e}"
    else:
        desktop_msg = "desktop config not found"
    
    action = "Would write" if dry_run else "Wrote"
    return f"{action} Claude MCP ({settings_msg}, {desktop_msg})"
