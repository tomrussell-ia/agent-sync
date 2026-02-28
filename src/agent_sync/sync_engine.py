"""Sync engine — compares canonical state vs tool configs and produces a SyncReport.

Also provides fix operations that apply changes to bring tools in sync.
"""

from __future__ import annotations

from agent_sync.formatters.commands import (
    sync_commands,
)
from agent_sync.formatters.mcp import (
    write_claude_mcp,
    write_codex_mcp,
    write_copilot_mcp,
)
from agent_sync.formatters.skills import (
    check_claude_additional_dirs,
    check_claude_skills_symlink,
    check_copilot_additional_dirs,
    fix_claude_additional_dirs,
    fix_claude_skills_symlink,
    fix_copilot_additional_dirs,
)
from agent_sync.models import (
    CanonicalState,
    FixAction,
    FixActionType,
    SyncItem,
    SyncReport,
    SyncStatus,
    ToolConfig,
    ToolName,
)


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------


def _mcp_name_normalize(name: str) -> str:
    """Normalize MCP server names for comparison across tools.

    Strips all non-alphanumeric characters and lowercases, so
    ``MicrosoftLearn``, ``microsoft-learn``, and ``Microsoft_Learn``
    all normalise to ``microsoftlearn``.
    """
    import re

    return re.sub(r"[^a-z0-9]", "", name.lower())


# ---------------------------------------------------------------------------
# MCP comparison
# ---------------------------------------------------------------------------


def _compare_mcp(
    canonical: CanonicalState,
    tool_configs: dict[ToolName, ToolConfig],
) -> list[SyncItem]:
    """Compare canonical MCP servers against each tool's config.
    
    Respects user config mcp.ignore_servers to skip specific servers.
    """
    from agent_sync.user_config import get_user_config
    
    user_cfg = get_user_config()
    ignored_servers = {_mcp_name_normalize(name) for name in user_cfg.mcp.ignore_servers}
    
    items: list[SyncItem] = []

    for srv in canonical.mcp_servers:
        # Skip ignored servers
        if _mcp_name_normalize(srv.name) in ignored_servers:
            continue
            
        for tool_name in [ToolName.COPILOT, ToolName.CLAUDE, ToolName.CODEX]:
            tc = tool_configs.get(tool_name)
            if not tc:
                continue

            if tool_name not in srv.enabled_for:
                items.append(
                    SyncItem(
                        content_type="mcp",
                        item_name=srv.name,
                        tool=tool_name,
                        status=SyncStatus.NOT_APPLICABLE,
                        detail="Not enabled for this tool",
                    )
                )
                continue

            # Find matching server in tool config
            tool_srv = None
            for ts in tc.mcp_servers:
                if _mcp_name_normalize(ts.name) == _mcp_name_normalize(srv.name):
                    tool_srv = ts
                    break

            if not tool_srv:
                items.append(
                    SyncItem(
                        content_type="mcp",
                        item_name=srv.name,
                        tool=tool_name,
                        status=SyncStatus.MISSING,
                        detail=f"Canonical server not found in {tool_name.value} config",
                        fix_action=FixAction(
                            action=FixActionType.ADD_MCP,
                            tool=tool_name,
                            content_type="mcp",
                            target=srv.name,
                            detail=f"Add {srv.name} to {tool_name.value} MCP config",
                        ),
                    )
                )
                continue

            # Compare key fields
            drift_reasons: list[str] = []
            if srv.url and tool_srv.url and srv.url != tool_srv.url:
                drift_reasons.append(f"URL mismatch: {tool_srv.url}")
            if srv.command and tool_srv.command and srv.command != tool_srv.command:
                drift_reasons.append(f"Command mismatch: {tool_srv.command}")
            if srv.args and tool_srv.args and srv.args != tool_srv.args:
                drift_reasons.append("Args mismatch")

            if drift_reasons:
                items.append(
                    SyncItem(
                        content_type="mcp",
                        item_name=srv.name,
                        tool=tool_name,
                        status=SyncStatus.DRIFT,
                        detail="; ".join(drift_reasons),
                        fix_action=FixAction(
                            action=FixActionType.UPDATE_MCP,
                            tool=tool_name,
                            content_type="mcp",
                            target=srv.name,
                            detail=f"Update {srv.name} in {tool_name.value}",
                        ),
                    )
                )
            else:
                items.append(
                    SyncItem(
                        content_type="mcp",
                        item_name=srv.name,
                        tool=tool_name,
                        status=SyncStatus.SYNCED,
                    )
                )

    # Check for extra servers in tool configs not in canonical
    canonical_names = {_mcp_name_normalize(s.name) for s in canonical.mcp_servers}
    for tool_name, tc in tool_configs.items():
        for ts in tc.mcp_servers:
            norm_name = _mcp_name_normalize(ts.name)
            
            # Skip if in canonical or ignored
            if norm_name in canonical_names or norm_name in ignored_servers:
                continue
            
            # Only flag as drift if ignore_extra_servers is False
            if not user_cfg.tools.ignore_extra_servers:
                items.append(
                    SyncItem(
                        content_type="mcp",
                        item_name=ts.name,
                        tool=tool_name,
                        status=SyncStatus.EXTRA,
                        detail=f"Server in {tool_name.value} not in canonical mcp.json",
                        fix_action=FixAction(
                            action=FixActionType.REMOVE_MCP,
                            tool=tool_name,
                            content_type="mcp",
                            target=ts.name,
                            detail=f"Add {ts.name} to canonical mcp.json or remove from {tool_name.value}",
                        ),
                    )
                )

    return items


