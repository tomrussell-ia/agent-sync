"""Path constants and tool definitions for agent-sync.

All paths resolve relative to the user's home directory.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Root directories
# ---------------------------------------------------------------------------

HOME = Path.home()

AGENTS_DIR = HOME / ".agents"
COPILOT_DIR = HOME / ".copilot"
CLAUDE_DIR = HOME / ".claude"
CODEX_DIR = HOME / ".codex"

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

# Try to discover ia-skills-hub repo location (common paths)
IA_SKILLS_HUB_PATHS = [
    HOME / "repos" / "github.com" / "integralanalytics" / "ia-skills-hub",
    HOME.parent.parent / "repos" / "github.com" / "integralanalytics" / "ia-skills-hub",
    Path("d:/repos/github.com/integralanalytics/ia-skills-hub"),
]
IA_SKILLS_HUB_DIR = None
for path in IA_SKILLS_HUB_PATHS:
    if path.exists() and (path / "plugins").exists():
        IA_SKILLS_HUB_DIR = path
        break

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
