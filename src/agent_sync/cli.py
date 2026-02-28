"""CLI entry point for agent-sync.

Commands:
    agent-sync dashboard  — Interactive Textual terminal UI (default)
    agent-sync check      — Non-interactive Rich console report
    agent-sync fix        — Apply all sync fixes (supports --dry-run)
    agent-sync probe      — Runtime validation of MCP servers and tools

Global flags for agent / CI consumption:
    --json       Emit structured JSON to stdout (suppress Rich output)
    --quiet      Suppress informational output (exit code only for check)
    --tool       Filter results to a single tool
    --type       Filter results to a single content type
"""

from __future__ import annotations

import json
import sys

import click
from rich.console import Console

from agent_sync import __version__
from agent_sync.models import SyncStatus


console = Console()


# ---------------------------------------------------------------------------
# Shared option sets (applied via decorators on sub-commands)
# ---------------------------------------------------------------------------

_TOOL_CHOICE = click.Choice(["copilot", "claude", "codex"], case_sensitive=False)
_TYPE_CHOICE = click.Choice(
    ["mcp", "skill", "command", "plugin", "infrastructure"], case_sensitive=False
)


def _output_options(fn):
    """Add --json and --quiet flags to a command."""
    fn = click.option("--json", "json_output", is_flag=True, help="Emit structured JSON to stdout")(
        fn
    )
    return click.option("--quiet", "-q", is_flag=True, help="Suppress informational output")(fn)


def _filter_options(fn):
    """Add --tool and --type filter flags to a command."""
    fn = click.option("--tool", type=_TOOL_CHOICE, default=None, help="Filter to a single tool")(fn)
    return click.option(
        "--type", "content_type", type=_TYPE_CHOICE, default=None, help="Filter to a content type"
    )(fn)


# ---------------------------------------------------------------------------
# Filtering helpers
# ---------------------------------------------------------------------------


def _filter_items(items, tool: str | None, content_type: str | None):
    """Return items matching --tool and --type filters."""
    from agent_sync.models import ToolName

    filtered = list(items)
    if tool:
        tool_enum = ToolName(tool.lower())
        filtered = [i for i in filtered if i.tool == tool_enum]
    if content_type:
        ct = content_type.lower()
        if ct == "infrastructure":
            filtered = [i for i in filtered if i.content_type in ("symlink", "config")]
        else:
            filtered = [i for i in filtered if i.content_type == ct]
    return filtered


def _filter_probe_results(results, tool: str | None):
    """Return probe results matching --tool filter."""
    from agent_sync.models import ToolName

    if not tool:
        return list(results)
    tool_enum = ToolName(tool.lower())
    return [r for r in results if r.tool == tool_enum]


# ---------------------------------------------------------------------------
# Main group
# ---------------------------------------------------------------------------


_MAIN_EPILOG = """
\b
CONCEPT
  agent-sync compares a canonical source of truth (~/.agents/) against the
  tool-specific configuration files for GitHub Copilot CLI (~/.copilot/),
  Claude Code (~/.claude/), and OpenAI Codex CLI (~/.codex/).  Items
  checked include MCP server definitions, shared skills, commands/prompts,
  and infrastructure (symlinks, additionalDirectories).

\b
TYPICAL AGENT WORKFLOW
  1. agent-sync check --json              # get structured diff report
  2. parse items where status is "drift" or "missing"
  3. agent-sync fix --dry-run --json       # preview what fix would do
  4. agent-sync fix --json                 # apply fixes, get before/after
  5. agent-sync probe --json               # verify runtime connectivity

\b
EXIT CODES
  0  All items in the filtered set are synced / probes are OK.
  1  At least one item is drift/missing (check/fix) or errored (probe).

\b
CONTENT TYPES (--type values)
  mcp              MCP server definitions (mcp.json entries)
  skill            Shared skill folders under ~/.agents/skills/
  command          Commands/prompts synced between Claude and Codex
  plugin           GitHub Copilot plugins from ia-skills-hub
  infrastructure   Symlinks and config entries (e.g. Claude symlink,
                   additionalDirectories)

\b
TOOL NAMES (--tool values)
  copilot   GitHub Copilot CLI (~/.copilot/)
  claude    Claude Code (~/.claude/)
  codex     OpenAI Codex CLI (~/.codex/)
"""


