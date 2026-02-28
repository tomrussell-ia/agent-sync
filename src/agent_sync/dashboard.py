"""Textual TUI dashboard for agent-sync.

Interactive terminal UI with panels for MCP servers, skills, commands,
product workflows, and tool configuration summaries.
"""

from __future__ import annotations

from datetime import datetime

from rich.table import Table
from rich.text import Text
from rich.tree import Tree
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane

from agent_sync.models import (
    CanonicalState,
    SyncReport,
    SyncStatus,
    ToolName,
)
from agent_sync.scanner import scan_all_tools, scan_canonical
from agent_sync.sync_engine import apply_fixes, build_sync_report


# ---------------------------------------------------------------------------
# Status rendering helpers
# ---------------------------------------------------------------------------

STATUS_ICONS = {
    SyncStatus.SYNCED: ("✅", "green"),
    SyncStatus.DRIFT: ("⚠️", "yellow"),
    SyncStatus.MISSING: ("❌", "red"),
    SyncStatus.EXTRA: ("➕", "cyan"),
    SyncStatus.NOT_APPLICABLE: ("—", "dim"),
}


def _icon(status: SyncStatus) -> Text:
    icon, color = STATUS_ICONS[status]
    return Text(icon, style=color)


def _status_text(status: SyncStatus) -> Text:
    icon, color = STATUS_ICONS[status]
    return Text(f"{icon} {status.value}", style=color)


# ---------------------------------------------------------------------------
# Panel builders
# ---------------------------------------------------------------------------


