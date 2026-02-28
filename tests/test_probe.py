"""Tests for the probe models, prober, log_parser, and plugin_validator modules."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_sync.models import (
    McpServer,
    McpServerType,
    PluginValidation,
    ProbeReport,
    ProbeResult,
    ProbeStatus,
    ProbeTargetType,
    ToolName,
)


# ===================================================================
# ProbeStatus / ProbeResult / ProbeReport model tests
# ===================================================================


class TestProbeStatus:
    """Test ProbeStatus enum values."""

    def test_enum_values(self):
        assert ProbeStatus.OK.value == "ok"
        assert ProbeStatus.ERROR.value == "error"
        assert ProbeStatus.TIMEOUT.value == "timeout"
        assert ProbeStatus.SKIPPED.value == "skipped"
        assert ProbeStatus.UNAVAILABLE.value == "unavailable"


class TestProbeTargetType:
    """Test ProbeTargetType enum values."""

    def test_enum_values(self):
        assert ProbeTargetType.COPILOT_SDK.value == "copilot-sdk"
        assert ProbeTargetType.MCP_HTTP.value == "mcp-http"
        assert ProbeTargetType.MCP_STDIO.value == "mcp-stdio"
        assert ProbeTargetType.MCP_LOCAL.value == "mcp-local"
        assert ProbeTargetType.PLUGIN.value == "plugin"
        assert ProbeTargetType.CLI_VERSION.value == "cli-version"


class TestProbeResult:
    """Test ProbeResult dataclass defaults and construction."""

    def test_defaults(self):
        r = ProbeResult(target="test", target_type=ProbeTargetType.MCP_HTTP)
        assert r.status == ProbeStatus.SKIPPED
        assert r.latency_ms is None
        assert r.tools_discovered == []
        assert r.models_discovered == []
        assert r.error_message == ""
        assert r.tool is None

    def test_full_construction(self):
        r = ProbeResult(
            target="my-server",
            target_type=ProbeTargetType.MCP_HTTP,
            tool=ToolName.COPILOT,
            status=ProbeStatus.OK,
            latency_ms=123.4,
            tools_discovered=["tool1", "tool2"],
            detail="2 tools",
        )
        assert r.target == "my-server"
        assert r.status == ProbeStatus.OK
        assert len(r.tools_discovered) == 2


class TestProbeReport:
    """Test ProbeReport computed properties."""

    def _make_report(self, statuses: list[ProbeStatus]) -> ProbeReport:
        results = [
            ProbeResult(
                target=f"t{i}",
                target_type=ProbeTargetType.MCP_HTTP,
                status=s,
            )
            for i, s in enumerate(statuses)
        ]
        return ProbeReport(results=results)

    def test_empty(self):
        r = ProbeReport()
        assert r.ok_count == 0
        assert r.error_count == 0
        assert r.overall_status == ProbeStatus.SKIPPED

    def test_all_ok(self):
        r = self._make_report([ProbeStatus.OK, ProbeStatus.OK])
        assert r.ok_count == 2
        assert r.overall_status == ProbeStatus.OK

    def test_has_errors(self):
        r = self._make_report([ProbeStatus.OK, ProbeStatus.ERROR])
        assert r.error_count == 1
        assert r.overall_status == ProbeStatus.ERROR

    def test_has_timeout(self):
        r = self._make_report([ProbeStatus.OK, ProbeStatus.TIMEOUT])
        assert r.timeout_count == 1
        assert r.overall_status == ProbeStatus.TIMEOUT

    def test_error_takes_precedence_over_timeout(self):
        r = self._make_report([ProbeStatus.ERROR, ProbeStatus.TIMEOUT])
        assert r.overall_status == ProbeStatus.ERROR


class TestPluginValidation:
    """Test PluginValidation status property."""

    def test_ok_when_no_errors(self):
        v = PluginValidation(name="test", path=Path("."), has_plugin_json=True)
        assert v.status == ProbeStatus.OK

    def test_error_when_errors(self):
        v = PluginValidation(
            name="test",
            path=Path("."),
            has_plugin_json=True,
            errors=["Missing key"],
        )
        assert v.status == ProbeStatus.ERROR

    def test_unavailable_when_no_plugin_json(self):
        v = PluginValidation(name="test", path=Path("."))
        assert v.status == ProbeStatus.UNAVAILABLE


# ===================================================================
# Prober tests (mocking SDKs to avoid real network/process calls)
# ===================================================================


class TestProberCliVersion:
    """Test probe_cli_version (subprocess-based)."""

    def test_tool_found_success(self):
        from agent_sync.prober import probe_cli_version

        with patch("agent_sync.prober.shutil.which", return_value="/usr/bin/copilot"), \
             patch("agent_sync.prober.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="1.2.3", stderr=""
            )
            result = probe_cli_version(ToolName.COPILOT)
            assert result.status == ProbeStatus.OK
            assert "1.2.3" in result.detail

    def test_tool_not_found(self):
        from agent_sync.prober import probe_cli_version

        with patch("agent_sync.prober.shutil.which", return_value=None):
            result = probe_cli_version(ToolName.COPILOT)
            assert result.status == ProbeStatus.UNAVAILABLE

    def test_tool_returns_error(self):
        from agent_sync.prober import probe_cli_version

        with patch("agent_sync.prober.shutil.which", return_value="/usr/bin/claude"), \
             patch("agent_sync.prober.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="some error"
            )
            result = probe_cli_version(ToolName.CLAUDE)
            assert result.status == ProbeStatus.ERROR

    def test_unsupported_tool(self):
        from agent_sync.prober import probe_cli_version

        result = probe_cli_version(ToolName.VSCODE)
        assert result.status == ProbeStatus.SKIPPED


class TestProberCopilotSdk:
    """Test probe_copilot_sdk with mocked SDK."""

    @pytest.mark.asyncio
    async def test_sdk_unavailable(self):
        from agent_sync.prober import probe_copilot_sdk

        with patch("agent_sync.prober._HAS_COPILOT_SDK", False):
            result = await probe_copilot_sdk()
            assert result.status == ProbeStatus.UNAVAILABLE

    @pytest.mark.asyncio
    async def test_sdk_success(self):
        from agent_sync.prober import probe_copilot_sdk

        mock_client = AsyncMock()
        mock_client.ping.return_value = MagicMock(protocol_version="1.0")
        mock_client.list_models.return_value = [
            MagicMock(id="gpt-4o"),
            MagicMock(id="claude-sonnet"),
        ]
        mock_client.list_tools.return_value = [
            MagicMock(name="read_file"),
            MagicMock(name="search"),
        ]

        with patch("agent_sync.prober._HAS_COPILOT_SDK", True), \
             patch("agent_sync.prober.CopilotClient", return_value=mock_client):
            result = await probe_copilot_sdk(timeout=5.0)
            assert result.status == ProbeStatus.OK
            assert len(result.models_discovered) == 2
            assert len(result.tools_discovered) == 2
            assert result.latency_ms is not None


class TestProberMcpHttp:
    """Test probe_mcp_http with mocked MCP SDK."""

    @pytest.mark.asyncio
    async def test_mcp_sdk_unavailable(self):
        from agent_sync.prober import probe_mcp_http

        server = McpServer(
            name="test", server_type=McpServerType.HTTP, url="https://example.com/mcp"
        )
        with patch("agent_sync.prober._HAS_MCP_SDK", False):
            result = await probe_mcp_http(server)
            assert result.status == ProbeStatus.UNAVAILABLE

    @pytest.mark.asyncio
    async def test_no_url(self):
        from agent_sync.prober import probe_mcp_http

        server = McpServer(name="test", server_type=McpServerType.HTTP)
        with patch("agent_sync.prober._HAS_MCP_SDK", True):
            result = await probe_mcp_http(server)
            assert result.status == ProbeStatus.ERROR
            assert "No URL" in result.error_message


class TestProberMcpStdio:
    """Test probe_mcp_stdio with mocked MCP SDK."""

    @pytest.mark.asyncio
    async def test_command_not_found(self):
        from agent_sync.prober import probe_mcp_stdio

        server = McpServer(
            name="test",
            server_type=McpServerType.STDIO,
            command="nonexistent-tool",
        )
        with patch("agent_sync.prober._HAS_MCP_SDK", True), \
             patch("agent_sync.prober.shutil.which", return_value=None):
            result = await probe_mcp_stdio(server)
            assert result.status == ProbeStatus.UNAVAILABLE

    @pytest.mark.asyncio
    async def test_no_command(self):
        from agent_sync.prober import probe_mcp_stdio

        server = McpServer(name="test", server_type=McpServerType.STDIO)
        with patch("agent_sync.prober._HAS_MCP_SDK", True):
            result = await probe_mcp_stdio(server)
            assert result.status == ProbeStatus.ERROR


# ===================================================================
# Log parser tests
# ===================================================================


class TestLogParser:
    """Test Copilot and Codex log parsing."""

    def test_parse_copilot_connected(self, tmp_path: Path):
        log = tmp_path / "process-123.log"
        log.write_text(
            "2026-02-27T23:33:07.682Z [ERROR] MCP client for Context7 connected, took 1794ms\n"
            "2026-02-27T23:33:07.804Z [ERROR] MCP client for GitBooks connected, took 1919ms\n"
        )
        from agent_sync.log_parser import _parse_copilot_log

        events, errors = _parse_copilot_log(log)
        assert len(events) == 2
        assert events[0].server_name == "Context7"
        assert events[0].event_type == "connected"
        assert events[0].latency_ms == 1794.0
        assert events[1].server_name == "GitBooks"

    def test_parse_copilot_errored(self, tmp_path: Path):
        log = tmp_path / "process-456.log"
        log.write_text(
            "2026-02-27T23:38:12.140Z [ERROR] MCP client for Context7 errored Error: SSE stream disconnected\n"
        )
        from agent_sync.log_parser import _parse_copilot_log

        events, errors = _parse_copilot_log(log)
        assert len(events) == 1
        assert events[0].event_type == "errored"
        assert "SSE" in events[0].detail

    def test_parse_copilot_starting(self, tmp_path: Path):
        log = tmp_path / "process-789.log"
        log.write_text(
            "2026-02-27T23:33:05.881Z [ERROR] Starting remote MCP client for GitBooks-Docs with url: https://example.com\n"
        )
        from agent_sync.log_parser import _parse_copilot_log

        events, errors = _parse_copilot_log(log)
        assert len(events) == 1
        assert events[0].event_type == "starting"
        assert events[0].server_name == "GitBooks-Docs"

    def test_parse_codex_auth_error(self, tmp_path: Path):
        log = tmp_path / "codex-tui.log"
        log.write_text(
            "2026-01-27T20:08:54.828398Z ERROR codex_core::auth: Failed to refresh token: 401 Unauthorized\n"
        )
        from agent_sync.log_parser import _parse_codex_log

        events, errors = _parse_codex_log(log)
        assert len(errors) == 1
        assert errors[0].category == "auth"
        assert "401" in errors[0].message

    def test_parse_logs_integration(self, tmp_path: Path):
        """Test parse_logs with mocked paths."""
        copilot_logs = tmp_path / "copilot" / "logs"
        copilot_logs.mkdir(parents=True)
        (copilot_logs / "process-1.log").write_text(
            "2026-02-27T23:33:07.682Z [ERROR] MCP client for Server1 connected, took 500ms\n"
        )

        codex_log_dir = tmp_path / "codex" / "log"
        codex_log_dir.mkdir(parents=True)
        (codex_log_dir / "codex-tui.log").write_text(
            "2026-01-27T20:08:54.828Z ERROR codex_core::auth: Token expired\n"
        )

        with patch("agent_sync.log_parser.COPILOT_DIR", tmp_path / "copilot"), \
             patch("agent_sync.log_parser.CODEX_DIR", tmp_path / "codex"):
            from agent_sync.log_parser import parse_logs

            report = parse_logs()
            assert report.log_files_scanned == 2
            assert len(report.connected_servers) == 1
            assert len(report.auth_errors) == 1


class TestLogReportProperties:
    """Test LogReport computed properties."""

    def test_connected_and_errored_servers(self):
        from agent_sync.log_parser import LogReport, McpLogEvent

        report = LogReport(
            mcp_events=[
                McpLogEvent(
                    timestamp="t1",
                    server_name="A",
                    event_type="connected",
                ),
                McpLogEvent(
                    timestamp="t2",
                    server_name="B",
                    event_type="errored",
                    detail="some error",
                ),
                McpLogEvent(
                    timestamp="t3",
                    server_name="A",
                    event_type="errored",
                    detail="later error",
                ),
            ]
        )
        assert "A" in report.connected_servers
        assert "B" in report.errored_servers
        assert "A" in report.errored_servers


# ===================================================================
# Plugin validator tests
# ===================================================================


class TestPluginValidator:
    """Test plugin.json and .mcp.json validation."""

    def test_valid_plugin_json(self, tmp_path: Path):
        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "skills").mkdir()
        (plugin_dir / "plugin.json").write_text(
            json.dumps(
                {
                    "name": "my-plugin",
                    "description": "Test plugin",
                    "version": "1.0.0",
                    "skills": "skills/",
                }
            )
        )

        from agent_sync.plugin_validator import _validate_plugin_json

        valid, errors = _validate_plugin_json(plugin_dir / "plugin.json")
        assert valid is True
        assert errors == []

    def test_missing_required_keys(self, tmp_path: Path):
        plugin_dir = tmp_path / "bad-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text(json.dumps({"name": "test"}))

        from agent_sync.plugin_validator import _validate_plugin_json

        valid, errors = _validate_plugin_json(plugin_dir / "plugin.json")
        assert valid is False
        assert any("description" in e for e in errors)
        assert any("version" in e for e in errors)

    def test_missing_referenced_path(self, tmp_path: Path):
        plugin_dir = tmp_path / "ref-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text(
            json.dumps(
                {
                    "name": "ref-plugin",
                    "description": "test",
                    "version": "1.0.0",
                    "skills": "nonexistent/",
                }
            )
        )

        from agent_sync.plugin_validator import _validate_plugin_json

        valid, errors = _validate_plugin_json(plugin_dir / "plugin.json")
        assert valid is False
        assert any("not found" in e for e in errors)

    def test_valid_mcp_json(self, tmp_path: Path):
        mcp_file = tmp_path / ".mcp.json"
        mcp_file.write_text(
            json.dumps(
                {
                    "servers": {
                        "my-server": {
                            "url": "https://example.com/mcp"
                        }
                    }
                }
            )
        )

        from agent_sync.plugin_validator import _validate_mcp_json

        valid, errors = _validate_mcp_json(mcp_file)
        assert valid is True

    def test_mcp_json_missing_url_and_command(self, tmp_path: Path):
        mcp_file = tmp_path / ".mcp.json"
        mcp_file.write_text(
            json.dumps(
                {
                    "servers": {
                        "bad-server": {"name": "test"}
                    }
                }
            )
        )

        from agent_sync.plugin_validator import _validate_mcp_json

        valid, errors = _validate_mcp_json(mcp_file)
        assert valid is False
        assert any("missing both" in e for e in errors)

    def test_mcp_json_no_servers_key(self, tmp_path: Path):
        mcp_file = tmp_path / ".mcp.json"
        mcp_file.write_text(json.dumps({"other": "data"}))

        from agent_sync.plugin_validator import _validate_mcp_json

        valid, errors = _validate_mcp_json(mcp_file)
        assert valid is False
        assert any("servers" in e for e in errors)

    def test_validate_plugins_integration(self, tmp_path: Path):
        """Test full plugin directory scan."""
        plugin_dir = tmp_path / "test-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text(
            json.dumps(
                {
                    "name": "test-plugin",
                    "description": "A test",
                    "version": "1.0.0",
                }
            )
        )
        (plugin_dir / ".mcp.json").write_text(
            json.dumps(
                {
                    "servers": {
                        "srv": {"url": "https://example.com"}
                    }
                }
            )
        )

        from agent_sync.plugin_validator import validate_plugins

        results = validate_plugins(plugins_dir=tmp_path)
        assert len(results) == 1
        assert results[0].name == "test-plugin"
        assert results[0].has_plugin_json is True
        assert results[0].has_mcp_json is True
        assert results[0].status == ProbeStatus.OK

    def test_validate_plugins_empty_dir(self, tmp_path: Path):
        from agent_sync.plugin_validator import validate_plugins

        results = validate_plugins(plugins_dir=tmp_path)
        assert results == []

    def test_validate_plugins_nonexistent_dir(self, tmp_path: Path):
        from agent_sync.plugin_validator import validate_plugins

        results = validate_plugins(plugins_dir=tmp_path / "nope")
        assert results == []


# ===================================================================
# Probe orchestrator tests
# ===================================================================


class TestProbeAll:
    """Test the probe_all orchestrator with mocked sub-probes."""

    @pytest.mark.asyncio
    async def test_skips_copilot_sdk_when_flagged(self):
        from agent_sync.models import CanonicalState
        from agent_sync.prober import probe_all

        canonical = CanonicalState(agents_dir=Path("."), mcp_servers=[])
        report = await probe_all(
            canonical,
            skip_copilot_sdk=True,
            skip_stdio=True,
        )
        sdk_results = [
            r for r in report.results if r.target_type == ProbeTargetType.COPILOT_SDK
        ]
        assert len(sdk_results) == 1
        assert sdk_results[0].status == ProbeStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_skips_stdio_servers_when_flagged(self):
        from agent_sync.models import CanonicalState
        from agent_sync.prober import probe_all

        canonical = CanonicalState(
            agents_dir=Path("."),
            mcp_servers=[
                McpServer(
                    name="http-srv",
                    server_type=McpServerType.HTTP,
                    url="https://example.com/mcp",
                ),
                McpServer(
                    name="stdio-srv",
                    server_type=McpServerType.STDIO,
                    command="npx",
                    args=["some-tool"],
                ),
            ],
        )

        with patch("agent_sync.prober._HAS_COPILOT_SDK", False), \
             patch("agent_sync.prober._HAS_MCP_SDK", False):
            report = await probe_all(
                canonical,
                skip_copilot_sdk=True,
                skip_stdio=True,
            )

        stdio_results = [
            r for r in report.results
            if r.target_type in (ProbeTargetType.MCP_STDIO, ProbeTargetType.MCP_LOCAL)
        ]
        assert len(stdio_results) == 1
        assert stdio_results[0].status == ProbeStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_includes_cli_version_checks(self):
        from agent_sync.models import CanonicalState
        from agent_sync.prober import probe_all

        canonical = CanonicalState(agents_dir=Path("."), mcp_servers=[])

        with patch("agent_sync.prober.shutil.which", return_value=None), \
             patch("agent_sync.prober._HAS_COPILOT_SDK", False):
            report = await probe_all(
                canonical,
                skip_copilot_sdk=True,
            )

        cli_results = [
            r for r in report.results
            if r.target_type == ProbeTargetType.CLI_VERSION
        ]
        assert len(cli_results) == 3  # copilot, claude, codex