@click.group(invoke_without_command=True, epilog=_MAIN_EPILOG)
@click.version_option(version=__version__, prog_name="agent-sync")
@click.option("--agents-dir", default=None, help="Override default ~/.agents directory")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.pass_context
def main(ctx: click.Context, agents_dir: str | None, verbose: bool) -> None:
    """Agent Sync \u2014 compare and repair AI agent configurations.

    Reads the canonical source of truth from ~/.agents/ and compares it
    against GitHub Copilot CLI, Claude Code, and OpenAI Codex CLI configs.
    Use 'check' to see drift, 'fix' to repair, and 'probe' to verify
    runtime connectivity.  Pass --json to any command for structured output
    suitable for programmatic / agent consumption.
    """
    ctx.ensure_object(dict)
    ctx.obj["agents_dir"] = agents_dir
    ctx.obj["verbose"] = verbose

    # Default to dashboard if no subcommand given
    if ctx.invoked_subcommand is None:
        ctx.invoke(dashboard)


# ---------------------------------------------------------------------------
# dashboard (unchanged)
# ---------------------------------------------------------------------------


@main.command()
@click.pass_context
def dashboard(ctx: click.Context) -> None:
    """Launch the interactive Textual dashboard."""
    from agent_sync.dashboard import run_dashboard

    run_dashboard(agents_dir=ctx.obj.get("agents_dir"))


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------


_CHECK_EPILOG = """
\b
JSON OUTPUT SCHEMA (--json)
  {
    "canonical":    { "agents_dir": "...", "mcp_servers": [...], ... },
    "tool_configs": { "copilot": {...}, "claude": {...}, "codex": {...} },
    "items": [
      {
        "content_type": "mcp"|"skill"|"command"|"symlink"|"config",
        "item_name":    "server-or-item-name",
        "tool":         "copilot"|"claude"|"codex",
        "status":       "synced"|"drift"|"missing"|"extra"|"n/a",
        "detail":       "human-readable explanation",
        "fix_action":   null | {
          "action":       "add-mcp"|"update-mcp"|"remove-mcp"|...,
          "tool":         "copilot"|"claude"|"codex",
          "content_type": "mcp"|"command"|...,
          "target":       "item-name",
          "detail":       "human-readable fix description"
        }
      }, ...
    ],
    "summary": {
      "synced_count":  int,
      "drift_count":   int,
      "missing_count": int,
      "extra_count":   int,
      "fixable_count": int,
      "overall_status": "synced"|"drift"
    }
  }

\b
FIX ACTION TYPES (fix_action.action values)
  add-mcp             Add a canonical MCP server to a tool's config
  update-mcp          Overwrite a drifted MCP server entry
  remove-mcp          Extra server not in canonical (manual decision)
  create-symlink      Create the Claude skills junction
  add-config          Add .agents to Claude additionalDirectories
  write-command       Write a canonical command to a tool
  overwrite-command   Overwrite a drifted command from canonical
  copy-command        Copy a command between Claude and Codex
  reconcile-command   Body differs between Claude and Codex (no canonical)

\b
EXIT CODES
  0  All items in the filtered set have status "synced" or "n/a".
  1  At least one item has status "drift" or "missing".

\b
EXAMPLES
  agent-sync check --json                        # full JSON report
  agent-sync check --json --tool claude           # only Claude items
  agent-sync check --json --tool copilot --type mcp  # Copilot MCP only
  agent-sync check --quiet                        # exit code only
"""


