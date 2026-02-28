"""Tests for agent-sync sync engine."""

from __future__ import annotations

from pathlib import Path

from agent_sync.models import (
    CanonicalState,
    Command,
    McpServer,
    McpServerType,
    SyncStatus,
    ToolConfig,
    ToolName,
)
from agent_sync.sync_engine import _mcp_name_normalize, build_sync_report


# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------


class TestMcpNameNormalize:
    def test_lowercase(self):
        assert _mcp_name_normalize("TestServer") == "testserver"

    def test_dash_stripped(self):
        assert _mcp_name_normalize("my-server") == "myserver"

    def test_spaces_stripped(self):
        assert _mcp_name_normalize("My Server") == "myserver"

    def test_already_normalized(self):
        assert _mcp_name_normalize("simple") == "simple"


# ---------------------------------------------------------------------------
# MCP comparison
# ---------------------------------------------------------------------------


class TestMcpSync:
    """Test MCP server sync detection."""

    @staticmethod
    def _canonical(servers: list[McpServer]) -> CanonicalState:
        return CanonicalState(agents_dir=Path("/fake"), mcp_servers=servers)

    @staticmethod
    def _tool_configs(
        copilot_servers: list[McpServer] | None = None,
    ) -> dict[ToolName, ToolConfig]:
        return {
            ToolName.COPILOT: ToolConfig(
                tool=ToolName.COPILOT,
                mcp_servers=copilot_servers or [],
            ),
            ToolName.CLAUDE: ToolConfig(tool=ToolName.CLAUDE),
            ToolName.CODEX: ToolConfig(tool=ToolName.CODEX),
        }

    def test_synced_server(self):
        """Server present in both canonical and tool with matching config."""
        srv = McpServer(
            name="TestServer",
            server_type=McpServerType.HTTP,
            url="https://example.com",
            enabled_for=[ToolName.COPILOT],
        )
        tool_srv = McpServer(
            name="TestServer",
            server_type=McpServerType.HTTP,
            url="https://example.com",
        )
        report = build_sync_report(
            self._canonical([srv]),
            self._tool_configs(copilot_servers=[tool_srv]),
        )
        mcp_items = [i for i in report.items if i.content_type == "mcp"]
        copilot_items = [i for i in mcp_items if i.tool == ToolName.COPILOT]
        synced = [i for i in copilot_items if i.status == SyncStatus.SYNCED]
        assert len(synced) >= 1

    def test_missing_server(self):
        """Server in canonical, not in tool → MISSING."""
        srv = McpServer(
            name="TestServer",
            server_type=McpServerType.HTTP,
            url="https://example.com",
            enabled_for=[ToolName.COPILOT],
        )
        report = build_sync_report(
            self._canonical([srv]),
            self._tool_configs(copilot_servers=[]),
        )
        mcp_items = [i for i in report.items if i.content_type == "mcp"]
        copilot_missing = [
            i for i in mcp_items
            if i.tool == ToolName.COPILOT and i.status == SyncStatus.MISSING
        ]
        assert len(copilot_missing) >= 1

    def test_url_drift(self):
        """URL mismatch between canonical and tool → DRIFT."""
        srv = McpServer(
            name="TestServer",
            server_type=McpServerType.HTTP,
            url="https://example.com/v2",
            enabled_for=[ToolName.COPILOT],
        )
        tool_srv = McpServer(
            name="TestServer",
            server_type=McpServerType.HTTP,
            url="https://example.com/v1",
        )
        report = build_sync_report(
            self._canonical([srv]),
            self._tool_configs(copilot_servers=[tool_srv]),
        )
        mcp_items = [i for i in report.items if i.content_type == "mcp"]
        drift = [
            i for i in mcp_items
            if i.tool == ToolName.COPILOT and i.status == SyncStatus.DRIFT
        ]
        assert len(drift) >= 1

    def test_extra_server(self):
        """Server in tool but not in canonical → EXTRA."""
        extra_srv = McpServer(
            name="ExtraServer",
            server_type=McpServerType.HTTP,
            url="https://extra.com",
        )
        report = build_sync_report(
            self._canonical([]),
            self._tool_configs(copilot_servers=[extra_srv]),
        )
        mcp_items = [i for i in report.items if i.content_type == "mcp"]
        extra = [i for i in mcp_items if i.status == SyncStatus.EXTRA]
        assert len(extra) >= 1
        assert extra[0].item_name == "ExtraServer"

    def test_not_enabled(self):
        """Server not enabled for a tool → NOT_APPLICABLE."""
        srv = McpServer(
            name="TestServer",
            server_type=McpServerType.HTTP,
            url="https://example.com",
            enabled_for=[ToolName.CLAUDE],  # not copilot
        )
        report = build_sync_report(
            self._canonical([srv]),
            self._tool_configs(),
        )
        mcp_items = [i for i in report.items if i.content_type == "mcp"]
        copilot_na = [
            i for i in mcp_items
            if i.tool == ToolName.COPILOT and i.status == SyncStatus.NOT_APPLICABLE
        ]
        assert len(copilot_na) >= 1


