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
