"""Scanners that read configuration from each AI tool and from .agents/ canonical sources.

Each scanner function returns a typed model (ToolConfig or CanonicalState).
All I/O is isolated here so the rest of the codebase works with pure data.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

if sys.version_info >= (3, 12):
    import tomllib
else:
    try:
        import tomllib  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[import-untyped, no-redef]

from agent_sync.config import (
    AGENTS_DIR,
    CANONICAL_COMMANDS_DIR,
    CANONICAL_SKILLS_DIR,
    CLAUDE_COMMANDS_DIR,
    CLAUDE_DIR,
    CLAUDE_SETTINGS_JSON,
    CLAUDE_SKILLS_DIR,
    CLAUDE_SYMLINK_SKILLS,
    CODEX_CONFIG_TOML,
    CODEX_PROMPTS_DIR,
    CODEX_SKILLS_DIR,
    COPILOT_CONFIG_JSON,
    COPILOT_INSTALLED_PLUGINS,
    COPILOT_MCP_CONFIG_JSON,
    IA_SKILLS_HUB_DIR,
    MCP_JSON,
    SKILL_FILE,
    SKILL_LOCK_JSON,
)
from agent_sync.models import (
    Agent,
    CanonicalState,
    Command,
    McpServer,
    McpServerType,
    Plugin,
    ProductWorkflow,
    Skill,
    ToolConfig,
    ToolName,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _body_hash(text: str) -> str:
    """SHA-256 of text with normalized whitespace for drift detection."""
    normalized = text.strip().replace("\r\n", "\n")
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split YAML frontmatter from markdown body.

    Returns (frontmatter_dict, body_text). If no frontmatter, returns ({}, full_text).
    """
    if not text.startswith("---"):
        return {}, text

    end = text.find("\n---", 3)
    if end == -1:
        return {}, text

    fm_block = text[3:end].strip()
    body = text[end + 4:].strip()

    fm: dict = {}
    for line in fm_block.splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        # Parse simple YAML values
        if value.startswith("[") and value.endswith("]"):
            # Parse YAML array: [a, b, c]
            items = value[1:-1].split(",")
            fm[key] = [i.strip().strip("'\"") for i in items if i.strip()]
        elif value.lower() in ("true", "false"):
            fm[key] = value.lower() == "true"
        elif value.startswith('"') and value.endswith('"'):
            fm[key] = value[1:-1]
        elif value.startswith("'") and value.endswith("'"):
            fm[key] = value[1:-1]
        else:
            fm[key] = value

    return fm, body


def _read_json(path: Path) -> dict:
    """Read a JSON/JSONC file, stripping // comments but preserving URLs.

    Uses a simple state machine to skip comment-stripping inside strings.
    """
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")

    # Strip // comments that appear outside of quoted strings
    result: list[str] = []
    in_string = False
    escape = False
    i = 0
    while i < len(text):
        ch = text[i]
        if escape:
            result.append(ch)
            escape = False
            i += 1
            continue
        if ch == "\\" and in_string:
            result.append(ch)
            escape = True
            i += 1
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
            i += 1
            continue
        if not in_string and ch == "/" and i + 1 < len(text) and text[i + 1] == "/":
            # Skip to end of line
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        result.append(ch)
        i += 1

    try:
        return json.loads("".join(result))
    except json.JSONDecodeError:
        return {}


