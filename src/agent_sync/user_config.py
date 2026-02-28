"""User configuration loader for agent-sync.

Reads optional ~/.agent-sync.toml for user preferences and path overrides.
Falls back to hardcoded defaults if config file doesn't exist.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 12):
    import tomllib
else:
    try:
        import tomllib  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[import-untyped, no-redef]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USER_CONFIG_PATH = Path.home() / ".agent-sync.toml"


# ---------------------------------------------------------------------------
# Configuration dataclasses
# ---------------------------------------------------------------------------


@dataclass
class PathsConfig:
    """Path overrides for tool directories."""
    
    agents_dir: Path | None = None
    copilot_dir: Path | None = None
    claude_dir: Path | None = None
    codex_dir: Path | None = None
    ia_skills_hub: Path | None = None


@dataclass
class ToolsConfig:
    """Tool-specific settings."""
    
    enabled: list[str] = field(default_factory=lambda: ["copilot", "claude", "codex"])
    ignore_extra_servers: bool = False


@dataclass
class McpConfig:
    """MCP server settings."""
    
    ignore_servers: list[str] = field(default_factory=list)
    force_user_scope: bool = False


@dataclass
class ScanConfig:
    """Scan behavior settings."""
    
    product_dirs: list[Path] = field(default_factory=list)
    skip_validation: bool = False


@dataclass
class OutputConfig:
    """Output preferences."""
    
    format: str = "auto"  # auto, json, table, dashboard
    verbosity: str = "normal"  # quiet, normal, verbose
    color: str = "auto"  # auto, always, never


@dataclass
class UserConfig:
    """Complete user configuration."""
    
    paths: PathsConfig = field(default_factory=PathsConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    mcp: McpConfig = field(default_factory=McpConfig)
    scan: ScanConfig = field(default_factory=ScanConfig)
    output: OutputConfig = field(default_factory=OutputConfig)


def _expand_path(path_str: str) -> Path:
    """Expand ~ and environment variables in path string."""
    return Path(path_str).expanduser().resolve()


def _parse_paths_section(data: dict[str, Any]) -> PathsConfig:
    """Parse [paths] section from TOML."""
    paths = PathsConfig()
    if "agents_dir" in data:
        paths.agents_dir = _expand_path(data["agents_dir"])
    if "copilot_dir" in data:
        paths.copilot_dir = _expand_path(data["copilot_dir"])
    if "claude_dir" in data:
        paths.claude_dir = _expand_path(data["claude_dir"])
    if "codex_dir" in data:
        paths.codex_dir = _expand_path(data["codex_dir"])
    if "ia_skills_hub" in data:
        paths.ia_skills_hub = _expand_path(data["ia_skills_hub"])
    return paths


def _parse_tools_section(data: dict[str, Any]) -> ToolsConfig:
    """Parse [tools] section from TOML."""
    tools = ToolsConfig()
    if "enabled" in data:
        tools.enabled = data["enabled"]
    if "ignore_extra_servers" in data:
        tools.ignore_extra_servers = data["ignore_extra_servers"]
    return tools


def _parse_mcp_section(data: dict[str, Any]) -> McpConfig:
    """Parse [mcp] section from TOML."""
    mcp = McpConfig()
    if "ignore_servers" in data:
        mcp.ignore_servers = data["ignore_servers"]
    if "force_user_scope" in data:
        mcp.force_user_scope = data["force_user_scope"]
    return mcp


def _parse_scan_section(data: dict[str, Any]) -> ScanConfig:
    """Parse [scan] section from TOML."""
    scan = ScanConfig()
    if "product_dirs" in data:
        scan.product_dirs = [_expand_path(p) for p in data["product_dirs"]]
    if "skip_validation" in data:
        scan.skip_validation = data["skip_validation"]
    return scan


def _parse_output_section(data: dict[str, Any]) -> OutputConfig:
    """Parse [output] section from TOML."""
    output = OutputConfig()
    if "format" in data:
        output.format = data["format"]
    if "verbosity" in data:
        output.verbosity = data["verbosity"]
    if "color" in data:
        output.color = data["color"]
    return output


def load_user_config(config_path: Path | None = None) -> UserConfig:
    """Load user configuration from TOML file.
    
    Args:
        config_path: Optional path to config file. Defaults to ~/.agent-sync.toml
        
    Returns:
        UserConfig with values from file, or defaults if file doesn't exist
        
    Raises:
        ValueError: If config file has syntax errors or invalid values
    """
    if config_path is None:
        config_path = Path.home() / ".agent-sync.toml"
    
    # If config doesn't exist, return defaults
    if not config_path.exists():
        return UserConfig()
    
    # Parse TOML
    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        raise ValueError(f"Failed to parse config file {config_path}: {e}") from e
    
    # Build config from sections
    config = UserConfig()
    
    if "paths" in data:
        config.paths = _parse_paths_section(data["paths"])
    
    if "tools" in data:
        config.tools = _parse_tools_section(data["tools"])
    
    if "mcp" in data:
        config.mcp = _parse_mcp_section(data["mcp"])
    
    if "scan" in data:
        config.scan = _parse_scan_section(data["scan"])
    
    if "output" in data:
        config.output = _parse_output_section(data["output"])
    
    return config


def validate_user_config(config: UserConfig) -> list[str]:
    """Validate user config and return list of warnings/errors.
    
    Args:
        config: UserConfig to validate
        
    Returns:
        List of warning/error messages (empty if valid)
    """
    warnings: list[str] = []
    
    # Validate paths exist
    if config.paths.agents_dir and not config.paths.agents_dir.exists():
        warnings.append(f"agents_dir does not exist: {config.paths.agents_dir}")
    
    if config.paths.copilot_dir and not config.paths.copilot_dir.exists():
        warnings.append(f"copilot_dir does not exist: {config.paths.copilot_dir}")
    
    if config.paths.claude_dir and not config.paths.claude_dir.exists():
        warnings.append(f"claude_dir does not exist: {config.paths.claude_dir}")
    
    if config.paths.codex_dir and not config.paths.codex_dir.exists():
        warnings.append(f"codex_dir does not exist: {config.paths.codex_dir}")
    
    if config.paths.ia_skills_hub and not config.paths.ia_skills_hub.exists():
        warnings.append(f"ia_skills_hub does not exist: {config.paths.ia_skills_hub}")
    
    # Validate tool names
    valid_tools = {"copilot", "claude", "codex"}
    for tool in config.tools.enabled:
        if tool not in valid_tools:
            warnings.append(f"Unknown tool in tools.enabled: {tool} (valid: {valid_tools})")
    
    # Validate output format
    valid_formats = {"auto", "json", "table", "dashboard"}
    if config.output.format not in valid_formats:
        warnings.append(f"Invalid output.format: {config.output.format} (valid: {valid_formats})")
    
    # Validate verbosity
    valid_verbosity = {"quiet", "normal", "verbose"}
    if config.output.verbosity not in valid_verbosity:
        warnings.append(f"Invalid output.verbosity: {config.output.verbosity} (valid: {valid_verbosity})")
    
    # Validate color
    valid_color = {"auto", "always", "never"}
    if config.output.color not in valid_color:
        warnings.append(f"Invalid output.color: {config.output.color} (valid: {valid_color})")
    
    return warnings


# Global config instance (loaded on first access)
_user_config: UserConfig | None = None


def get_user_config(reload: bool = False) -> UserConfig:
    """Get the global user config instance.
    
    Args:
        reload: If True, reload config from disk
        
    Returns:
        Global UserConfig instance
    """
    global _user_config
    if _user_config is None or reload:
        _user_config = load_user_config()
    return _user_config