# ---------------------------------------------------------------------------
# Skills comparison
# ---------------------------------------------------------------------------


def _compare_skills(
    canonical: CanonicalState,
    tool_configs: dict[ToolName, ToolConfig],
) -> list[SyncItem]:
    """Compare skill availability across tools."""
    items: list[SyncItem] = []

    # Check symlink health (for Claude symlink-based access)
    symlink_ok, symlink_detail = check_claude_skills_symlink()
    items.append(
        SyncItem(
            content_type="symlink",
            item_name="claude-skills-symlink",
            tool=ToolName.CLAUDE,
            status=SyncStatus.SYNCED if symlink_ok else SyncStatus.MISSING,
            detail=symlink_detail,
            fix_action=None
            if symlink_ok
            else FixAction(
                action=FixActionType.CREATE_SYMLINK,
                tool=ToolName.CLAUDE,
                content_type="symlink",
                target="claude-skills-symlink",
                detail="Create junction .agents/.claude/skills/ → .agents/skills/",
            ),
        )
    )

    # Check Claude additionalDirectories
    claude_dirs_ok, claude_dirs_detail = check_claude_additional_dirs()
    items.append(
        SyncItem(
            content_type="config",
            item_name="claude-additional-dirs",
            tool=ToolName.CLAUDE,
            status=SyncStatus.SYNCED if claude_dirs_ok else SyncStatus.MISSING,
            detail=claude_dirs_detail,
            fix_action=None
            if claude_dirs_ok
            else FixAction(
                action=FixActionType.ADD_CONFIG,
                tool=ToolName.CLAUDE,
                content_type="config",
                target="claude-additional-dirs",
                detail="Add .agents/skills to Claude additionalDirectories",
            ),
        )
    )

    # Check Copilot additionalDirectories
    copilot_dirs_ok, copilot_dirs_detail = check_copilot_additional_dirs()
    items.append(
        SyncItem(
            content_type="config",
            item_name="copilot-additional-dirs",
            tool=ToolName.COPILOT,
            status=SyncStatus.SYNCED if copilot_dirs_ok else SyncStatus.MISSING,
            detail=copilot_dirs_detail,
            fix_action=None
            if copilot_dirs_ok
            else FixAction(
                action=FixActionType.ADD_CONFIG,
                tool=ToolName.COPILOT,
                content_type="config",
                target="copilot-additional-dirs",
                detail="Add .agents/skills to Copilot additionalDirectories",
            ),
        )
    )

    # Per-skill status - now accurately reflects scanner results
    for skill in canonical.skills:
        for tool_name, tc in tool_configs.items():
            tool_skill_names = {s.name for s in tc.skills}
            if skill.name in tool_skill_names:
                # Scanner found this skill accessible (via additionalDirectories, symlink, or direct)
                items.append(
                    SyncItem(
                        content_type="skill",
                        item_name=skill.name,
                        tool=tool_name,
                        status=SyncStatus.SYNCED,
                        detail="Accessible",
                    )
                )
            # Codex can't easily link external skills
            elif tool_name == ToolName.CODEX:
                items.append(
                    SyncItem(
                        content_type="skill",
                        item_name=skill.name,
                        tool=tool_name,
                        status=SyncStatus.NOT_APPLICABLE,
                        detail="Codex uses built-in skills only",
                    )
                )
            else:
                # Skill not found by scanner - report as missing with actionable detail
                detail = f"Not accessible in {tool_name.value}"
                if tool_name == ToolName.CLAUDE and not claude_dirs_ok:
                    detail = "Configure additionalDirectories to access"
                elif tool_name == ToolName.COPILOT and not copilot_dirs_ok:
                    detail = "Configure additionalDirectories to access"
                
                items.append(
                    SyncItem(
                        content_type="skill",
                        item_name=skill.name,
                        tool=tool_name,
                        status=SyncStatus.MISSING,
                        detail=detail,
                    )
                )

    return items