def build_overview_table(report: SyncReport) -> Table:
    """Summary card showing overall sync health."""
    table = Table(title="Sync Overview", expand=True, show_lines=True)
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    total = len(report.items)
    table.add_row("Total checks", str(total))
    table.add_row("✅ Synced", Text(str(report.synced_count), style="green"))
    table.add_row("⚠️  Drift", Text(str(report.drift_count), style="yellow"))
    table.add_row("❌ Missing", Text(str(report.missing_count), style="red"))
    table.add_row("➕ Extra", Text(str(report.extra_count), style="cyan"))
    table.add_row("🔧 Fixable", Text(str(report.fixable_count), style="blue"))
    table.add_row(
        "Overall",
        _status_text(report.overall_status),
    )
    table.add_row("Scanned at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    return table


def build_mcp_table(report: SyncReport) -> Table:
    """Table of MCP server sync status per tool."""
    table = Table(title="MCP Servers", expand=True, show_lines=True)
    table.add_column("Server", style="bold", no_wrap=True)
    table.add_column("Type", style="dim")
    table.add_column("Copilot", justify="center")
    table.add_column("Claude", justify="center")
    table.add_column("Codex", justify="center")
    table.add_column("Detail")

    # Group items by server name
    mcp_items = [i for i in report.items if i.content_type == "mcp"]
    servers: dict[str, dict[ToolName, any]] = {}  # type: ignore[type-arg]
    for item in mcp_items:
        servers.setdefault(item.item_name, {})[item.tool] = item

    # Also get type from canonical
    type_map: dict[str, str] = {}
    for srv in report.canonical.mcp_servers:
        type_map[srv.name] = srv.server_type.value

    for name, tools in sorted(servers.items()):
        copilot = tools.get(ToolName.COPILOT)
        claude = tools.get(ToolName.CLAUDE)
        codex = tools.get(ToolName.CODEX)

        details: list[str] = []
        for item in tools.values():
            if item.detail:
                details.append(item.detail)

        table.add_row(
            name,
            type_map.get(name, "?"),
            _icon(copilot.status) if copilot else Text("—", style="dim"),
            _icon(claude.status) if claude else Text("—", style="dim"),
            _icon(codex.status) if codex else Text("—", style="dim"),
            "; ".join(details[:2]) if details else "",
        )

    return table


def build_skills_tree(report: SyncReport) -> Tree:
    """Tree view of shared skills and their distribution."""
    tree = Tree("📚 Shared Skills", guide_style="dim")

    skill_items = [i for i in report.items if i.content_type == "skill"]
    # Group by skill name
    skills: dict[str, dict[ToolName, any]] = {}  # type: ignore[type-arg]
    for item in skill_items:
        skills.setdefault(item.item_name, {})[item.tool] = item

    # Get source info from canonical
    source_map: dict[str, str] = {}
    for skill in report.canonical.skills:
        source_map[skill.name] = skill.source if skill.source != "local" else ""

    for name, tools in sorted(skills.items()):
        source = source_map.get(name, "")
        source_tag = f" [{source}]" if source else ""

        statuses: list[str] = []
        for tn in [ToolName.COPILOT, ToolName.CLAUDE, ToolName.CODEX]:
            item = tools.get(tn)
            if item:
                icon, _ = STATUS_ICONS[item.status]
                statuses.append(f"{tn.value}:{icon}")

        label = f"{name}{source_tag}  {'  '.join(statuses)}"
        tree.add(label)

    return tree


def build_commands_table(report: SyncReport) -> Table:
    """Table of command/prompt sync status."""
    table = Table(title="Commands / Prompts", expand=True, show_lines=True)
    table.add_column("Command", style="bold", no_wrap=True)
    table.add_column("Claude", justify="center")
    table.add_column("Codex", justify="center")
    table.add_column("Detail")

    cmd_items = [i for i in report.items if i.content_type == "command"]
    commands: dict[str, dict[ToolName, any]] = {}  # type: ignore[type-arg]
    for item in cmd_items:
        commands.setdefault(item.item_name, {})[item.tool] = item

    for name, tools in sorted(commands.items()):
        claude = tools.get(ToolName.CLAUDE)
        codex = tools.get(ToolName.CODEX)

        details: list[str] = []
        for item in tools.values():
            if item.detail:
                details.append(item.detail)

        table.add_row(
            name,
            _icon(claude.status) if claude else Text("—", style="dim"),
            _icon(codex.status) if codex else Text("—", style="dim"),
            "; ".join(details[:2]) if details else "",
        )

    return table


def build_workflows_tree(report: SyncReport) -> Tree:
    """Tree view of product workflows."""
    tree = Tree("🏗️  Product Workflows", guide_style="dim")

    for wf in report.canonical.product_workflows:
        branch = tree.add(f"[bold]{wf.name}[/bold]")
        branch.add(f"Agents: {len(wf.agents)}")
        branch.add(f"Prompts: {len(wf.prompts)}")
        branch.add(f"Instructions: {len(wf.instructions)}")
        branch.add(f"Skills: {len(wf.skills)}")
        if wf.copilot_plugin_installed:
            branch.add(f"Copilot Plugin: ✅ v{wf.copilot_plugin_version}")
        else:
            branch.add("Copilot Plugin: —")

        # Expand agents list
        if wf.agents:
            ag_branch = branch.add("Agent list")
            for ag in wf.agents:
                ag_branch.add(ag.name)

    return tree


def build_tool_configs_table(report: SyncReport) -> Table:
    """Summary table of each tool's configuration."""
    table = Table(title="Tool Configurations", expand=True, show_lines=True)
    table.add_column("Tool", style="bold")
    table.add_column("Model")
    table.add_column("MCP Servers", justify="right")
    table.add_column("Skills", justify="right")
    table.add_column("Commands", justify="right")
    table.add_column("Details")

    for tool_name, tc in sorted(report.tool_configs.items(), key=lambda x: x[0].value):
        details: list[str] = []
        for k, v in tc.extra_info.items():
            if v:
                details.append(f"{k}={v}")

        table.add_row(
            tool_name.value.title(),
            tc.model or "—",
            str(len(tc.mcp_servers)),
            str(len(tc.skills)),
            str(len(tc.commands)),
            ", ".join(details[:3]) if details else "",
        )

    # Add canonical row
    c = report.canonical
    table.add_row(
        Text("Canonical (.agents/)", style="bold cyan"),
        "—",
        str(len(c.mcp_servers)),
        str(len(c.skills)),
        str(len(c.commands)),
        f"workflows={len(c.product_workflows)}",
    )

    return table


def build_infra_table(report: SyncReport) -> Table:
    """Infrastructure checks (symlinks, config entries)."""
    table = Table(title="Infrastructure Checks", expand=True, show_lines=True)
    table.add_column("Check", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Detail")

    infra_types = {"symlink", "config"}
    for item in report.items:
        if item.content_type in infra_types:
            table.add_row(
                item.item_name,
                _icon(item.status),
                item.detail,
            )

    return table


# ---------------------------------------------------------------------------
# Textual App
# ---------------------------------------------------------------------------


class SyncDashboard(App):
    """Agent Sync Dashboard — Textual TUI application."""

    TITLE = "Agent Sync Dashboard"
    SUB_TITLE = "AI Tool Configuration Manager"
    CSS = """
    Screen {
        background: $surface;
    }
    #overview {
        height: auto;
        margin: 1 2;
    }
    .panel {
        margin: 0 1;
        padding: 1;
    }
    TabbedContent {
        margin: 0 1;
    }
    """
    BINDINGS = [
        Binding("f", "fix", "Fix All"),
        Binding("d", "dry_run", "Dry Run"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, agents_dir: str | None = None) -> None:
        super().__init__()
        self._agents_dir = agents_dir
        self._report: SyncReport | None = None

    def _scan(self) -> SyncReport:
        """Run the full scan and build report."""
        canonical = scan_canonical()
        tool_configs = scan_all_tools()
        return build_sync_report(canonical, tool_configs)

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Static(id="overview")
            with TabbedContent():
                with TabPane("MCP Servers", id="tab-mcp"):
                    yield Static(id="mcp-panel", classes="panel")
                with TabPane("Skills", id="tab-skills"):
                    yield Static(id="skills-panel", classes="panel")
                with TabPane("Commands", id="tab-commands"):
                    yield Static(id="commands-panel", classes="panel")
                with TabPane("Workflows", id="tab-workflows"):
                    yield Static(id="workflows-panel", classes="panel")
                with TabPane("Tools", id="tab-tools"):
                    yield Static(id="tools-panel", classes="panel")
                with TabPane("Infrastructure", id="tab-infra"):
                    yield Static(id="infra-panel", classes="panel")
                with TabPane("Fix Log", id="tab-log"):
                    yield Static(id="log-panel", classes="panel")
        yield Footer()

    def on_mount(self) -> None:
        self.action_refresh()

    def action_refresh(self) -> None:
        """Rescan all configs and refresh the dashboard."""
        self._report = self._scan()
        r = self._report

        self.query_one("#overview", Static).update(build_overview_table(r))
        self.query_one("#mcp-panel", Static).update(build_mcp_table(r))
        self.query_one("#skills-panel", Static).update(build_skills_tree(r))
        self.query_one("#commands-panel", Static).update(build_commands_table(r))
        self.query_one("#workflows-panel", Static).update(build_workflows_tree(r))
        self.query_one("#tools-panel", Static).update(build_tool_configs_table(r))
        self.query_one("#infra-panel", Static).update(build_infra_table(r))

        self.sub_title = f"Scanned {datetime.now():%H:%M:%S} — {r.overall_status.value}"

    def action_fix(self) -> None:
        """Apply all fixes."""
        if not self._report:
            return
        actions = apply_fixes(self._report, dry_run=False)
        log_text = "\n".join(f"• {a}" for a in actions) if actions else "No fixes needed."
        self.query_one("#log-panel", Static).update(log_text)
        # Re-scan after fixes
        self.action_refresh()

    def action_dry_run(self) -> None:
        """Show what fixes would be applied."""
        if not self._report:
            return
        actions = apply_fixes(self._report, dry_run=True)
        log_text = "\n".join(f"• {a}" for a in actions) if actions else "Everything in sync."
        self.query_one("#log-panel", Static).update(f"[DRY RUN]\n{log_text}")


def run_dashboard(agents_dir: str | None = None) -> None:
    """Launch the Textual dashboard."""
    app = SyncDashboard(agents_dir=agents_dir)
    app.run()