# ---------------------------------------------------------------------------
# Command comparison (no canonical commands — Claude vs Codex)
# ---------------------------------------------------------------------------


class TestCommandCrossComparison:
    """Test Claude-vs-Codex command comparison when no canonical commands exist."""

    @staticmethod
    def _make_cmd(slug: str, ns: str, body_hash: str) -> Command:
        return Command(
            name=slug.title(),
            slug=slug,
            namespace=ns,
            body_hash=body_hash,
        )

    def test_matching_commands(self):
        """Both Claude and Codex have same command with same body → SYNCED."""
        canonical = CanonicalState(agents_dir=Path("/fake"))
        tool_configs = {
            ToolName.CLAUDE: ToolConfig(
                tool=ToolName.CLAUDE,
                commands=[self._make_cmd("explore", "opsx", "abc123")],
            ),
            ToolName.CODEX: ToolConfig(
                tool=ToolName.CODEX,
                commands=[self._make_cmd("explore", "opsx", "abc123")],
            ),
            ToolName.COPILOT: ToolConfig(tool=ToolName.COPILOT),
        }
        report = build_sync_report(canonical, tool_configs)
        cmd_items = [i for i in report.items if i.content_type == "command"]
        synced = [i for i in cmd_items if i.status == SyncStatus.SYNCED]
        assert len(synced) >= 1

    def test_body_drift(self):
        """Body hash mismatch → DRIFT."""
        canonical = CanonicalState(agents_dir=Path("/fake"))
        tool_configs = {
            ToolName.CLAUDE: ToolConfig(
                tool=ToolName.CLAUDE,
                commands=[self._make_cmd("explore", "opsx", "hash_a")],
            ),
            ToolName.CODEX: ToolConfig(
                tool=ToolName.CODEX,
                commands=[self._make_cmd("explore", "opsx", "hash_b")],
            ),
            ToolName.COPILOT: ToolConfig(tool=ToolName.COPILOT),
        }
        report = build_sync_report(canonical, tool_configs)
        cmd_items = [i for i in report.items if i.content_type == "command"]
        drift = [i for i in cmd_items if i.status == SyncStatus.DRIFT]
        assert len(drift) >= 1
        assert "mismatch" in drift[0].detail.lower()

    def test_claude_only_command(self):
        """Command in Claude but not Codex → MISSING in Codex."""
        canonical = CanonicalState(agents_dir=Path("/fake"))
        tool_configs = {
            ToolName.CLAUDE: ToolConfig(
                tool=ToolName.CLAUDE,
                commands=[self._make_cmd("special", "opsx", "hash_c")],
            ),
            ToolName.CODEX: ToolConfig(tool=ToolName.CODEX),
            ToolName.COPILOT: ToolConfig(tool=ToolName.COPILOT),
        }
        report = build_sync_report(canonical, tool_configs)
        cmd_items = [i for i in report.items if i.content_type == "command"]
        missing = [
            i for i in cmd_items
            if i.tool == ToolName.CODEX and i.status == SyncStatus.MISSING
        ]
        assert len(missing) >= 1


# ---------------------------------------------------------------------------
# Overall report status
# ---------------------------------------------------------------------------


class TestOverallStatus:
    def test_empty_canonical_empty_tools(self):
        """No content at all → SYNCED (nothing to compare)."""
        canonical = CanonicalState(agents_dir=Path("/fake"))
        tool_configs = {
            ToolName.COPILOT: ToolConfig(tool=ToolName.COPILOT),
            ToolName.CLAUDE: ToolConfig(tool=ToolName.CLAUDE),
            ToolName.CODEX: ToolConfig(tool=ToolName.CODEX),
        }
        report = build_sync_report(canonical, tool_configs)
        # Only infrastructure items (symlink, additional dirs)
        non_infra = [
            i for i in report.items
            if i.content_type not in ("symlink", "config")
        ]
        # With no canonical content, there should be no mcp/skill/command items
        assert all(i.content_type in ("symlink", "config") for i in report.items) or len(non_infra) == 0