# ---------------------------------------------------------------------------
# Command comparison
# ---------------------------------------------------------------------------


def _compare_commands(
    canonical: CanonicalState,
    tool_configs: dict[ToolName, ToolConfig],
) -> list[SyncItem]:
    """Compare canonical commands against Claude and Codex versions."""
    items: list[SyncItem] = []

    if not canonical.commands:
        # No canonical commands yet — compare Claude vs Codex directly
        claude_tc = tool_configs.get(ToolName.CLAUDE)
        codex_tc = tool_configs.get(ToolName.CODEX)
        if claude_tc and codex_tc:
            claude_by_slug = {(c.namespace, c.slug): c for c in claude_tc.commands}
            codex_by_slug = {(c.namespace, c.slug): c for c in codex_tc.commands}

            all_keys = set(claude_by_slug) | set(codex_by_slug)
            for ns, slug in sorted(all_keys):
                c_cmd = claude_by_slug.get((ns, slug))
                x_cmd = codex_by_slug.get((ns, slug))
                name = f"{ns}/{slug}" if ns else slug

                if c_cmd and x_cmd:
                    if c_cmd.body_hash == x_cmd.body_hash:
                        items.append(
                            SyncItem(
                                content_type="command",
                                item_name=name,
                                tool=ToolName.CLAUDE,
                                status=SyncStatus.SYNCED,
                                detail="Body matches Codex",
                            )
                        )
                    else:
                        items.append(
                            SyncItem(
                                content_type="command",
                                item_name=name,
                                tool=ToolName.CLAUDE,
                                status=SyncStatus.DRIFT,
                                detail=f"Body hash mismatch: Claude={c_cmd.body_hash[:8]} Codex={x_cmd.body_hash[:8]}",
                                fix_action=FixAction(
                                    action=FixActionType.RECONCILE_COMMAND,
                                    tool=ToolName.CLAUDE,
                                    content_type="command",
                                    target=name,
                                    detail="Reconcile command body between Claude and Codex",
                                ),
                            )
                        )
                elif c_cmd and not x_cmd:
                    items.append(
                        SyncItem(
                            content_type="command",
                            item_name=name,
                            tool=ToolName.CODEX,
                            status=SyncStatus.MISSING,
                            detail="Exists in Claude but not Codex",
                            fix_action=FixAction(
                                action=FixActionType.COPY_COMMAND,
                                tool=ToolName.CODEX,
                                content_type="command",
                                target=name,
                                detail=f"Copy {name} to Codex prompts",
                            ),
                        )
                    )
                elif x_cmd and not c_cmd:
                    items.append(
                        SyncItem(
                            content_type="command",
                            item_name=name,
                            tool=ToolName.CLAUDE,
                            status=SyncStatus.MISSING,
                            detail="Exists in Codex but not Claude",
                            fix_action=FixAction(
                                action=FixActionType.COPY_COMMAND,
                                tool=ToolName.CLAUDE,
                                content_type="command",
                                target=name,
                                detail=f"Copy {name} to Claude commands",
                            ),
                        )
                    )
        return items

    # Canonical commands exist — compare against each tool
    for cmd in canonical.commands:
        name = f"{cmd.namespace}/{cmd.slug}" if cmd.namespace else cmd.slug
        targets = cmd.sync_to or [ToolName.CLAUDE, ToolName.CODEX]

        for tool_name in targets:
            tc = tool_configs.get(tool_name)
            if not tc:
                continue

            # Find matching command
            tool_cmd = None
            for tc_cmd in tc.commands:
                if tc_cmd.namespace == cmd.namespace and tc_cmd.slug == cmd.slug:
                    tool_cmd = tc_cmd
                    break

            if not tool_cmd:
                items.append(
                    SyncItem(
                        content_type="command",
                        item_name=name,
                        tool=tool_name,
                        status=SyncStatus.MISSING,
                        detail=f"Canonical command not found in {tool_name.value}",
                        fix_action=FixAction(
                            action=FixActionType.WRITE_COMMAND,
                            tool=tool_name,
                            content_type="command",
                            target=name,
                            detail=f"Write {name} to {tool_name.value}",
                        ),
                    )
                )
                continue

            if cmd.body_hash == tool_cmd.body_hash:
                items.append(
                    SyncItem(
                        content_type="command",
                        item_name=name,
                        tool=tool_name,
                        status=SyncStatus.SYNCED,
                    )
                )
            else:
                items.append(
                    SyncItem(
                        content_type="command",
                        item_name=name,
                        tool=tool_name,
                        status=SyncStatus.DRIFT,
                        detail=f"Body hash: canonical={cmd.body_hash[:8]} {tool_name.value}={tool_cmd.body_hash[:8]}",
                        fix_action=FixAction(
                            action=FixActionType.OVERWRITE_COMMAND,
                            tool=tool_name,
                            content_type="command",
                            target=name,
                            detail=f"Overwrite {tool_name.value} {name} from canonical",
                        ),
                    )
                )

    return items


