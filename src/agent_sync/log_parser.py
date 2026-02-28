"""Parse tool log files for MCP connection events and errors.

Scans Copilot CLI logs (``~/.copilot/logs/``) and Codex logs
(``~/.codex/log/``) for patterns related to MCP server lifecycle,
authentication failures, and runtime errors.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from agent_sync.config import CODEX_DIR, COPILOT_DIR


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class McpLogEvent:
    """A single MCP-related event extracted from a log file."""

    timestamp: str
    server_name: str
    event_type: str  # "connected", "errored", "starting", "creating", "connecting"
    detail: str = ""
    latency_ms: float | None = None


@dataclass
class LogError:
    """A general error extracted from a tool log file."""

    timestamp: str
    source: str  # "copilot" or "codex"
    category: str  # "auth", "mcp", "general"
    message: str


@dataclass
class LogReport:
    """Aggregated log analysis results."""

    mcp_events: list[McpLogEvent] = field(default_factory=list)
    errors: list[LogError] = field(default_factory=list)
    log_files_scanned: int = 0

    @property
    def connected_servers(self) -> list[str]:
        """Server names that have at least one 'connected' event."""
        return list({e.server_name for e in self.mcp_events if e.event_type == "connected"})

    @property
    def errored_servers(self) -> list[str]:
        """Server names that have at least one 'errored' event."""
        return list({e.server_name for e in self.mcp_events if e.event_type == "errored"})

    @property
    def auth_errors(self) -> list[LogError]:
        return [e for e in self.errors if e.category == "auth"]


# ---------------------------------------------------------------------------
# Copilot log patterns
# ---------------------------------------------------------------------------

# "MCP client for Context7 connected, took 1794ms"
_RE_MCP_CONNECTED = re.compile(
    r"^(?P<ts>[\dT:.Z-]+)\s+\[ERROR\]\s+"
    r"MCP client for (?P<name>\S+) connected,\s+took (?P<ms>\d+)ms$"
)

# "MCP client for Context7 errored Error: SSE stream disconnected: ..."
_RE_MCP_ERRORED = re.compile(
    r"^(?P<ts>[\dT:.Z-]+)\s+\[ERROR\]\s+"
    r"MCP client for (?P<name>\S+) errored\s+(?P<detail>.+)$"
)

# "Starting remote MCP client for GitBooks-LoadSEER-Docs with url: ..."
_RE_MCP_STARTING = re.compile(
    r"^(?P<ts>[\dT:.Z-]+)\s+\[ERROR\]\s+"
    r"Starting (?:remote )?MCP client for (?P<name>\S+)"
)

# "Connecting MCP client for GitBooks-LoadSEER-Docs..."
_RE_MCP_CONNECTING = re.compile(
    r"^(?P<ts>[\dT:.Z-]+)\s+\[ERROR\]\s+"
    r"Connecting MCP client for (?P<name>\S+)"
)


def _parse_copilot_log(path: Path) -> tuple[list[McpLogEvent], list[LogError]]:
    """Parse a single Copilot process log file."""
    events: list[McpLogEvent] = []
    errors: list[LogError] = []

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return events, errors

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        # Connected
        m = _RE_MCP_CONNECTED.match(line)
        if m:
            events.append(
                McpLogEvent(
                    timestamp=m.group("ts"),
                    server_name=m.group("name"),
                    event_type="connected",
                    latency_ms=float(m.group("ms")),
                )
            )
            continue

        # Errored
        m = _RE_MCP_ERRORED.match(line)
        if m:
            events.append(
                McpLogEvent(
                    timestamp=m.group("ts"),
                    server_name=m.group("name"),
                    event_type="errored",
                    detail=m.group("detail"),
                )
            )
            continue

        # Starting
        m = _RE_MCP_STARTING.match(line)
        if m:
            events.append(
                McpLogEvent(
                    timestamp=m.group("ts"),
                    server_name=m.group("name"),
                    event_type="starting",
                )
            )
            continue

        # Connecting
        m = _RE_MCP_CONNECTING.match(line)
        if m:
            events.append(
                McpLogEvent(
                    timestamp=m.group("ts"),
                    server_name=m.group("name").rstrip("."),
                    event_type="connecting",
                )
            )

    return events, errors


# ---------------------------------------------------------------------------
# Codex log patterns
# ---------------------------------------------------------------------------

# "2026-01-27T20:08:54.828398Z ERROR codex_core::auth: Failed to refresh token: ..."
_RE_CODEX_AUTH_ERROR = re.compile(r"^(?P<ts>[\dT:.Z-]+)\s+ERROR\s+codex_core::auth:\s+(?P<msg>.+)$")

# "2026-01-27T... ERROR codex_core::models_manager::manager: ..."
_RE_CODEX_MODEL_ERROR = re.compile(
    r"^(?P<ts>[\dT:.Z-]+)\s+ERROR\s+codex_core::(?P<module>[^:]+).*?:\s+(?P<msg>.+)$"
)


def _parse_codex_log(path: Path) -> tuple[list[McpLogEvent], list[LogError]]:
    """Parse the Codex TUI log file."""
    events: list[McpLogEvent] = []
    errors: list[LogError] = []

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return events, errors

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        # Auth errors
        m = _RE_CODEX_AUTH_ERROR.match(line)
        if m:
            errors.append(
                LogError(
                    timestamp=m.group("ts"),
                    source="codex",
                    category="auth",
                    message=m.group("msg")[:200],
                )
            )
            continue

        # Other errors
        m = _RE_CODEX_MODEL_ERROR.match(line)
        if m and "auth" not in m.group("module"):
            errors.append(
                LogError(
                    timestamp=m.group("ts"),
                    source="codex",
                    category="general",
                    message=m.group("msg")[:200],
                )
            )

    return events, errors


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_logs(*, max_copilot_logs: int = 5) -> LogReport:
    """Parse recent tool logs and return an aggregated report.

    Parameters
    ----------
    max_copilot_logs:
        Maximum number of recent Copilot log files to scan (newest first).
    """
    report = LogReport()

    # Copilot logs — newest first
    copilot_log_dir = COPILOT_DIR / "logs"
    if copilot_log_dir.is_dir():
        log_files = sorted(
            copilot_log_dir.glob("process-*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for log_file in log_files[:max_copilot_logs]:
            events, errors = _parse_copilot_log(log_file)
            report.mcp_events.extend(events)
            report.errors.extend(errors)
            report.log_files_scanned += 1

    # Codex log
    codex_log = CODEX_DIR / "log" / "codex-tui.log"
    if codex_log.is_file():
        events, errors = _parse_codex_log(codex_log)
        report.mcp_events.extend(events)
        report.errors.extend(errors)
        report.log_files_scanned += 1

    return report
