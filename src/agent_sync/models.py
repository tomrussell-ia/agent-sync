"""Data models for agent-sync tool.

Typed dataclasses representing MCP servers, skills, commands, agents,
tool configurations, product workflows, and sync state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ToolName(StrEnum):
    """Supported AI coding tools."""

    COPILOT = "copilot"
    CLAUDE = "claude"
    CODEX = "codex"
    VSCODE = "vscode"


class SyncStatus(StrEnum):
    """Sync comparison result for a single item."""

    SYNCED = "synced"  # canonical == tool-specific
    DRIFT = "drift"  # tool-specific exists but differs
    MISSING = "missing"  # canonical exists but tool-specific does not
    EXTRA = "extra"  # tool-specific exists but canonical does not
    NOT_APPLICABLE = "n/a"  # tool doesn't support this content type


class McpServerType(StrEnum):
    """Transport type for an MCP server connection."""

    HTTP = "http"
    STDIO = "stdio"
    LOCAL = "local"


class ProbeStatus(StrEnum):
    """Result of a runtime probe against a target."""

    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"
    UNAVAILABLE = "unavailable"


class ProbeTargetType(StrEnum):
    """What kind of entity was probed."""

    COPILOT_SDK = "copilot-sdk"
    MCP_HTTP = "mcp-http"
    MCP_STDIO = "mcp-stdio"
    MCP_LOCAL = "mcp-local"
    PLUGIN = "plugin"
    LOG_CHECK = "log-check"
    CLI_VERSION = "cli-version"


class FixActionType(StrEnum):
    """Machine-parseable category for an auto-fix action."""

    ADD_MCP = "add-mcp"
    UPDATE_MCP = "update-mcp"
    REMOVE_MCP = "remove-mcp"
    CREATE_SYMLINK = "create-symlink"
    ADD_CONFIG = "add-config"
    WRITE_COMMAND = "write-command"
    OVERWRITE_COMMAND = "overwrite-command"
    COPY_COMMAND = "copy-command"
    RECONCILE_COMMAND = "reconcile-command"
    INSTALL_PLUGIN = "install-plugin"


# ---------------------------------------------------------------------------
# Content items
# ---------------------------------------------------------------------------


@dataclass
class McpServer:
    """A single MCP server definition."""

    name: str
    server_type: McpServerType
    url: str | None = None
    command: str | None = None
    args: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)
    tools: list[str] = field(default_factory=lambda: ["*"])
    enabled_for: list[ToolName] = field(default_factory=list)
    enabled: bool = True


@dataclass
class Skill:
    """A skill folder reference."""

    name: str
    path: Path
    description: str = ""
    source: str = "local"
    source_type: str = "local"
    source_url: str = ""
    skill_path: str = ""
    folder_hash: str = ""
    installed_at: str = ""
    updated_at: str = ""


@dataclass
class Command:
    """A command/prompt file definition (canonical superset frontmatter)."""

    name: str
    slug: str  # filename without extension, e.g. "explore"
    namespace: str  # e.g. "opsx"
    description: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    argument_hint: str = ""
    sync_to: list[ToolName] = field(default_factory=list)
    body: str = ""  # content below frontmatter
    body_hash: str = ""  # sha256 of body for drift detection
    source_path: Path | None = None


@dataclass
class Agent:
    """An agent definition file."""

    name: str
    path: Path
    format: str = "markdown"  # "markdown" (.agent.md) or "yaml" (openai.yaml)


@dataclass
class Plugin:
    """A Copilot plugin available in ia-skills-hub marketplace."""

    name: str
    path: Path
    description: str = ""
    version: str = ""
    category: str = ""


@dataclass
class ProductWorkflow:
    """A product-specific workflow directory under .agents/."""

    name: str
    path: Path
    agents: list[Agent] = field(default_factory=list)
    prompts: list[Path] = field(default_factory=list)
    instructions: list[Path] = field(default_factory=list)
    skills: list[Skill] = field(default_factory=list)
    copilot_plugin_installed: bool = False
    copilot_plugin_version: str = ""


# ---------------------------------------------------------------------------
# Per-tool scan results
# ---------------------------------------------------------------------------


@dataclass
class ToolConfig:
    """Scanned state of a single tool's configuration."""

    tool: ToolName
    config_path: Path | None = None
    mcp_servers: list[McpServer] = field(default_factory=list)
    skills: list[Skill] = field(default_factory=list)
    commands: list[Command] = field(default_factory=list)
    agents: list[Agent] = field(default_factory=list)
    model: str = ""
    extra_info: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Canonical state (central .agents/)