# ---------------------------------------------------------------------------
# Plugin comparison
# ---------------------------------------------------------------------------


def _compare_plugins(
    canonical: CanonicalState,
    tool_configs: dict[ToolName, ToolConfig],
) -> list[SyncItem]:
    """Compare product workflows against available ia-skills-hub plugins."""
    items: list[SyncItem] = []

    # Only Copilot supports plugins currently
    if ToolName.COPILOT not in tool_configs:
        return items

    # For each product workflow, check if there's a matching plugin
    for workflow in canonical.product_workflows:
        # Find matching plugin by heuristic name matching
        matching_plugin = None
        product_tokens = (
            workflow.name.lower().replace("next", "-next").replace("studio", "-studio").split("-")
        )

        for plugin in canonical.available_plugins:
            plugin_name_lower = plugin.name.lower()
            # Check if plugin name contains significant product tokens
            if any(token in plugin_name_lower for token in product_tokens if len(token) > 3):
                matching_plugin = plugin
                break

        # If no matching plugin, skip (not all products need plugins)
        if not matching_plugin:
            continue

        # Check installation status
        if workflow.copilot_plugin_installed:
            items.append(
                SyncItem(
                    content_type="plugin",
                    item_name=matching_plugin.name,
                    tool=ToolName.COPILOT,
                    status=SyncStatus.SYNCED,
                    detail=f"v{workflow.copilot_plugin_version}",
                )
            )
        else:
            items.append(
                SyncItem(
                    content_type="plugin",
                    item_name=matching_plugin.name,
                    tool=ToolName.COPILOT,
                    status=SyncStatus.MISSING,
                    detail=f"{workflow.name} workflow plugin not installed",
                    fix_action=FixAction(
                        action=FixActionType.INSTALL_PLUGIN,
                        tool=ToolName.COPILOT,
                        content_type="plugin",
                        target=matching_plugin.name,
                        detail=f"Install via: gh copilot plugin install integralanalytics/ia-skills-hub/{matching_plugin.name}",
                    ),
                )
            )

    return items


