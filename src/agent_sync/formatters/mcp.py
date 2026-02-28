"""MCP configuration format translators.

Reads canonical mcp.json and generates tool-specific config files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if sys.version_info >= (3, 12):
    import tomllib
else:
    try:
        import tomllib  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[import-untyped, no-redef]

import tomli_w

from agent_sync.config import (
    CLAUDE_SETTINGS_JSON,
    CODEX_CONFIG_TOML,
    COPILOT_MCP_CONFIG_JSON,
)
from agent_sync.models import McpServer, McpServerType, ToolName


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
    """Write Copilot MCP config. Returns description of what was/would be done."""
    data = generate_copilot_mcp(servers)
    target = COPILOT_MCP_CONFIG_JSON
    new_text = json.dumps(data, indent=2) + "\n"

    if dry_run:
        return f"Would write {len(data['mcpServers'])} servers to {target}"

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(new_text, encoding="utf-8")
    return f"Wrote {len(data['mcpServers'])} servers to {target}"


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
    """Patch MCP sections into Codex config.toml, preserving other settings."""
    sections = generate_codex_mcp_sections(servers)
    target = CODEX_CONFIG_TOML

    if not target.exists():
        return f"Skipped: {target} does not exist"

    # Parse existing TOML to preserve non-MCP settings
    existing = tomllib.loads(target.read_text(encoding="utf-8"))

    # Replace mcp_servers
    existing["mcp_servers"] = {}
    for name, entry in sections.items():
        existing["mcp_servers"][name] = entry

    new_text = tomli_w.dumps(existing)

    if dry_run:
        return f"Would write {len(sections)} MCP servers to {target}"

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
    """Write Claude MCP permissions to settings.json.
    
    Claude Code stores MCP server permissions in the permissions.allow array
    rather than as full server definitions. This function updates that array
    while preserving other permissions and settings.
    
    Returns description of what was/would be done.
    """
    perms = generate_claude_mcp_permissions(servers)
    target = CLAUDE_SETTINGS_JSON

    if not target.exists():
        return f"Skipped: {target} does not exist"

    # Read existing settings
    try:
        existing = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return f"Error reading {target}: {e}"

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

    if dry_run:
        return f"Would write {len(perms)} MCP permissions to {target}"

    target.write_text(new_text, encoding="utf-8")
    return f"Wrote {len(perms)} MCP permissions to {target}"
