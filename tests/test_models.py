"""Tests for agent-sync models."""

from agent_sync.models import (
    CanonicalState,
    Command,
    FixAction,
    FixActionType,
    McpServer,
    McpServerType,
    Skill,
    SyncItem,
    SyncReport,
    SyncStatus,
    ToolConfig,
    ToolName,
)
from pathlib import Path


class TestSyncStatus:
    """Test SyncStatus enum values and string representation."""

    def test_enum_values(self):
        assert SyncStatus.SYNCED.value == "synced"
        assert SyncStatus.DRIFT.value == "drift"
        assert SyncStatus.MISSING.value == "missing"
        assert SyncStatus.EXTRA.value == "extra"
        assert SyncStatus.NOT_APPLICABLE.value == "n/a"


class TestMcpServer:
    """Test McpServer dataclass."""

    def test_basic_http_server(self):
        srv = McpServer(
            name="test-server",
            server_type=McpServerType.HTTP,
            url="https://example.com/mcp",
            enabled_for=[ToolName.COPILOT, ToolName.CLAUDE],
        )
        assert srv.name == "test-server"
        assert srv.server_type == McpServerType.HTTP
        assert srv.url == "https://example.com/mcp"
        assert ToolName.COPILOT in srv.enabled_for
        assert srv.enabled is True
        assert srv.tools == ["*"]

    def test_stdio_server(self):
        srv = McpServer(
            name="local-tool",
            server_type=McpServerType.STDIO,
            command="npx",
            args=["-y", "some-mcp-server"],
            enabled_for=[ToolName.CODEX],
        )
        assert srv.command == "npx"
        assert len(srv.args) == 2
        assert srv.url is None


class TestCommand:
    """Test Command dataclass."""

    def test_command_creation(self):
        cmd = Command(
            name="Explore",
            slug="explore",
            namespace="opsx",
            description="Explore ideas",
            body="Some body text",
            body_hash="abc123",
        )
        assert cmd.slug == "explore"
        assert cmd.namespace == "opsx"
        assert cmd.sync_to == []


class TestSyncReport:
    """Test SyncReport computed properties."""

    def _make_report(self, statuses: list[SyncStatus]) -> SyncReport:
        canonical = CanonicalState(agents_dir=Path("/fake"))
        items = [
            SyncItem(
                content_type="mcp",
                item_name=f"item-{i}",
                tool=ToolName.COPILOT,
                status=s,
            )
            for i, s in enumerate(statuses)
        ]
        return SyncReport(canonical=canonical, items=items)

    def test_all_synced(self):
        report = self._make_report([SyncStatus.SYNCED, SyncStatus.SYNCED])
        assert report.synced_count == 2
        assert report.drift_count == 0
        assert report.missing_count == 0
        assert report.overall_status == SyncStatus.SYNCED

    def test_with_drift(self):
        report = self._make_report([SyncStatus.SYNCED, SyncStatus.DRIFT])
        assert report.drift_count == 1
        assert report.overall_status == SyncStatus.DRIFT

    def test_with_missing(self):
        report = self._make_report([SyncStatus.MISSING])
        assert report.missing_count == 1
        assert report.overall_status == SyncStatus.DRIFT  # any issue -> DRIFT

    def test_fixable_count(self):
        canonical = CanonicalState(agents_dir=Path("/fake"))
        items = [
            SyncItem(
                content_type="mcp",
                item_name="a",
                tool=ToolName.COPILOT,
                status=SyncStatus.MISSING,
                fix_action=FixAction(
                    action=FixActionType.ADD_MCP,
                    tool=ToolName.COPILOT,
                    content_type="mcp",
                    target="a",
                    detail="write MCP config",
                ),
            ),
            SyncItem(
                content_type="mcp",
                item_name="b",
                tool=ToolName.COPILOT,
                status=SyncStatus.SYNCED,
            ),
        ]
        report = SyncReport(canonical=canonical, items=items)
        assert report.fixable_count == 1

    def test_empty_report(self):
        report = self._make_report([])
        assert report.synced_count == 0
        assert report.overall_status == SyncStatus.SYNCED