# ---------------------------------------------------------------------------
# Full comparison
# ---------------------------------------------------------------------------


def build_sync_report(
    canonical: CanonicalState,
    tool_configs: dict[ToolName, ToolConfig],
) -> SyncReport:
    """Build a comprehensive sync report comparing canonical vs all tools."""
    items: list[SyncItem] = []
    items.extend(_compare_mcp(canonical, tool_configs))
    items.extend(_compare_skills(canonical, tool_configs))
    items.extend(_compare_commands(canonical, tool_configs))
    items.extend(_compare_plugins(canonical, tool_configs))

    return SyncReport(
        canonical=canonical,
        tool_configs=tool_configs,
        items=items,
    )


# ---------------------------------------------------------------------------
# Fix operations
# ---------------------------------------------------------------------------


def apply_fixes(report: SyncReport, *, dry_run: bool = False) -> list[str]:
    """Apply all available fixes from the sync report.

    Returns list of action descriptions.
    """
    actions: list[str] = []

    # 1. Fix MCP configs
    mcp_actions = [item for item in report.items if item.content_type == "mcp" and item.fix_action]
    if mcp_actions:
        # Group servers by tool to batch updates
        copilot_servers: list[McpServer] = []
        codex_servers: list[McpServer] = []
        claude_servers: list[McpServer] = []
        
        for item in mcp_actions:
            if item.fix_action.action in (FixActionType.ADD_MCP, FixActionType.UPDATE_MCP):
                # Find canonical server
                canonical_server = None
                for srv in report.canonical.mcp_servers:
                    if srv.name == item.item_name:
                        canonical_server = srv
                        break
                
                if not canonical_server:
                    continue
                
                # Route to appropriate tool
                if item.tool == ToolName.COPILOT:
                    copilot_servers.append(canonical_server)
                elif item.tool == ToolName.CODEX:
                    codex_servers.append(canonical_server)
                elif item.tool == ToolName.CLAUDE:
                    claude_servers.append(canonical_server)
        
        # Apply fixes per tool (batched)
        if copilot_servers:
            msg = write_copilot_mcp(copilot_servers, dry_run=dry_run)
            actions.append(f"MCP/copilot: {msg}")
        
        if codex_servers:
            msg = write_codex_mcp(codex_servers, dry_run=dry_run)
            actions.append(f"MCP/codex: {msg}")
        
        if claude_servers:
            actions.append(
                f"MCP/claude: Skipped {len(claude_servers)} servers (manual configuration required via Claude Desktop)"
            )

    # 2. Fix infrastructure (symlinks, additionalDirectories)
    claude_dirs_items = [
        i for i in report.items 
        if i.content_type == "config" and i.item_name == "claude-additional-dirs" 
        and i.status != SyncStatus.SYNCED
    ]
    if claude_dirs_items:
        actions.append(fix_claude_additional_dirs(dry_run=dry_run))

    copilot_dirs_items = [
        i for i in report.items 
        if i.content_type == "config" and i.item_name == "copilot-additional-dirs" 
        and i.status != SyncStatus.SYNCED
    ]
    if copilot_dirs_items:
        actions.append(fix_copilot_additional_dirs(dry_run=dry_run))

    # 3. Fix Claude skills symlink
    symlink_items = [
        i for i in report.items if i.content_type == "symlink" and i.status != SyncStatus.SYNCED
    ]
    if symlink_items:
        actions.append(fix_claude_skills_symlink(dry_run=dry_run))

    # 4. Fix commands (only if canonical commands exist)
    if report.canonical.commands:
        cmd_issues = [
            i
            for i in report.items
            if i.content_type == "command" and i.status in (SyncStatus.MISSING, SyncStatus.DRIFT)
        ]
        if cmd_issues:
            actions.extend(sync_commands(report.canonical.commands, dry_run=dry_run))

    return actions