# ---------------------------------------------------------------------------


@dataclass
class CanonicalState:
    """Full state read from the canonical .agents/ directory."""

    agents_dir: Path
    mcp_servers: list[McpServer] = field(default_factory=list)
    skills: list[Skill] = field(default_factory=list)
    commands: list[Command] = field(default_factory=list)
    product_workflows: list[ProductWorkflow] = field(default_factory=list)
    available_plugins: list[Plugin] = field(default_factory=list)
    skill_lock: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Fix actions
# ---------------------------------------------------------------------------


@dataclass
class FixAction:
    """Structured description of an auto-fix action.

    ``action`` is the machine-parseable verb; ``detail`` is a short
    human-readable sentence for display.
    """

    action: FixActionType
    tool: ToolName
    content_type: str  # "mcp", "skill", "command", "infrastructure"
    target: str  # item name affected
    detail: str = ""  # human-readable description


# ---------------------------------------------------------------------------
# Sync comparison results
# ---------------------------------------------------------------------------


@dataclass
class SyncItem:
    """One comparison between canonical and tool-specific content."""

    content_type: str  # "mcp", "skill", "command"
    item_name: str
    tool: ToolName
    status: SyncStatus
    detail: str = ""
    fix_action: FixAction | None = None  # structured auto-fix descriptor


@dataclass
class SyncReport:
    """Full sync report across all tools."""

    canonical: CanonicalState
    tool_configs: dict[ToolName, ToolConfig] = field(default_factory=dict)
    items: list[SyncItem] = field(default_factory=list)

    @property
    def synced_count(self) -> int:
        return sum(1 for i in self.items if i.status == SyncStatus.SYNCED)

    @property
    def drift_count(self) -> int:
        return sum(1 for i in self.items if i.status == SyncStatus.DRIFT)

    @property
    def missing_count(self) -> int:
        return sum(1 for i in self.items if i.status == SyncStatus.MISSING)

    @property
    def extra_count(self) -> int:
        return sum(1 for i in self.items if i.status == SyncStatus.EXTRA)

    @property
    def fixable_count(self) -> int:
        return sum(1 for i in self.items if i.fix_action is not None)

    @property
    def overall_status(self) -> SyncStatus:
        if self.drift_count or self.missing_count or self.extra_count:
            return SyncStatus.DRIFT
        return SyncStatus.SYNCED


# ---------------------------------------------------------------------------
# Probe / runtime validation models
# ---------------------------------------------------------------------------


@dataclass
class ProbeResult:
    """Result of probing a single target (MCP server, Copilot SDK, plugin, etc.)."""

    target: str  # e.g. server name, "copilot-sdk", plugin name
    target_type: ProbeTargetType
    tool: ToolName | None = None  # which tool this is relevant to
    status: ProbeStatus = ProbeStatus.SKIPPED
    latency_ms: float | None = None
    tools_discovered: list[str] = field(default_factory=list)
    models_discovered: list[str] = field(default_factory=list)
    agents_discovered: list[str] = field(default_factory=list)
    error_message: str = ""
    detail: str = ""


@dataclass
class PluginValidation:
    """Validation result for a Copilot CLI plugin directory."""

    name: str
    path: Path
    has_plugin_json: bool = False
    has_mcp_json: bool = False
    plugin_json_valid: bool = False
    mcp_json_valid: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def status(self) -> ProbeStatus:
        if self.errors:
            return ProbeStatus.ERROR
        if not self.has_plugin_json:
            return ProbeStatus.UNAVAILABLE
        return ProbeStatus.OK


@dataclass
class ProbeReport:
    """Full runtime probe report."""

    results: list[ProbeResult] = field(default_factory=list)
    plugin_validations: list[PluginValidation] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def ok_count(self) -> int:
        return sum(1 for r in self.results if r.status == ProbeStatus.OK)

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.results if r.status == ProbeStatus.ERROR)

    @property
    def timeout_count(self) -> int:
        return sum(1 for r in self.results if r.status == ProbeStatus.TIMEOUT)

    @property
    def skipped_count(self) -> int:
        return sum(1 for r in self.results if r.status == ProbeStatus.SKIPPED)

    @property
    def overall_status(self) -> ProbeStatus:
        if self.error_count:
            return ProbeStatus.ERROR
        if self.timeout_count:
            return ProbeStatus.TIMEOUT
        if self.ok_count:
            return ProbeStatus.OK
        return ProbeStatus.SKIPPED