@main.command(epilog=_CHECK_EPILOG)
@_output_options
@_filter_options
@click.pass_context
def check(
    ctx: click.Context, json_output: bool, quiet: bool, tool: str | None, content_type: str | None
) -> None:
    """Compare canonical ~/.agents/ config against all tool configs.

    Scans MCP servers, skills, commands, and infrastructure. Prints a
    Rich table by default, or structured JSON with --json.  Exits 1 if
    any drift or missing items are found in the (optionally filtered) set.
    """
    from agent_sync.scanner import scan_all_tools, scan_canonical
    from agent_sync.serializers import to_dict
    from agent_sync.sync_engine import build_sync_report

    canonical = scan_canonical()
    tool_configs = scan_all_tools()
    report = build_sync_report(canonical, tool_configs)

    # Apply filters
    filtered_items = _filter_items(report.items, tool, content_type)

    if json_output:
        payload = to_dict(report)
        # Replace items list with filtered subset
        payload["items"] = [to_dict(i) for i in filtered_items]
        click.echo(json.dumps(payload, indent=2))
    elif not quiet:
        from agent_sync.console import print_report

        print_report(report, items=filtered_items)

    # Exit with non-zero if filtered set has issues
    has_issues = any(i.status.value in ("drift", "missing") for i in filtered_items)
    if has_issues:
        sys.exit(1)


# ---------------------------------------------------------------------------
# fix
# ---------------------------------------------------------------------------


_FIX_EPILOG = """
\b
IMPORTANT: --tool and --type filter the REPORT output only.
  The fix operation always applies ALL available fixes regardless of
  filters.  To preview, use --dry-run --json first.

\b
JSON OUTPUT SCHEMA (--json)
  {
    "dry_run":        true|false,
    "actions_taken":  ["description of each fix applied", ...],
    "report_before":  { <same schema as 'check --json'> },
    "report_after":   { <same schema as 'check --json'> }  // omitted if dry_run
  }

\b
EXAMPLES
  agent-sync fix --dry-run --json    # preview fixes as JSON
  agent-sync fix --json              # apply and get before/after report
  agent-sync fix --dry-run           # human-readable preview
  agent-sync fix                     # apply and show Rich output
"""


@main.command(epilog=_FIX_EPILOG)
@click.option("--dry-run", is_flag=True, help="Show what would be changed without making changes")
@_output_options
@_filter_options
@click.pass_context
def fix(
    ctx: click.Context,
    dry_run: bool,
    json_output: bool,
    quiet: bool,
    tool: str | None,
    content_type: str | None,
) -> None:
    """Apply all sync fixes to bring tools in line with canonical config.

    Rewrites MCP configs, creates symlinks, and syncs commands based on
    the canonical ~/.agents/ state.  Use --dry-run to preview.
    Note: --tool/--type filter the output report, not the fix scope.
    """
    from agent_sync.scanner import scan_all_tools, scan_canonical
    from agent_sync.serializers import to_dict
    from agent_sync.sync_engine import apply_fixes, build_sync_report

    canonical = scan_canonical()
    tool_configs = scan_all_tools()
    report = build_sync_report(canonical, tool_configs)

    # Show dry-run banner for human mode
    if dry_run and not quiet and not json_output:
        console.print("[bold yellow]DRY RUN[/bold yellow] — no changes will be made\n")

    actions = apply_fixes(report, dry_run=dry_run)

    if json_output:
        # Build before/after for JSON
        report_before = to_dict(report)
        payload: dict = {
            "dry_run": dry_run,
            "actions_taken": actions,
            "report_before": report_before,
        }
        if not dry_run:
            canonical2 = scan_canonical()
            tool_configs2 = scan_all_tools()
            report2 = build_sync_report(canonical2, tool_configs2)
            payload["report_after"] = to_dict(report2)
        click.echo(json.dumps(payload, indent=2))
        return

    if quiet:
        return

    # Check report status, not just actions
    if report.overall_status == SyncStatus.SYNCED:
        console.print("[green]Everything is in sync![/green]")
        return

    if not actions:
        # There are issues but no automated fixes available
        console.print("[yellow]Issues detected but no automated fixes available.[/yellow]")
        console.print(f"  Missing: {report.missing_count}")
        console.print(f"  Drift: {report.drift_count}")
        console.print(f"  Extra: {report.extra_count}")
        console.print("\nRun 'agent-sync check' for details.")
        return

    for action in actions:
        prefix = "Would: " if dry_run else "Done: "
        console.print(f"  • {prefix}{action}")

    console.print()
    if not dry_run:
        console.print(f"[green]Applied {len(actions)} fix(es).[/green]")

        # Re-check after fix
        canonical2 = scan_canonical()
        tool_configs2 = scan_all_tools()
        report2 = build_sync_report(canonical2, tool_configs2)
        if report2.overall_status.value == "synced":
            console.print("[green]All checks pass after fix.[/green]")
        else:
            console.print(
                f"[yellow]Still {report2.drift_count} drift / "
                f"{report2.missing_count} missing after fix.[/yellow]"
            )


