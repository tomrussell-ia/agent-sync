"""Tests for format translators."""

from __future__ import annotations

from agent_sync.formatters.mcp import (
    generate_claude_mcp_permissions,
    generate_codex_mcp_sections,
    generate_copilot_mcp,
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
