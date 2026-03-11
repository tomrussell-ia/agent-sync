"""Tests for format translators."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_sync.formatters.mcp import (
    generate_claude_mcp_permissions,
    generate_codex_mcp_sections,
    generate_copilot_mcp,
    generate_vscode_mcp,
    write_vscode_mcp,
)
from agent_sync.models import McpServer, McpServerType, ToolName


class TestCopilotMcpFormat:
    """Test Copilot MCP config generation."""

    def test_http_server(self):
        srv = McpServer(
            name="TestServer",
            server_type=McpServerType.HTTP,
            url="https://example.com/mcp",
            enabled_for=[ToolName.COPILOT],
        )
        result = generate_copilot_mcp([srv])
        assert "TestServer" in result["mcpServers"]
        entry = result["mcpServers"]["TestServer"]
        assert entry["type"] == "http"
        assert entry["url"] == "https://example.com/mcp"

    def test_stdio_server(self):
        srv = McpServer(
            name="LocalTool",
            server_type=McpServerType.STDIO,
            command="npx",
            args=["-y", "tool"],
            enabled_for=[ToolName.COPILOT],
        )
        result = generate_copilot_mcp([srv])
        entry = result["mcpServers"]["LocalTool"]
        assert entry["command"] == "npx"
        assert entry["args"] == ["-y", "tool"]

    def test_filtered_by_enabled_for(self):
        """Only servers enabled for Copilot should appear."""
        copilot_srv = McpServer(
            name="ForCopilot",
            server_type=McpServerType.HTTP,
            url="https://a.com",
            enabled_for=[ToolName.COPILOT],
        )
        claude_srv = McpServer(
            name="ForClaude",
            server_type=McpServerType.HTTP,
            url="https://b.com",
            enabled_for=[ToolName.CLAUDE],
        )
        result = generate_copilot_mcp([copilot_srv, claude_srv])
        assert "ForCopilot" in result["mcpServers"]
        assert "ForClaude" not in result["mcpServers"]

    def test_empty_servers(self):
        result = generate_copilot_mcp([])
        assert result == {"mcpServers": {}}


class TestCodexMcpFormat:
    """Test Codex TOML MCP section generation."""

    def test_http_server(self):
        srv = McpServer(
            name="TestServer",
            server_type=McpServerType.HTTP,
            url="https://example.com/mcp",
            enabled_for=[ToolName.CODEX],
        )
        sections = generate_codex_mcp_sections([srv])
        assert "TestServer" in sections
        assert sections["TestServer"]["url"] == "https://example.com/mcp"

    def test_filtered_by_enabled_for(self):
        srv = McpServer(
            name="CopilotOnly",
            server_type=McpServerType.HTTP,
            url="https://a.com",
            enabled_for=[ToolName.COPILOT],
        )
        sections = generate_codex_mcp_sections([srv])
        assert len(sections) == 0


class TestClaudeMcpPermissions:
    """Test Claude permission string generation."""

    def test_basic_permission(self):
        srv = McpServer(
            name="my-server",
            server_type=McpServerType.HTTP,
            enabled_for=[ToolName.CLAUDE],
        )
        perms = generate_claude_mcp_permissions([srv])
        assert "mcp__my_server__*" in perms

    def test_name_normalization(self):
        srv = McpServer(
            name="My Server Name",
            server_type=McpServerType.HTTP,
            enabled_for=[ToolName.CLAUDE],
        )
        perms = generate_claude_mcp_permissions([srv])
        assert "mcp__my_server_name__*" in perms

    def test_not_enabled_for_claude(self):
        srv = McpServer(
            name="test",
            server_type=McpServerType.HTTP,
            enabled_for=[ToolName.COPILOT],
        )
        perms = generate_claude_mcp_permissions([srv])
        assert len(perms) == 0


class TestVsCodeMcpFormat:
    """Test VS Code MCP config generation."""

    def test_http_server_no_headers(self):
        """HTTP server without headers produces a clean server entry."""
        srv = McpServer(
            name="TestServer",
            server_type=McpServerType.HTTP,
            url="https://example.com/mcp",
            enabled_for=[ToolName.VSCODE],
        )
        result = generate_vscode_mcp([srv])
        assert "TestServer" in result["servers"]
        entry = result["servers"]["TestServer"]
        assert entry["type"] == "http"
        assert entry["url"] == "https://example.com/mcp"
        assert "inputs" not in result

    def test_http_server_with_headers_generates_inputs(self):
        """Non-empty header values become ${input:id} references with matching inputs entries."""
        srv = McpServer(
            name="SecureServer",
            server_type=McpServerType.HTTP,
            url="https://example.com/mcp",
            headers={"CONTEXT7_API_KEY": "op://secret/value"},
            enabled_for=[ToolName.VSCODE],
        )
        result = generate_vscode_mcp([srv])
        entry = result["servers"]["SecureServer"]
        assert entry["headers"]["CONTEXT7_API_KEY"] == "${input:context7_api_key}"
        assert "inputs" in result
        assert len(result["inputs"]) == 1
        inp = result["inputs"][0]
        assert inp["id"] == "context7_api_key"
        assert inp["type"] == "promptString"
        assert inp["password"] is True
        assert inp["description"] == "CONTEXT7_API_KEY"

    def test_empty_header_value_not_promoted_to_input(self):
        """Headers with empty string values are passed through without generating an input."""
        srv = McpServer(
            name="OptionalHeader",
            server_type=McpServerType.HTTP,
            url="https://example.com/mcp",
            headers={"X-Optional": ""},
            enabled_for=[ToolName.VSCODE],
        )
        result = generate_vscode_mcp([srv])
        entry = result["servers"]["OptionalHeader"]
        assert entry["headers"]["X-Optional"] == ""
        assert "inputs" not in result

    def test_local_server_no_inputs(self):
        """Local/stdio server without headers produces no inputs array."""
        srv = McpServer(
            name="Playwright",
            server_type=McpServerType.LOCAL,
            command="npx",
            args=["@playwright/mcp@latest"],
            enabled_for=[ToolName.VSCODE],
        )
        result = generate_vscode_mcp([srv])
        entry = result["servers"]["Playwright"]
        assert entry["type"] == "local"
        assert entry["command"] == "npx"
        assert entry["args"] == ["@playwright/mcp@latest"]
        assert "inputs" not in result

    def test_filtered_by_enabled_for(self):
        """Only servers with ToolName.VSCODE in enabled_for are included."""
        vscode_srv = McpServer(
            name="ForVSCode",
            server_type=McpServerType.HTTP,
            url="https://a.com",
            enabled_for=[ToolName.VSCODE],
        )
        copilot_srv = McpServer(
            name="ForCopilot",
            server_type=McpServerType.HTTP,
            url="https://b.com",
            enabled_for=[ToolName.COPILOT],
        )
        result = generate_vscode_mcp([vscode_srv, copilot_srv])
        assert "ForVSCode" in result["servers"]
        assert "ForCopilot" not in result["servers"]

    def test_deduplicates_inputs_across_servers(self):
        """Two servers sharing the same header key produce a single input entry."""
        srv1 = McpServer(
            name="ServerA",
            server_type=McpServerType.HTTP,
            url="https://a.com",
            headers={"API_KEY": "val1"},
            enabled_for=[ToolName.VSCODE],
        )
        srv2 = McpServer(
            name="ServerB",
            server_type=McpServerType.HTTP,
            url="https://b.com",
            headers={"API_KEY": "val2"},
            enabled_for=[ToolName.VSCODE],
        )
        result = generate_vscode_mcp([srv1, srv2])
        assert len(result["inputs"]) == 1
        assert result["inputs"][0]["id"] == "api_key"

    def test_empty_servers(self):
        result = generate_vscode_mcp([])
        assert result == {"servers": {}}

    def test_write_vscode_mcp_creates_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """write_vscode_mcp writes a valid JSON file when target doesn't exist."""
        import agent_sync.formatters.mcp as mcp_mod

        target = tmp_path / "mcp.json"
        monkeypatch.setattr(mcp_mod, "VSCODE_MCP_JSON", target)

        srv = McpServer(
            name="TestServer",
            server_type=McpServerType.HTTP,
            url="https://example.com/mcp",
            enabled_for=[ToolName.VSCODE],
        )
        msg = write_vscode_mcp([srv])
        assert target.exists()
        data = json.loads(target.read_text())
        assert "TestServer" in data["servers"]
        assert "Wrote" in msg

    def test_write_vscode_mcp_dry_run(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Dry run returns a description and does not write any file."""
        import agent_sync.formatters.mcp as mcp_mod

        target = tmp_path / "mcp.json"
        monkeypatch.setattr(mcp_mod, "VSCODE_MCP_JSON", target)

        srv = McpServer(
            name="TestServer",
            server_type=McpServerType.HTTP,
            url="https://example.com/mcp",
            enabled_for=[ToolName.VSCODE],
        )
        msg = write_vscode_mcp([srv], dry_run=True)
        assert not target.exists()
        assert "Would merge" in msg

    def test_write_vscode_mcp_merges_existing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """write_vscode_mcp preserves servers already in the file that aren't in canonical."""
        import agent_sync.formatters.mcp as mcp_mod

        target = tmp_path / "mcp.json"
        # Pre-populate with an existing server not in canonical
        target.write_text(json.dumps({"servers": {"ExistingServer": {"type": "http", "url": "https://existing.com"}}}))
        monkeypatch.setattr(mcp_mod, "VSCODE_MCP_JSON", target)

        srv = McpServer(
            name="NewServer",
            server_type=McpServerType.HTTP,
            url="https://new.com",
            enabled_for=[ToolName.VSCODE],
        )
        write_vscode_mcp([srv])
        data = json.loads(target.read_text())
        assert "ExistingServer" in data["servers"]
        assert "NewServer" in data["servers"]
