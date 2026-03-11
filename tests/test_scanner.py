"""Tests for agent-sync scanner module."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_sync.models import McpServerType, ToolName
from agent_sync.scanner import (
    _body_hash,
    _parse_frontmatter,
    _read_json,
)


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------


class TestBodyHash:
    """Test body hash normalization."""

    def test_same_content_same_hash(self):
        assert _body_hash("hello world") == _body_hash("hello world")

    def test_whitespace_normalized(self):
        assert _body_hash("  hello world  ") == _body_hash("hello world")

    def test_crlf_normalized(self):
        assert _body_hash("line1\r\nline2") == _body_hash("line1\nline2")

    def test_different_content_different_hash(self):
        assert _body_hash("hello") != _body_hash("world")

    def test_returns_16_char_hex(self):
        h = _body_hash("some content")
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)


class TestParseFrontmatter:
    """Test frontmatter parsing."""

    def test_no_frontmatter(self):
        fm, body = _parse_frontmatter("Just a body")
        assert fm == {}
        assert body == "Just a body"

    def test_basic_frontmatter(self):
        text = """---
name: Test
description: A test command
---
Body content here"""
        fm, body = _parse_frontmatter(text)
        assert fm["name"] == "Test"
        assert fm["description"] == "A test command"
        assert body == "Body content here"

    def test_array_frontmatter(self):
        text = """---
tags: [a, b, c]
---
body"""
        fm, _body = _parse_frontmatter(text)
        assert fm["tags"] == ["a", "b", "c"]

    def test_boolean_frontmatter(self):
        text = """---
enabled: true
disabled: false
---
body"""
        fm, _body = _parse_frontmatter(text)
        assert fm["enabled"] is True
        assert fm["disabled"] is False

    def test_quoted_string(self):
        text = """---
name: "Hello World"
---
body"""
        fm, _body = _parse_frontmatter(text)
        assert fm["name"] == "Hello World"

    def test_missing_end_delimiter(self):
        text = """---