# ---------------------------------------------------------------------------
# probe
# ---------------------------------------------------------------------------


_PROBE_EPILOG = """
\b
PROBE TYPES (always run unless skipped)
  cli-version    Checks copilot-cli, claude, codex executables on PATH.
  copilot-sdk    Pings the Copilot SDK, lists models and tools.
                 Skip with --skip-copilot-sdk. Requires [probe] extra.
  mcp-http       Sends HTTP request to each http-type MCP server.
  mcp-stdio      Spawns each stdio/local MCP server process.
                 Skip with --skip-stdio (avoids spawning processes).

\b
OPTIONAL EXTRAS (opt-in via flags)
  --log-history  Parse ~/.copilot/logs/ and ~/.codex/log/ for recent MCP
                 connection events, auth failures, and runtime errors.
  --plugins      Validate plugin.json / .mcp.json manifests in
                 ~/.copilot/installed-plugins/.

\b
JSON OUTPUT SCHEMA (--json)
  {
    "probe": {
      "results": [
        {
          "target":            "server-name or sdk or cli-name",
          "target_type":       "copilot-sdk"|"mcp-http"|"mcp-stdio"|
                               "mcp-local"|"cli-version"|"plugin"|"log-check",
          "tool":              "copilot"|"claude"|"codex"|null,
          "status":            "ok"|"error"|"timeout"|"skipped"|"unavailable",
          "latency_ms":        float|null,
          "tools_discovered":  ["tool-name", ...],
          "models_discovered": ["model-id", ...],
          "error_message":     "" or error text,
          "detail":            "version string or status detail"
        }, ...
      ],
      "plugin_validations": [...],
      "timestamp": "ISO-8601",
      "summary": {
        "ok_count": int, "error_count": int,
        "timeout_count": int, "skipped_count": int,
        "overall_status": "ok"|"error"|"timeout"|"skipped"
      }
    },
    "logs":    { ... }   // only if --log-history
    "plugins": [ ... ]   // only if --plugins
  }

\b
EXIT CODES
  0  All probes in the filtered set returned "ok" or "skipped".
  1  At least one probe returned "error".

\b
EXAMPLES
  agent-sync probe --json                        # full probe as JSON
  agent-sync probe --json --skip-stdio            # skip process spawning
  agent-sync probe --json --tool copilot          # only Copilot probes
  agent-sync probe --json --log-history --plugins # include all extras
"""


