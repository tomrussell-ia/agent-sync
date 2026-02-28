"""Rich console output for non-interactive mode (agent-sync check / probe)."""

from __future__ import annotations

import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from agent_sync.log_parser import LogReport, McpLogEvent
from agent_sync.models import (
    PluginValidation,
    ProbeReport,
    ProbeStatus,
    SyncReport,
    SyncStatus,
)


console = Console()

# Detect whether the terminal can handle emoji/Unicode.
_ENCODING = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
_USE_EMOJI = _ENCODING.lower().replace("-", "") in ("utf8", "utf16", "utf32")

if _USE_EMOJI:
    STATUS_STYLE = {
        SyncStatus.SYNCED: ("✅", "green"),
        SyncStatus.DRIFT: ("⚠️", "yellow"),
        SyncStatus.MISSING: ("❌", "red"),
        SyncStatus.EXTRA: ("➕", "cyan"),
        SyncStatus.NOT_APPLICABLE: ("—", "dim"),
    }
    PROBE_STYLE = {
        ProbeStatus.OK: ("✅", "green"),
        ProbeStatus.ERROR: ("❌", "red"),
        ProbeStatus.TIMEOUT: ("⏱️", "yellow"),
        ProbeStatus.SKIPPED: ("⏭️", "dim"),
        ProbeStatus.UNAVAILABLE: ("🚫", "dim"),
    }
else:
    STATUS_STYLE = {
        SyncStatus.SYNCED: ("[OK]", "green"),
        SyncStatus.DRIFT: ("[!!]", "yellow"),
        SyncStatus.MISSING: ("[XX]", "red"),
        SyncStatus.EXTRA: ("[++]", "cyan"),
        SyncStatus.NOT_APPLICABLE: ("--", "dim"),
    }
    PROBE_STYLE = {
        ProbeStatus.OK: ("[OK]", "green"),
        ProbeStatus.ERROR: ("[ERR]", "red"),
        ProbeStatus.TIMEOUT: ("[T/O]", "yellow"),
        ProbeStatus.SKIPPED: ("[SKIP]", "dim"),
        ProbeStatus.UNAVAILABLE: ("[N/A]", "dim"),
    }


def _icon(status: SyncStatus) -> str:
    icon, _ = STATUS_STYLE[status]
    return icon


