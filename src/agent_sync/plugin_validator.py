"""Validate Copilot CLI plugin directories.

Checks ``~/.copilot/installed-plugins/`` for well-formed ``plugin.json``
and ``.mcp.json`` manifests.
"""

from __future__ import annotations

import json
from pathlib import Path

from agent_sync.config import COPILOT_INSTALLED_PLUGINS
from agent_sync.models import PluginValidation


# ---------------------------------------------------------------------------
# Required / expected keys
# ---------------------------------------------------------------------------

_REQUIRED_PLUGIN_KEYS = {"name", "description", "version"}
_OPTIONAL_PLUGIN_KEYS = {
    "author",
    "keywords",
    "category",
    "agents",
    "commands",
    "skills",
    "instructions",
}


def _validate_plugin_json(path: Path) -> tuple[bool, list[str]]:
    """Validate a plugin.json file and return (valid, errors)."""
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, [f"Invalid JSON: {exc}"]
    except OSError as exc:
        return False, [f"Cannot read file: {exc}"]

    if not isinstance(data, dict):
        return False, ["Expected a JSON object at top level"]

    for key in _REQUIRED_PLUGIN_KEYS:
        if key not in data:
            errors.append(f"Missing required key: {key}")

    # Check that referenced paths actually exist
    plugin_dir = path.parent
    for field_name in ("agents", "commands", "skills"):
        val = data.get(field_name)
        if val is None:
            continue

        refs = val if isinstance(val, list) else [val]
        for ref in refs:
            if not isinstance(ref, str):
                continue
            ref_path = plugin_dir / ref
            if not ref_path.exists():
                errors.append(f"{field_name} reference not found: {ref}")

    return len(errors) == 0, errors


def _validate_mcp_json(path: Path) -> tuple[bool, list[str]]:
    """Validate a .mcp.json file and return (valid, errors)."""
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, [f"Invalid JSON: {exc}"]
    except OSError as exc:
        return False, [f"Cannot read file: {exc}"]

    if not isinstance(data, dict):
        return False, ["Expected a JSON object at top level"]

    # MCP config should have either "servers" or "mcpServers"
    servers = data.get("servers") or data.get("mcpServers")
    if not servers:
        errors.append("No 'servers' or 'mcpServers' key found")
    elif not isinstance(servers, dict):
        errors.append("'servers' should be a JSON object")
    else:
        for name, cfg in servers.items():
            if not isinstance(cfg, dict):
                errors.append(f"Server '{name}' config is not an object")
                continue
            # Must have either url or command
            if not cfg.get("url") and not cfg.get("command"):
                errors.append(f"Server '{name}' missing both 'url' and 'command'")

    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_plugins(
    plugins_dir: Path | None = None,
) -> list[PluginValidation]:
    """Scan installed plugin directories and validate manifests.

    Parameters
    ----------
    plugins_dir:
        Override path to ``installed-plugins/`` (default: ``~/.copilot/installed-plugins/``).

    Returns
    -------
    list[PluginValidation]
        One entry per plugin directory discovered.
    """
    root = plugins_dir or COPILOT_INSTALLED_PLUGINS
    results: list[PluginValidation] = []

    if not root.is_dir():
        return results

    # Walk one or two levels — plugins can be at root/plugin/ or root/source/plugin/
    seen: set[Path] = set()

    for candidate in _discover_plugin_dirs(root):
        if candidate in seen:
            continue
        seen.add(candidate)

        v = PluginValidation(
            name=candidate.name,
            path=candidate,
        )

        plugin_json = candidate / "plugin.json"
        if plugin_json.is_file():
            v.has_plugin_json = True
            valid, errs = _validate_plugin_json(plugin_json)
            v.plugin_json_valid = valid
            v.errors.extend(errs)

        mcp_json = candidate / ".mcp.json"
        if mcp_json.is_file():
            v.has_mcp_json = True
            valid, errs = _validate_mcp_json(mcp_json)
            v.mcp_json_valid = valid
            v.errors.extend(errs)

        results.append(v)

    return results


def _discover_plugin_dirs(root: Path) -> list[Path]:
    """Find directories that look like plugins (contain plugin.json or .mcp.json)."""
    results: list[Path] = []

    for path in root.rglob("plugin.json"):
        results.append(path.parent)

    for path in root.rglob(".mcp.json"):
        if path.parent not in results:
            results.append(path.parent)

    return sorted(results)