@main.command(epilog=_PROBE_EPILOG)
@click.option(
    "--skip-copilot-sdk",
    is_flag=True,
    help="Skip the Copilot SDK ping/models/tools probe",
)
@click.option(
    "--skip-stdio",
    is_flag=True,
    help="Skip stdio/local MCP server probes (they spawn processes)",
)
@click.option(
    "--timeout",
    type=float,
    default=15.0,
    help="Per-probe timeout in seconds (default: 15)",
)
@click.option(
    "--log-history",
    is_flag=True,
    help="Also parse recent Copilot/Codex logs for MCP events and errors",
)
@click.option(
    "--plugins",
    is_flag=True,
    help="Also validate Copilot CLI plugin manifests",
)
@_output_options
@click.option("--tool", type=_TOOL_CHOICE, default=None, help="Filter to a single tool")
@click.pass_context
def probe(
    ctx: click.Context,
    skip_copilot_sdk: bool,
    skip_stdio: bool,
    timeout: float,
    log_history: bool,
    plugins: bool,
    json_output: bool,
    quiet: bool,
    tool: str | None,
) -> None:
    """Verify runtime connectivity to MCP servers and AI tool CLIs.

    Pings each MCP server (HTTP and optionally stdio), checks CLI tool
    versions, and optionally validates Copilot SDK connectivity, log
    health, and plugin manifests.  Pass --json for structured output.
    """
    from agent_sync.prober import run_probe
    from agent_sync.scanner import scan_canonical
    from agent_sync.serializers import to_dict

    canonical = scan_canonical()

    if not quiet and not json_output:
        with console.status("[bold cyan]Running probes…[/bold cyan]"):
            probe_report = run_probe(
                canonical,
                skip_copilot_sdk=skip_copilot_sdk,
                skip_stdio=skip_stdio,
                timeout=timeout,
            )
    else:
        probe_report = run_probe(
            canonical,
            skip_copilot_sdk=skip_copilot_sdk,
            skip_stdio=skip_stdio,
            timeout=timeout,
        )

    # Filter probe results by tool
    filtered_results = _filter_probe_results(probe_report.results, tool)

    # Build optional extras
    log_report_obj = None
    plugin_results_list = None

    if log_history:
        from agent_sync.log_parser import parse_logs

        log_report_obj = parse_logs()

    if plugins:
        from agent_sync.plugin_validator import validate_plugins

        plugin_results_list = validate_plugins()

    if json_output:
        payload: dict = {
            "probe": to_dict(probe_report),
        }
        # Replace results with filtered subset
        payload["probe"]["results"] = [to_dict(r) for r in filtered_results]
        if log_report_obj is not None:
            payload["logs"] = to_dict(log_report_obj)
        if plugin_results_list is not None:
            payload["plugins"] = [to_dict(p) for p in plugin_results_list]
        click.echo(json.dumps(payload, indent=2))
    elif not quiet:
        from agent_sync.console import print_log_report, print_plugin_report, print_probe_report

        print_probe_report(probe_report, verbose=ctx.obj.get("verbose", False))

        if log_report_obj is not None:
            print_log_report(log_report_obj)
        if plugin_results_list is not None:
            print_plugin_report(plugin_results_list)

    # Exit with non-zero if any filtered probes errored
    if any(r.status.value == "error" for r in filtered_results):
        sys.exit(1)


# ---------------------------------------------------------------------------
# config command group
# ---------------------------------------------------------------------------


@main.group()
def config() -> None:
    """Manage ~/.agent-sync.toml user configuration."""