def print_report(report: SyncReport, *, items: list | None = None) -> None:
    """Print a full sync report to the Rich console.

    Parameters
    ----------
    report:
        The full sync report (used for header stats and non-item sections).
    items:
        When provided, only these items are rendered in the per-section
        tables.  *Header summary* still reflects the full report so that
        filter narrowing is obvious.
    """
    display_items = items if items is not None else report.items

    console.print()

    # Header
    overall_icon, overall_style = STATUS_STYLE[report.overall_status]
    console.print(
        Panel(
            f"[bold]{overall_icon} Overall: {report.overall_status.value.upper()}[/bold]\n"
            f"Synced: {report.synced_count}  Drift: {report.drift_count}  "
            f"Missing: {report.missing_count}  Extra: {report.extra_count}  "
            f"Fixable: {report.fixable_count}",
            title="[bold]Agent Sync Report[/bold]",
            border_style=overall_style,
            expand=False,
        )
    )

    # MCP Servers
    mcp_items = [i for i in display_items if i.content_type == "mcp"]
    if mcp_items:
        table = Table(title="MCP Servers", show_lines=True)
        table.add_column("Server", style="bold")
        table.add_column("Tool")
        table.add_column("Status", justify="center")
        table.add_column("Detail")
        table.add_column("Fix", style="dim")
        for item in sorted(mcp_items, key=lambda x: (x.item_name, x.tool.value)):
            table.add_row(
                item.item_name,
                item.tool.value,
                _icon(item.status),
                item.detail or "",
                item.fix_action.detail if item.fix_action else "",
            )
        console.print(table)

    # Infrastructure
    infra_items = [i for i in display_items if i.content_type in ("symlink", "config")]
    if infra_items:
        table = Table(title="Infrastructure", show_lines=True)
        table.add_column("Check", style="bold")
        table.add_column("Status", justify="center")
        table.add_column("Detail")
        table.add_column("Fix", style="dim")
        for item in infra_items:
            table.add_row(
                item.item_name,
                _icon(item.status),
                item.detail or "",
                item.fix_action.detail if item.fix_action else "",
            )
        console.print(table)

    # Plugins
    plugin_items = [i for i in display_items if i.content_type == "plugin"]
    if plugin_items:
        table = Table(title="GitHub Copilot Plugins", show_lines=True)
        table.add_column("Plugin", style="bold")
        table.add_column("Status", justify="center")
        table.add_column("Detail")
        table.add_column("Fix", style="dim")
        for item in plugin_items:
            table.add_row(
                item.item_name,
                _icon(item.status),
                item.detail or "",
                item.fix_action.detail if item.fix_action else "",
            )
        console.print(table)

    # Commands
    cmd_items = [i for i in display_items if i.content_type == "command"]
    if cmd_items:
        table = Table(title="Commands / Prompts", show_lines=True)
        table.add_column("Command", style="bold")
        table.add_column("Tool")
        table.add_column("Status", justify="center")
        table.add_column("Detail")
        table.add_column("Fix", style="dim")
        for item in sorted(cmd_items, key=lambda x: (x.item_name, x.tool.value)):
            table.add_row(
                item.item_name,
                item.tool.value,
                _icon(item.status),
                item.detail or "",
                item.fix_action.detail if item.fix_action else "",
            )
        console.print(table)

    # Skills summary (grouped, not one row per tool×skill)
    skill_items = [i for i in display_items if i.content_type == "skill"]
    if skill_items:
        by_name: dict[str, dict[str, SyncStatus]] = {}
        for item in skill_items:
            by_name.setdefault(item.item_name, {})[item.tool.value] = item.status

        table = Table(title=f"Skills ({len(by_name)} shared)", show_lines=True)
        table.add_column("Skill", style="bold")
        table.add_column("Copilot", justify="center")
        table.add_column("Claude", justify="center")
        table.add_column("Codex", justify="center")

        for name, statuses in sorted(by_name.items()):
            table.add_row(
                name,
                _icon(statuses.get("copilot", SyncStatus.NOT_APPLICABLE)),
                _icon(statuses.get("claude", SyncStatus.NOT_APPLICABLE)),
                _icon(statuses.get("codex", SyncStatus.NOT_APPLICABLE)),
            )
        console.print(table)

    # Product workflows
    if report.canonical.product_workflows:
        tree = Tree("🏗️ Product Workflows")
        for wf in report.canonical.product_workflows:
            branch = tree.add(f"[bold]{wf.name}[/bold]")
            branch.add(f"Agents: {len(wf.agents)}")
            branch.add(f"Prompts: {len(wf.prompts)}")
            branch.add(f"Instructions: {len(wf.instructions)}")
            branch.add(f"Skills: {len(wf.skills)}")
            _ok = "✅" if _USE_EMOJI else "[OK]"
            _na = "—" if _USE_EMOJI else "--"
            plugin_status = (
                f"{_ok} v{wf.copilot_plugin_version}" if wf.copilot_plugin_installed else _na
            )
            branch.add(f"Copilot Plugin: {plugin_status}")
        console.print(tree)

    # Tool configs
    table = Table(title="Tool Configurations", show_lines=True)
    table.add_column("Tool", style="bold")
    table.add_column("Model")
    table.add_column("MCP")
    table.add_column("Skills")
    table.add_column("Commands")
    for tool_name, tc in sorted(report.tool_configs.items(), key=lambda x: x[0].value):
        table.add_row(
            tool_name.value.title(),
            tc.model or _NA,
            str(len(tc.mcp_servers)),
            str(len(tc.skills)),
            str(len(tc.commands)),
        )
    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# Probe report rendering
# ---------------------------------------------------------------------------


def _probe_icon(status: ProbeStatus) -> str:
    icon, _ = PROBE_STYLE[status]
    return icon


_NA = "\u2014" if _USE_EMOJI else "--"


def _fmt_latency(ms: float | None) -> str:
    if ms is None:
        return _NA
    if ms < 1000:
        return f"{ms:.0f}ms"
    return f"{ms / 1000:.1f}s"


