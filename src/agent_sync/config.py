"""Path constants and tool definitions for agent-sync.

All paths resolve relative to the user's home directory, with optional
overrides from ~/.agent-sync.toml user config.
"""

from __future__ import annotations

from pathlib import Path


def _get_config():
    """Lazy import to avoid circular dependencies."""
    from agent_sync.user_config import get_user_config
    return get_user_config()


# ---------------------------------------------------------------------------
# Root directories (with user config override support)
# ---------------------------------------------------------------------------

HOME = Path.home()


def get_agents_dir() -> Path:
    """Get agents directory (respects user config override)."""
    config = _get_config()
    return config.paths.agents_dir if config.paths.agents_dir else HOME / ".agents"


def get_copilot_dir() -> Path:
    """Get copilot directory (respects user config override)."""
    config = _get_config()
    return config.paths.copilot_dir if config.paths.copilot_dir else HOME / ".copilot"


def get_claude_dir() -> Path:
    """Get claude directory (respects user config override)."""
    config = _get_config()
    return config.paths.claude_dir if config.paths.claude_dir else HOME / ".claude"


def get_codex_dir() -> Path:
    """Get codex directory (respects user config override)."""
    config = _get_config()
    return config.paths.codex_dir if config.paths.codex_dir else HOME / ".codex"


# Backwards compatibility: Keep constants for now (call functions)
AGENTS_DIR = get_agents_dir()
COPILOT_DIR = get_copilot_dir()
CLAUDE_DIR = get_claude_dir()
CODEX_DIR = get_codex_dir()

# ---------------------------------------------------------------------------
# Canonical config files inside .agents/
# ---------------------------------------------------------------------------

MCP_JSON = AGENTS_DIR / "mcp.json"
SKILL_LOCK_JSON = AGENTS_DIR / ".skill-lock.json"
CANONICAL_COMMANDS_DIR = AGENTS_DIR / "commands"
CANONICAL_SKILLS_DIR = AGENTS_DIR / "skills"

# ---------------------------------------------------------------------------
# Copilot CLI paths
# ---------------------------------------------------------------------------

COPILOT_CONFIG_JSON = COPILOT_DIR / "config.json"
COPILOT_MCP_CONFIG_JSON = COPILOT_DIR / "mcp-config.json"
COPILOT_INSTALLED_PLUGINS = COPILOT_DIR / "installed-plugins"
COPILOT_MARKETPLACE_CACHE = COPILOT_DIR / "marketplace-cache"

# ---------------------------------------------------------------------------
# Claude Code paths
# ---------------------------------------------------------------------------

CLAUDE_SETTINGS_JSON = CLAUDE_DIR / "settings.json"
CLAUDE_CODE_CONFIG_JSON = HOME / ".claude.json"  # Claude Code's actual config
CLAUDE_DESKTOP_CONFIG_JSON = HOME / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
CLAUDE_COMMANDS_DIR = CLAUDE_DIR / "commands"
CLAUDE_SKILLS_DIR = CLAUDE_DIR / "skills"
CLAUDE_SYMLINK_SKILLS = AGENTS_DIR / ".claude" / "skills"

# ---------------------------------------------------------------------------
# OpenAI Codex paths
# ---------------------------------------------------------------------------

CODEX_CONFIG_TOML = CODEX_DIR / "config.toml"
CODEX_PROMPTS_DIR = CODEX_DIR / "prompts"
CODEX_SKILLS_DIR = CODEX_DIR / "skills"

# ---------------------------------------------------------------------------
# Product workflow directories (auto-discovered, but known names listed)
# ---------------------------------------------------------------------------

KNOWN_PRODUCTS = ["LoadSEERNext", "LSStudio", "atlas-viewer"]

# ---------------------------------------------------------------------------
# ia-skills-hub plugin repository
# ---------------------------------------------------------------------------

def get_ia_skills_hub_dir() -> Path | None:
    """Get ia-skills-hub directory (respects user config override).
    
    Returns path if configured or auto-discovered, None otherwise.
    """
    config = _get_config()
    if config.paths.ia_skills_hub:
        return config.paths.ia_skills_hub
    
    # Auto-discover from common paths
    common_paths = [
        HOME / "repos" / "github.com" / "integralanalytics" / "ia-skills-hub",
        HOME.parent.parent / "repos" / "github.com" / "integralanalytics" / "ia-skills-hub",
        Path("d:/repos/github.com/integralanalytics/ia-skills-hub"),
    ]
    for path in common_paths:
        if path.exists() and (path / "plugins").exists():
            return path
    return None


# Backwards compatibility
IA_SKILLS_HUB_DIR = get_ia_skills_hub_dir()

# ---------------------------------------------------------------------------
# File patterns
# ---------------------------------------------------------------------------

SKILL_FILE = "SKILL.md"
AGENT_MD_GLOB = "*.agent.md"
AGENT_YAML = "openai.yaml"
COMMAND_MD_GLOB = "*.md"

# ---------------------------------------------------------------------------
# Content type labels
# ---------------------------------------------------------------------------

CT_MCP = "mcp"
CT_SKILL = "skill"
CT_COMMAND = "command"
CT_AGENT = "agent"
CT_SYMLINK = "symlink"
CT_CONFIG = "config"
