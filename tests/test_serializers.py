"""Tests for agent_sync.serializers — to_dict / to_json round-trips."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_sync.log_parser import LogError, LogReport, McpLogEvent
from agent_sync.models import (
    CanonicalState,
    FixAction,
    FixActionType,
    McpServer,
    McpServerType,
    PluginValidation,
    ProbeReport,
    ProbeResult,
    ProbeStatus,
    ProbeTargetType,
    Skill,
    SyncItem,
    SyncReport,
    SyncStatus,
    ToolConfig,
    ToolName,
)
from agent_sync.serializers import to_dict, to_json


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_sync_report(items: list[SyncItem] | None = None) -> SyncReport:
    return SyncReport(
        canonical=CanonicalState(agents_dir=Path("C:/Users/Test/.agents")),
        tool_configs={
            ToolName.CLAUDE: ToolConfig(tool=ToolName.CLAUDE, config_path=Path("~/.claude")),
        },
        items=items or [],
    )


# ---------------------------------------------------------------------------
# to_dict basics
# ---------------------------------------------------------------------------


class TestToDict:
    """Core to_dict behaviour: Enum, Path, nested structures."""

    def test_rejects_non_dataclass(self):
        with pytest.raises(TypeError, match="Expected a dataclass"):
            to_dict({"not": "a dataclass"})

    def test_rejects_class_itself(self):
        with pytest.raises(TypeError, match="Expected a dataclass"):
            to_dict(SyncReport)

    def test_enum_becomes_value(self):
        item = SyncItem(
            content_type="mcp",
            item_name="test-srv",
            tool=ToolName.COPILOT,
            status=SyncStatus.SYNCED,
        )
        d = to_dict(item)
        assert d["tool"] == "copilot"
        assert d["status"] == "synced"

    def test_path_becomes_string(self):
        skill = Skill(name="my-skill", path=Path("C:/Users/Test/.agents/skills/my-skill"))
        d = to_dict(skill)
        assert isinstance(d["path"], str)
        assert "my-skill" in d["path"]

    def test_nested_enum_list(self):
        srv = McpServer(
            name="srv",
            server_type=McpServerType.HTTP,
            url="https://example.com",
            enabled_for=[ToolName.COPILOT, ToolName.CLAUDE],
        )
        d = to_dict(srv)
        assert d["enabled_for"] == ["copilot", "claude"]
        assert d["server_type"] == "http"

    def test_none_fix_action(self):
        item = SyncItem(
            content_type="mcp",
            item_name="srv",
            tool=ToolName.COPILOT,
            status=SyncStatus.SYNCED,
        )
        d = to_dict(item)
        assert d["fix_action"] is None

    def test_fix_action_serialized(self):
        fa = FixAction(
            action=FixActionType.ADD_MCP,
            tool=ToolName.CLAUDE,
            content_type="mcp",
            target="my-server",
            detail="Add my-server to claude MCP config",
        )
        item = SyncItem(
            content_type="mcp",
            item_name="my-server",
            tool=ToolName.CLAUDE,
            status=SyncStatus.MISSING,
            fix_action=fa,
        )
        d = to_dict(item)
        assert d["fix_action"]["action"] == "add-mcp"
        assert d["fix_action"]["tool"] == "claude"
        assert d["fix_action"]["target"] == "my-server"


# ---------------------------------------------------------------------------
# Computed properties / "summary" key
# ---------------------------------------------------------------------------


class TestComputedProperties:
    """Verify that @property fields appear in the serialized 'summary'."""

    def test_sync_report_summary(self):
        items = [
            SyncItem("mcp", "a", ToolName.COPILOT, SyncStatus.SYNCED),
            SyncItem("mcp", "b", ToolName.COPILOT, SyncStatus.DRIFT, fix_action=FixAction(
                FixActionType.UPDATE_MCP, ToolName.COPILOT, "mcp", "b", "fix b"
            )),
            SyncItem("mcp", "c", ToolName.COPILOT, SyncStatus.MISSING, fix_action=FixAction(
                FixActionType.ADD_MCP, ToolName.COPILOT, "mcp", "c", "fix c"
            )),
        ]
        report = _minimal_sync_report(items)
        d = to_dict(report)
        s = d["summary"]
        assert s["synced_count"] == 1
        assert s["drift_count"] == 1
        assert s["missing_count"] == 1
        assert s["extra_count"] == 0
        assert s["fixable_count"] == 2
        assert s["overall_status"] == "drift"

    def test_probe_report_summary(self):
        report = ProbeReport(results=[
            ProbeResult("sdk", ProbeTargetType.COPILOT_SDK, status=ProbeStatus.OK),
            ProbeResult("srv", ProbeTargetType.MCP_HTTP, status=ProbeStatus.ERROR, error_message="boom"),
        ])
        d = to_dict(report)
        s = d["summary"]
        assert s["ok_count"] == 1
        assert s["error_count"] == 1
        assert s["overall_status"] == "error"

    def test_plugin_validation_summary(self):
        pv = PluginValidation(
            name="my-plugin",
            path=Path("/plugins/my-plugin"),
            has_plugin_json=True,
            plugin_json_valid=True,
            errors=["bad field"],
        )
        d = to_dict(pv)
        assert d["summary"]["status"] == "error"

    def test_plugin_validation_ok(self):
        pv = PluginValidation(
            name="good-plugin",
            path=Path("/plugins/good-plugin"),
            has_plugin_json=True,
            plugin_json_valid=True,
        )
        d = to_dict(pv)
        assert d["summary"]["status"] == "ok"

    def test_log_report_summary(self):
        lr = LogReport(
            mcp_events=[
                McpLogEvent("2025-01-01T00:00:00Z", "srv1", "connected"),
                McpLogEvent("2025-01-01T00:00:01Z", "srv2", "errored"),
            ],
            errors=[
                LogError("2025-01-01T00:00:02Z", "copilot", "auth", "token expired"),
            ],
            log_files_scanned=3,
        )
        d = to_dict(lr)
        s = d["summary"]
        assert "srv1" in s["connected_servers"]
        assert "srv2" in s["errored_servers"]
        assert len(s["auth_errors"]) == 1


# ---------------------------------------------------------------------------
# to_json
# ---------------------------------------------------------------------------


class TestToJson:
    """Verify JSON string output."""

    def test_valid_json(self):
        report = _minimal_sync_report()
        result = to_json(report)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)
        assert "items" in parsed

    def test_indent_default(self):
        item = SyncItem("mcp", "x", ToolName.COPILOT, SyncStatus.SYNCED)
        result = to_json(item)
        # Default indent=2 means newlines
        assert "\n" in result

    def test_indent_override(self):
        item = SyncItem("mcp", "x", ToolName.COPILOT, SyncStatus.SYNCED)
        result = to_json(item, indent=None)
        assert "\n" not in result

    def test_round_trip_preserves_data(self):
        fa = FixAction(
            action=FixActionType.WRITE_COMMAND,
            tool=ToolName.CODEX,
            content_type="command",
            target="opsx/explore",
            detail="Write opsx/explore to codex",
        )
        item = SyncItem(
            content_type="command",
            item_name="opsx/explore",
            tool=ToolName.CODEX,
            status=SyncStatus.MISSING,
            detail="Not found",
            fix_action=fa,
        )
        js = to_json(item)
        parsed = json.loads(js)
        assert parsed["fix_action"]["action"] == "write-command"
        assert parsed["fix_action"]["tool"] == "codex"
        assert parsed["content_type"] == "command"
        assert parsed["status"] == "missing"


# ---------------------------------------------------------------------------
# FixAction model tests
# ---------------------------------------------------------------------------


class TestFixAction:
    """Test the FixAction dataclass itself."""

    def test_all_action_types_exist(self):
        expected = {
            "add-mcp", "update-mcp", "remove-mcp",
            "create-symlink", "add-config",
            "write-command", "overwrite-command", "copy-command", "reconcile-command",
            "install-plugin",
        }
        actual = {t.value for t in FixActionType}
        assert actual == expected

    def test_fix_action_fields(self):
        fa = FixAction(
            action=FixActionType.ADD_MCP,
            tool=ToolName.COPILOT,
            content_type="mcp",
            target="server-a",
            detail="Add server-a to copilot MCP config",
        )
        assert fa.action == FixActionType.ADD_MCP
        assert fa.tool == ToolName.COPILOT
        assert fa.content_type == "mcp"
        assert fa.target == "server-a"
        assert fa.detail == "Add server-a to copilot MCP config"

    def test_fix_action_is_none_when_synced(self):
        item = SyncItem("mcp", "srv", ToolName.COPILOT, SyncStatus.SYNCED)
        assert item.fix_action is None


# ---------------------------------------------------------------------------
# CLI filtering helpers (unit-level)
# ---------------------------------------------------------------------------


class TestFilterHelpers:
    """Test the _filter_items and _filter_probe_results functions."""

    def test_filter_by_tool(self):
        from agent_sync.cli import _filter_items

        items = [
            SyncItem("mcp", "a", ToolName.COPILOT, SyncStatus.SYNCED),
            SyncItem("mcp", "a", ToolName.CLAUDE, SyncStatus.DRIFT),
            SyncItem("mcp", "a", ToolName.CODEX, SyncStatus.MISSING),
        ]
        result = _filter_items(items, tool="claude", content_type=None)
        assert len(result) == 1
        assert result[0].tool == ToolName.CLAUDE

    def test_filter_by_type(self):
        from agent_sync.cli import _filter_items

        items = [
            SyncItem("mcp", "srv", ToolName.COPILOT, SyncStatus.SYNCED),
            SyncItem("command", "cmd", ToolName.COPILOT, SyncStatus.DRIFT),
            SyncItem("skill", "sk", ToolName.COPILOT, SyncStatus.SYNCED),
        ]
        result = _filter_items(items, tool=None, content_type="command")
        assert len(result) == 1
        assert result[0].content_type == "command"

    def test_filter_infrastructure(self):
        from agent_sync.cli import _filter_items

        items = [
            SyncItem("symlink", "sym", ToolName.CLAUDE, SyncStatus.MISSING),
            SyncItem("config", "cfg", ToolName.CLAUDE, SyncStatus.MISSING),
            SyncItem("mcp", "srv", ToolName.COPILOT, SyncStatus.SYNCED),
        ]
        result = _filter_items(items, tool=None, content_type="infrastructure")
        assert len(result) == 2
        assert all(i.content_type in ("symlink", "config") for i in result)

    def test_filter_combined(self):
        from agent_sync.cli import _filter_items

        items = [
            SyncItem("mcp", "srv", ToolName.COPILOT, SyncStatus.SYNCED),
            SyncItem("mcp", "srv", ToolName.CLAUDE, SyncStatus.DRIFT),
            SyncItem("command", "cmd", ToolName.CLAUDE, SyncStatus.MISSING),
        ]
        result = _filter_items(items, tool="claude", content_type="mcp")
        assert len(result) == 1
        assert result[0].tool == ToolName.CLAUDE
        assert result[0].content_type == "mcp"

    def test_no_filter_returns_all(self):
        from agent_sync.cli import _filter_items

        items = [
            SyncItem("mcp", "a", ToolName.COPILOT, SyncStatus.SYNCED),
            SyncItem("mcp", "b", ToolName.CLAUDE, SyncStatus.DRIFT),
        ]
        result = _filter_items(items, tool=None, content_type=None)
        assert len(result) == 2

    def test_filter_probe_results(self):
        from agent_sync.cli import _filter_probe_results

        results = [
            ProbeResult("sdk", ProbeTargetType.COPILOT_SDK, tool=ToolName.COPILOT, status=ProbeStatus.OK),
            ProbeResult("srv", ProbeTargetType.MCP_HTTP, tool=ToolName.CLAUDE, status=ProbeStatus.OK),
        ]
        filtered = _filter_probe_results(results, tool="copilot")
        assert len(filtered) == 1
        assert filtered[0].target == "sdk"

    def test_filter_probe_no_filter(self):
        from agent_sync.cli import _filter_probe_results

        results = [
            ProbeResult("a", ProbeTargetType.MCP_HTTP, tool=ToolName.COPILOT),
            ProbeResult("b", ProbeTargetType.MCP_HTTP, tool=ToolName.CLAUDE),
        ]
        filtered = _filter_probe_results(results, tool=None)
        assert len(filtered) == 2