def print_probe_report(report: ProbeReport, *, verbose: bool = False) -> None:
    """Print the runtime probe report to the Rich console."""
    console.print()

    overall_icon, overall_style = PROBE_STYLE[report.overall_status]
    console.print(
        Panel(
            f"[bold]{overall_icon} Probe: {report.overall_status.value.upper()}[/bold]\n"
            f"OK: {report.ok_count}  Error: {report.error_count}  "
            f"Timeout: {report.timeout_count}  Skipped: {report.skipped_count}",
            title="[bold]Runtime Probe Report[/bold]",
            border_style=overall_style,
            expand=False,
        )
    )

    # CLI version checks
    cli_results = [r for r in report.results if r.target_type.value == "cli-version"]
    if cli_results:
        table = Table(title="CLI Tools", show_lines=True)
        table.add_column("Tool", style="bold")
        table.add_column("Status", justify="center")
        table.add_column("Version / Detail")
        table.add_column("Latency")
        for r in cli_results:
            table.add_row(
                r.target,
                _probe_icon(r.status),
                r.detail or r.error_message or "",
                _fmt_latency(r.latency_ms),
            )
        console.print(table)

    # Copilot SDK
    sdk_results = [r for r in report.results if r.target_type.value == "copilot-sdk"]
    if sdk_results:
        table = Table(title="Copilot SDK", show_lines=True)
        table.add_column("Target", style="bold")
        table.add_column("Status", justify="center")
        table.add_column("Detail")
        table.add_column("Models")
        table.add_column("Tools")
        table.add_column("Latency")
        for r in sdk_results:
            table.add_row(
                r.target,
                _probe_icon(r.status),
                r.detail or r.error_message or "",
                str(len(r.models_discovered)) if r.models_discovered else _NA,
                str(len(r.tools_discovered)) if r.tools_discovered else _NA,
                _fmt_latency(r.latency_ms),
            )
        console.print(table)

        # Verbose: list discovered models and tools
        if verbose:
            for r in sdk_results:
                if r.models_discovered:
                    _label = "📋 Models discovered" if _USE_EMOJI else "Models discovered"
                    tree = Tree(_label)
                    for m in sorted(r.models_discovered):
                        tree.add(m)
                    console.print(tree)
                if r.tools_discovered:
                    _label = "🔧 Tools discovered" if _USE_EMOJI else "Tools discovered"
                    tree = Tree(_label)
                    for t in sorted(r.tools_discovered):
                        tree.add(t)
                    console.print(tree)

    # MCP server probes
    mcp_results = [
        r for r in report.results if r.target_type.value in ("mcp-http", "mcp-stdio", "mcp-local")
    ]
    if mcp_results:
        table = Table(title="MCP Servers", show_lines=True)
        table.add_column("Server", style="bold")
        table.add_column("Type")
        table.add_column("Status", justify="center")
        table.add_column("Detail")
        table.add_column("Tools")
        table.add_column("Latency")
        for r in sorted(mcp_results, key=lambda x: x.target):
            table.add_row(
                r.target,
                r.target_type.value.replace("mcp-", ""),
                _probe_icon(r.status),
                r.detail or r.error_message or "",
                str(len(r.tools_discovered)) if r.tools_discovered else _NA,
                _fmt_latency(r.latency_ms),
            )
        console.print(table)

        # Verbose: tool names per server
        if verbose:
            for r in mcp_results:
                if r.tools_discovered:
                    _prefix = "🔧" if _USE_EMOJI else "-"
                    tree = Tree(f"{_prefix} {r.target} tools")
                    for t in sorted(r.tools_discovered):
                        tree.add(t)
                    console.print(tree)

    console.print()


def print_log_report(report: LogReport) -> None:
    """Print log analysis results."""

    console.print()
    console.print(
        Panel(
            f"Scanned {report.log_files_scanned} log file(s)\n"
            f"Connected: {len(report.connected_servers)}  "
            f"Errored: {len(report.errored_servers)}  "
            f"Auth errors: {len(report.auth_errors)}",
            title="[bold]Log History[/bold]",
            border_style="blue",
            expand=False,
        )
    )

    # Recent MCP connection events (deduplicated, show latest per server)
    if report.mcp_events:
        # Keep only latest event per server
        latest: dict[str, McpLogEvent] = {}
        for evt in report.mcp_events:
            key = f"{evt.server_name}:{evt.event_type}"
            latest[key] = evt

        table = Table(title="MCP Log Events (recent)", show_lines=True)
        table.add_column("Server", style="bold")
        table.add_column("Event")
        table.add_column("Latency")
        table.add_column("Detail")
        for key in sorted(latest):
            evt = latest[key]
            table.add_row(
                evt.server_name,
                evt.event_type,
                _fmt_latency(evt.latency_ms),
                evt.detail[:80] if evt.detail else "",
            )
        console.print(table)

    # Auth / general errors
    if report.errors:
        table = Table(title="Errors from Logs", show_lines=True)
        table.add_column("Source", style="bold")
        table.add_column("Category")
        table.add_column("Timestamp")
        table.add_column("Message")
        for err in report.errors[:20]:
            table.add_row(
                err.source,
                err.category,
                err.timestamp[:19],
                err.message[:100],
            )
        console.print(table)

    console.print()


def print_plugin_report(results: list[PluginValidation]) -> None:
    """Print plugin validation results."""
    console.print()
    if not results:
        console.print("[dim]No plugins found in installed-plugins/[/dim]")
        return

    table = Table(title="Plugin Validation", show_lines=True)
    table.add_column("Plugin", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("plugin.json")
    table.add_column(".mcp.json")
    table.add_column("Errors")

    for v in sorted(results, key=lambda x: x.name):
        table.add_row(
            v.name,
            _probe_icon(v.status),
            ("✅" if _USE_EMOJI else "[OK]")
            if v.plugin_json_valid
            else (("❌" if _USE_EMOJI else "[ERR]") if v.has_plugin_json else _NA),
            ("✅" if _USE_EMOJI else "[OK]")
            if v.mcp_json_valid
            else (("❌" if _USE_EMOJI else "[ERR]") if v.has_mcp_json else _NA),
            "; ".join(v.errors[:3]) if v.errors else "",
        )
    console.print(table)
    console.print()