def _read_toml(path: Path) -> dict:
    """Read a TOML config file."""
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _folder_hash(folder: Path) -> str:
    """Compute a deterministic hash of all files in a folder."""
    h = hashlib.sha1(usedforsecurity=False)
    for p in sorted(folder.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(folder).as_posix().encode())
            h.update(p.read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# MCP canonical scanner
# ---------------------------------------------------------------------------


def scan_canonical_mcp() -> list[McpServer]:
    """Read the canonical mcp.json from .agents/."""
    data = _read_json(MCP_JSON)
    servers: list[McpServer] = []
    for name, cfg in data.get("servers", {}).items():
        servers.append(
            McpServer(
                name=name,
                server_type=McpServerType(cfg.get("type", "http")),
                url=cfg.get("url"),
                command=cfg.get("command"),
                args=cfg.get("args", []),
                headers=cfg.get("headers", {}),
                env=cfg.get("env", {}),
                tools=cfg.get("tools", ["*"]),
                enabled_for=[ToolName(t) for t in cfg.get("enabled_for", [])],
            )
        )
    return servers


# ---------------------------------------------------------------------------
# Skill scanners
# ---------------------------------------------------------------------------


def scan_canonical_skills() -> list[Skill]:
    """Enumerate skills from the canonical .agents/skills/ directory."""
    skills: list[Skill] = []
    if not CANONICAL_SKILLS_DIR.exists():
        return skills

    lock = _read_json(SKILL_LOCK_JSON)
    lock_skills = lock.get("skills", {})

    for d in sorted(CANONICAL_SKILLS_DIR.iterdir()):
        if not d.is_dir():
            continue
        skill_file = d / SKILL_FILE
        desc = ""
        if skill_file.exists():
            fm, _ = _parse_frontmatter(skill_file.read_text(encoding="utf-8"))
            desc = fm.get("description", "")

        lock_entry = lock_skills.get(d.name, {})
        skills.append(
            Skill(
                name=d.name,
                path=d,
                description=desc,
                source=lock_entry.get("source", "local"),
                source_type=lock_entry.get("sourceType", "local"),
                source_url=lock_entry.get("sourceUrl", ""),
                skill_path=lock_entry.get("skillPath", ""),
                folder_hash=lock_entry.get("skillFolderHash", ""),
                installed_at=lock_entry.get("installedAt", ""),
                updated_at=lock_entry.get("updatedAt", ""),
            )
        )
    return skills


# ---------------------------------------------------------------------------
# Command scanners
# ---------------------------------------------------------------------------


def _scan_commands_dir(
    base_dir: Path,
    *,
    namespace_from_folder: bool = True,
    slug_prefix_strip: str = "",
) -> list[Command]:
    """Scan a directory tree for markdown command/prompt files."""
    commands: list[Command] = []
    if not base_dir.exists():
        return commands

    for md_file in sorted(base_dir.rglob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        fm, body = _parse_frontmatter(text)

        if namespace_from_folder:
            ns = md_file.parent.name if md_file.parent != base_dir else ""
            slug = md_file.stem
        else:
            # Codex style: opsx-explore.md -> namespace=opsx, slug=explore
            parts = md_file.stem.split("-", 1)
            ns = parts[0] if len(parts) > 1 else ""
            slug = parts[1] if len(parts) > 1 else md_file.stem

        tags_raw = fm.get("tags", [])
        if isinstance(tags_raw, str):
            tags_raw = [t.strip() for t in tags_raw.split(",")]

        sync_to_raw = fm.get("sync_to", [])
        if isinstance(sync_to_raw, str):
            sync_to_raw = [t.strip() for t in sync_to_raw.split(",")]
        sync_to = []
        for t in sync_to_raw:
            try:
                sync_to.append(ToolName(t))
            except ValueError:
                pass

        commands.append(
            Command(
                name=fm.get("name", ""),
                slug=slug,
                namespace=ns,
                description=fm.get("description", ""),
                category=fm.get("category", ""),
                tags=tags_raw,
                argument_hint=fm.get("argument-hint", ""),
                sync_to=sync_to,
                body=body,
                body_hash=_body_hash(body),
                source_path=md_file,
            )
        )
    return commands


def scan_canonical_commands() -> list[Command]:
    """Read commands from .agents/commands/."""
    return _scan_commands_dir(CANONICAL_COMMANDS_DIR, namespace_from_folder=True)


# ---------------------------------------------------------------------------
# Product workflow scanner
# ---------------------------------------------------------------------------


def scan_product_workflows() -> list[ProductWorkflow]:
    """Discover product-specific workflow directories under .agents/."""
    workflows: list[ProductWorkflow] = []
    if not AGENTS_DIR.exists():
        return workflows

    # Skip hidden dirs and known non-product dirs
    skip = {".claude", "skills", "tools", "commands"}

    for d in sorted(AGENTS_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or d.name in skip:
            continue

        wf = ProductWorkflow(name=d.name, path=d)

        # Agents
        agents_dir = d / "agents"
        if agents_dir.exists():
            for f in sorted(agents_dir.rglob("*.agent.md")):
                wf.agents.append(Agent(name=f.stem.replace(".agent", ""), path=f))

        # Prompts
        prompts_dir = d / "prompts"
        if prompts_dir.exists():
            wf.prompts = sorted(prompts_dir.rglob("*.md"))

        # Instructions
        instr_dir = d / "instructions"
        if instr_dir.exists():
            wf.instructions = sorted(instr_dir.rglob("*.md"))

        # Product-specific skills
        skills_dir = d / "skills"
        if skills_dir.exists():
            for sd in sorted(skills_dir.iterdir()):
                if sd.is_dir() and (sd / SKILL_FILE).exists():
                    fm, _ = _parse_frontmatter(
                        (sd / SKILL_FILE).read_text(encoding="utf-8")
                    )
                    wf.skills.append(
                        Skill(name=sd.name, path=sd, description=fm.get("description", ""))
                    )

        # Check if this product has a Copilot plugin installed
        plugin_dir = COPILOT_INSTALLED_PLUGINS / "ia-skills-hub"
        if plugin_dir.exists():
            # Look for a plugin that matches this product name (e.g., ls-next-workflow)
            for pd in plugin_dir.iterdir():
                if pd.is_dir():
                    pjson = pd / "plugin.json"
                    if pjson.exists():
                        pdata = _read_json(pjson)
                        # Heuristic: check if the plugin name references this product
                        pname = pdata.get("name", "").lower()
                        product_slug = d.name.lower().replace("next", "-next").replace("studio", "-studio")
                        if any(token in pname for token in product_slug.split("-") if len(token) > 3):
                            wf.copilot_plugin_installed = True
                            wf.copilot_plugin_version = pdata.get("version", "")

        workflows.append(wf)
    return workflows


def scan_available_plugins() -> list[Plugin]:
    """Scan ia-skills-hub repository for available Copilot plugins."""
    plugins: list[Plugin] = []
    
    if not IA_SKILLS_HUB_DIR or not IA_SKILLS_HUB_DIR.exists():
        return plugins
    
    plugins_dir = IA_SKILLS_HUB_DIR / "plugins"
    if not plugins_dir.exists():
        return plugins
    
    for plugin_path in sorted(plugins_dir.iterdir()):
        if not plugin_path.is_dir():
            continue
            
        plugin_json = plugin_path / "plugin.json"
        if not plugin_json.exists():
            continue
        
        try:
            pdata = _read_json(plugin_json)
            plugins.append(
                Plugin(
                    name=pdata.get("name", plugin_path.name),
                    path=plugin_path,
                    description=pdata.get("description", ""),
                    version=pdata.get("version", ""),
                    category=pdata.get("category", ""),
                )
            )
        except Exception:
            # Skip malformed plugin.json files
            continue
    
    return plugins


# ---------------------------------------------------------------------------
# Copilot scanner
# ---------------------------------------------------------------------------


def scan_copilot() -> ToolConfig:
    """Scan GitHub Copilot CLI configuration."""
    cfg = ToolConfig(tool=ToolName.COPILOT, config_path=COPILOT_CONFIG_JSON)

    # MCP servers
    mcp_data = _read_json(COPILOT_MCP_CONFIG_JSON)
    for name, srv in mcp_data.get("mcpServers", {}).items():
        cfg.mcp_servers.append(
            McpServer(
                name=name,
                server_type=McpServerType(srv.get("type", "http")),
                url=srv.get("url"),
                command=srv.get("command"),
                args=srv.get("args", []),
                headers=srv.get("headers", {}),
                tools=srv.get("tools", ["*"]),
            )
        )

    # Config info
    config_data = _read_json(COPILOT_CONFIG_JSON)
    cfg.extra_info["marketplaces"] = str(len(config_data.get("marketplaces", {})))
    cfg.extra_info["installed_plugins"] = str(len(config_data.get("installed_plugins", [])))

    # Installed plugin skills
    if COPILOT_INSTALLED_PLUGINS.exists():
        for plugin_dir in COPILOT_INSTALLED_PLUGINS.rglob("plugin.json"):
            pdata = _read_json(plugin_dir)
            skills_dir = plugin_dir.parent / "skills"
            if skills_dir.exists():
                for sd in skills_dir.iterdir():
                    if sd.is_dir() and (sd / SKILL_FILE).exists():
                        cfg.skills.append(Skill(name=sd.name, path=sd))

            # Agents
            agents_dir = plugin_dir.parent / "agents"
            if agents_dir.exists():
                for f in agents_dir.rglob("*.md"):
                    cfg.agents.append(
                        Agent(name=f.stem, path=f, format="markdown")
                    )

    return cfg


# ---------------------------------------------------------------------------
# Claude scanner
# ---------------------------------------------------------------------------


def scan_claude() -> ToolConfig:
    """Scan Claude Code configuration."""
    cfg = ToolConfig(tool=ToolName.CLAUDE, config_path=CLAUDE_SETTINGS_JSON)

    settings = _read_json(CLAUDE_SETTINGS_JSON)
    cfg.model = settings.get("model", "")
    cfg.extra_info["thinking"] = str(settings.get("alwaysThinkingEnabled", False))
    cfg.extra_info["agent_teams"] = settings.get("env", {}).get(
        "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS", ""
    )

    # Detect MCP from permissions
    allow = settings.get("permissions", {}).get("allow", [])
    mcp_names: set[str] = set()
    for perm in allow:
        if isinstance(perm, str) and perm.startswith("mcp__"):
            parts = perm.split("__")
            if len(parts) >= 2:
                mcp_names.add(parts[1])
    for mcp_name in sorted(mcp_names):
        cfg.mcp_servers.append(
            McpServer(name=mcp_name, server_type=McpServerType.LOCAL)
        )

    # Additional directories
    additional_dirs = settings.get("permissions", {}).get("additionalDirectories", [])
    cfg.extra_info["additional_directories"] = ", ".join(additional_dirs)

    # Check symlink to skills
    if CLAUDE_SYMLINK_SKILLS.exists():
        cfg.extra_info["skills_symlink"] = str(CLAUDE_SYMLINK_SKILLS)
        if CLAUDE_SYMLINK_SKILLS.is_symlink() or CLAUDE_SYMLINK_SKILLS.is_junction():
            cfg.extra_info["skills_symlink_target"] = str(
                CLAUDE_SYMLINK_SKILLS.resolve()
            )
        # Count skills accessible via symlink
        for sd in CLAUDE_SYMLINK_SKILLS.iterdir():
            if sd.is_dir() and (sd / SKILL_FILE).exists():
                cfg.skills.append(Skill(name=sd.name, path=sd))

    # Direct skills in ~/.claude/skills/
    if CLAUDE_SKILLS_DIR.exists():
        for sd in CLAUDE_SKILLS_DIR.iterdir():
            if sd.is_dir() and (sd / SKILL_FILE).exists():
                if not any(s.name == sd.name for s in cfg.skills):
                    cfg.skills.append(Skill(name=sd.name, path=sd))

    # Commands
    cfg.commands = _scan_commands_dir(CLAUDE_COMMANDS_DIR, namespace_from_folder=True)

    return cfg


# ---------------------------------------------------------------------------
# Codex scanner
# ---------------------------------------------------------------------------


def scan_codex() -> ToolConfig:
    """Scan OpenAI Codex configuration."""
    cfg = ToolConfig(tool=ToolName.CODEX, config_path=CODEX_CONFIG_TOML)

    toml_data = _read_toml(CODEX_CONFIG_TOML)
    cfg.model = toml_data.get("model", "")
    cfg.extra_info["personality"] = toml_data.get("personality", "")
    cfg.extra_info["reasoning_effort"] = toml_data.get("model_reasoning_effort", "")

    # MCP servers
    for name, srv in toml_data.get("mcp_servers", {}).items():
        stype = McpServerType.HTTP if "url" in srv else McpServerType.STDIO
        cfg.mcp_servers.append(
            McpServer(
                name=name,
                server_type=stype,
                url=srv.get("url"),
                command=srv.get("command"),
                args=srv.get("args", []),
                enabled=srv.get("enabled", True),
            )
        )

    # Prompts (Codex naming: opsx-explore.md)
    cfg.commands = _scan_commands_dir(
        CODEX_PROMPTS_DIR,
        namespace_from_folder=False,
    )

    # Skills
    if CODEX_SKILLS_DIR.exists():
        for sd in CODEX_SKILLS_DIR.rglob(SKILL_FILE):
            cfg.skills.append(
                Skill(name=sd.parent.name, path=sd.parent)
            )

    return cfg


# ---------------------------------------------------------------------------
# Full canonical scan
# ---------------------------------------------------------------------------


def scan_canonical(agents_dir: Path | None = None) -> CanonicalState:
    """Build the full canonical state from .agents/."""
    root = agents_dir or AGENTS_DIR
    return CanonicalState(
        agents_dir=root,
        mcp_servers=scan_canonical_mcp(),
        skills=scan_canonical_skills(),
        commands=scan_canonical_commands(),
        product_workflows=scan_product_workflows(),
        available_plugins=scan_available_plugins(),
        skill_lock=_read_json(SKILL_LOCK_JSON),
    )


def scan_all_tools() -> dict[ToolName, ToolConfig]:
    """Scan all supported tools and return a dict keyed by ToolName."""
    return {
        ToolName.COPILOT: scan_copilot(),
        ToolName.CLAUDE: scan_claude(),
        ToolName.CODEX: scan_codex(),
    }