@config.command()
def init() -> None:
    """Generate example ~/.agent-sync.toml with current detected paths."""
    from pathlib import Path
    from agent_sync.user_config import USER_CONFIG_PATH
    from agent_sync.config import HOME
    
    if USER_CONFIG_PATH.exists():
        console.print(f"[yellow]Config file already exists at {USER_CONFIG_PATH}[/yellow]")
        console.print("Run 'agent-sync config show' to view current config")
        sys.exit(1)
    
    # Generate example with common defaults
    example = f"""# Agent-Sync User Configuration
# This file overrides built-in defaults for paths, tool settings, and preferences.
# All settings are optional - delete any section you don't need to customize.

[paths]
# Override directory locations (paths are expanded with ~)
# agents_dir = "~/.agents"
# copilot_dir = "~/.copilot"
# claude_dir = "~/.claude"
# codex_dir = "~/.codex"
# ia_skills_hub = "~/repos/github.com/integralanalytics/ia-skills-hub"

[tools]
# Which tools to sync (comment out to disable a tool)
enabled = ["copilot", "claude", "codex"]
# Don't flag extra servers as drift
# ignore_extra_servers = false

[mcp]
# Servers to ignore during sync checks
# ignore_servers = ["github"]
# Always add MCP servers to user config (not project-specific)
# force_user_scope = true

[scan]
# Additional product workflow directories to scan
# product_dirs = ["~/repos/LoadSEERNext", "~/repos/LSStudio"]
# Skip JSON schema validation for faster scans
# skip_validation = false

[output]
# Output format: "auto", "json", "table", or "dashboard"
# format = "auto"
# Verbosity: "quiet", "normal", or "verbose"
# verbosity = "normal"
# Color: "auto", "always", or "never"
# color = "auto"
"""
    
    USER_CONFIG_PATH.write_text(example, encoding="utf-8")
    console.print(f"[green]✓[/green] Created example config at {USER_CONFIG_PATH}")
    console.print("Edit the file to customize settings, then run 'agent-sync config validate'")


@config.command()
def show() -> None:
    """Display effective configuration (merged defaults + user overrides)."""
    from agent_sync.user_config import get_user_config, USER_CONFIG_PATH
    
    cfg = get_user_config()
    
    console.print(f"\n[bold]Configuration Source:[/bold] {USER_CONFIG_PATH}")
    console.print(f"[dim]File exists: {USER_CONFIG_PATH.exists()}[/dim]\n")
    
    console.print("[bold cyan][paths][/bold cyan]")
    console.print(f"  agents_dir:    {cfg.paths.agents_dir}")
    console.print(f"  copilot_dir:   {cfg.paths.copilot_dir}")
    console.print(f"  claude_dir:    {cfg.paths.claude_dir}")
    console.print(f"  codex_dir:     {cfg.paths.codex_dir}")
    console.print(f"  ia_skills_hub: {cfg.paths.ia_skills_hub or '(auto-discover)'}")
    
    console.print(f"\n[bold cyan][tools][/bold cyan]")
    console.print(f"  enabled:              {cfg.tools.enabled}")
    console.print(f"  ignore_extra_servers: {cfg.tools.ignore_extra_servers}")
    
    console.print(f"\n[bold cyan][mcp][/bold cyan]")
    console.print(f"  ignore_servers:   {cfg.mcp.ignore_servers}")
    console.print(f"  force_user_scope: {cfg.mcp.force_user_scope}")
    
    console.print(f"\n[bold cyan][scan][/bold cyan]")
    console.print(f"  product_dirs:    {cfg.scan.product_dirs}")
    console.print(f"  skip_validation: {cfg.scan.skip_validation}")
    
    console.print(f"\n[bold cyan][output][/bold cyan]")
    console.print(f"  format:    {cfg.output.format}")
    console.print(f"  verbosity: {cfg.output.verbosity}")
    console.print(f"  color:     {cfg.output.color}")


@config.command()
def validate() -> None:
    """Validate ~/.agent-sync.toml syntax and paths."""
    from agent_sync.user_config import USER_CONFIG_PATH, get_user_config, validate_user_config
    
    if not USER_CONFIG_PATH.exists():
        console.print(f"[yellow]No config file found at {USER_CONFIG_PATH}[/yellow]")
        console.print("Run 'agent-sync config init' to create an example config")
        sys.exit(0)
    
    try:
        cfg = get_user_config()
        errors = validate_user_config(cfg)
        
        if errors:
            console.print(f"[red]✗ Config validation failed:[/red]")
            for err in errors:
                console.print(f"  • {err}")
            sys.exit(1)
        else:
            console.print(f"[green]✓ Config is valid[/green]")
            console.print(f"  Path: {USER_CONFIG_PATH}")
            console.print(f"  Tools enabled: {', '.join(cfg.tools.enabled)}")
            
    except Exception as e:
        console.print(f"[red]✗ Failed to load config:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