name: Test
No end delimiter"""
        fm, _body = _parse_frontmatter(text)
        assert fm == {}


class TestReadJson:
    """Test JSON/JSONC reading."""

    def test_valid_json(self, tmp_path: Path):
        p = tmp_path / "test.json"
        p.write_text('{"key": "value"}')
        assert _read_json(p) == {"key": "value"}

    def test_jsonc_comments(self, tmp_path: Path):
        p = tmp_path / "test.json"
        p.write_text('{\n  // comment\n  "key": "value"\n}')
        assert _read_json(p) == {"key": "value"}

    def test_missing_file(self, tmp_path: Path):
        p = tmp_path / "nonexistent.json"
        assert _read_json(p) == {}

    def test_invalid_json(self, tmp_path: Path):
        p = tmp_path / "bad.json"
        p.write_text("not json at all")
        assert _read_json(p) == {}


# ---------------------------------------------------------------------------
# MCP scanner tests
# ---------------------------------------------------------------------------


class TestScanCanonicalMcp:
    """Test canonical MCP scanner with a fixture mcp.json."""

    def test_scan_fixture(self, monkeypatch: pytest.MonkeyPatch):
        """Provide fixture MCP data via monkeypatched _read_json."""
        from agent_sync import scanner as scanner_mod

        mcp_data = {
            "servers": {
                "TestServer": {
                    "type": "http",
                    "url": "https://example.com/mcp",
                    "enabled_for": ["copilot", "claude"],
                },
                "LocalTool": {
                    "type": "stdio",
                    "command": "npx",
                    "args": ["-y", "test-tool"],
                    "enabled_for": ["codex"],
                },
            }
        }

        monkeypatch.setattr(scanner_mod, "_read_json", lambda _path: mcp_data)

        servers = scanner_mod.scan_canonical_mcp()
        assert len(servers) == 2

        test_srv = next(s for s in servers if s.name == "TestServer")
        assert test_srv.server_type == McpServerType.HTTP
        assert test_srv.url == "https://example.com/mcp"
        assert ToolName.COPILOT in test_srv.enabled_for
        assert ToolName.CLAUDE in test_srv.enabled_for

        local_srv = next(s for s in servers if s.name == "LocalTool")
        assert local_srv.server_type == McpServerType.STDIO
        assert local_srv.command == "npx"
        assert ToolName.CODEX in local_srv.enabled_for

    def test_missing_mcp_json(self, monkeypatch: pytest.MonkeyPatch):
        from agent_sync import scanner as scanner_mod

        monkeypatch.setattr(scanner_mod, "_read_json", lambda _path: {})
        servers = scanner_mod.scan_canonical_mcp()
        assert servers == []


# ---------------------------------------------------------------------------
# VS Code scanner tests
# ---------------------------------------------------------------------------


class TestScanVsCode:
    """Test VS Code MCP scanner."""

    def test_parses_http_server(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """HTTP server with url is parsed correctly."""
        mcp_json = tmp_path / "mcp.json"
        mcp_json.write_text(
            '{"servers": {"MyServer": {"type": "http", "url": "https://example.com/mcp"}}}'
        )
        import agent_sync.scanner as scanner_mod

        monkeypatch.setattr(scanner_mod, "VSCODE_MCP_JSON", mcp_json)

        cfg = scanner_mod.scan_vscode()
        assert cfg.tool == ToolName.VSCODE
        assert len(cfg.mcp_servers) == 1
        srv = cfg.mcp_servers[0]
        assert srv.name == "MyServer"
        assert srv.server_type == McpServerType.HTTP
        assert srv.url == "https://example.com/mcp"

    def test_parses_stdio_server(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Stdio server with command/args is parsed correctly."""
        mcp_json = tmp_path / "mcp.json"
        mcp_json.write_text(
            '{"servers": {"Playwright": {"type": "stdio", "command": "npx", "args": ["@playwright/mcp@latest"]}}}'
        )
        import agent_sync.scanner as scanner_mod

        monkeypatch.setattr(scanner_mod, "VSCODE_MCP_JSON", mcp_json)

        cfg = scanner_mod.scan_vscode()
        srv = cfg.mcp_servers[0]
        assert srv.name == "Playwright"
        assert srv.server_type == McpServerType.STDIO
        assert srv.command == "npx"
        assert srv.args == ["@playwright/mcp@latest"]

    def test_infers_type_from_url(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Server without explicit type but with url is inferred as http."""
        mcp_json = tmp_path / "mcp.json"
        mcp_json.write_text(
            '{"servers": {"NoType": {"url": "https://example.com/mcp"}}}'
        )
        import agent_sync.scanner as scanner_mod

        monkeypatch.setattr(scanner_mod, "VSCODE_MCP_JSON", mcp_json)

        cfg = scanner_mod.scan_vscode()
        assert cfg.mcp_servers[0].server_type == McpServerType.HTTP

    def test_infers_type_from_command(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Server without explicit type but with command is inferred as stdio."""
        mcp_json = tmp_path / "mcp.json"
        mcp_json.write_text(
            '{"servers": {"NoType": {"command": "npx", "args": ["-y", "tool"]}}}'
        )
        import agent_sync.scanner as scanner_mod

        monkeypatch.setattr(scanner_mod, "VSCODE_MCP_JSON", mcp_json)

        cfg = scanner_mod.scan_vscode()
        assert cfg.mcp_servers[0].server_type == McpServerType.STDIO

    def test_missing_file_returns_empty_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """When mcp.json doesn't exist, returns an empty ToolConfig."""
        import agent_sync.scanner as scanner_mod

        monkeypatch.setattr(scanner_mod, "VSCODE_MCP_JSON", tmp_path / "nonexistent.json")

        cfg = scanner_mod.scan_vscode()
        assert cfg.tool == ToolName.VSCODE
        assert cfg.mcp_servers == []

    def test_parses_multiple_servers(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Multiple servers are all parsed regardless of type."""
        import json as _json

        mcp_json = tmp_path / "mcp.json"
        data = {
            "servers": {
                "HttpSrv": {"type": "http", "url": "https://a.com"},
                "StdioSrv": {"type": "stdio", "command": "npx", "args": ["-y", "tool"]},
                "LocalSrv": {"type": "local", "command": "npx", "args": ["@playwright/mcp@latest"]},
            }
        }
        mcp_json.write_text(_json.dumps(data))
        import agent_sync.scanner as scanner_mod

        monkeypatch.setattr(scanner_mod, "VSCODE_MCP_JSON", mcp_json)

        cfg = scanner_mod.scan_vscode()
        assert len(cfg.mcp_servers) == 3
        names = {s.name for s in cfg.mcp_servers}
        assert names == {"HttpSrv", "StdioSrv", "LocalSrv"}
