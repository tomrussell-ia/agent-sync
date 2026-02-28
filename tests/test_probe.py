"""Tests for configuration validation and guidance (no SDK connectivity)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from agent_sync.models import (
    CanonicalState,
    McpServer,
    McpServerType,
    ProbeStatus,
    ProbeTargetType,
    ToolName,
)
from agent_sync.prober import (
    run_validation,
    validate_all,
    validate_cli_availability,
    validate_config_file,
    validate_mcp_server,
)


class TestValidateCliAvailability:
    """Test CLI tool availability validation."""
    
    def test_tool_found_on_path(self):
        """Test when CLI tool is found on PATH."""
        with patch("shutil.which", return_value="/usr/bin/python"):
            result = validate_cli_availability(ToolName.COPILOT)
            
            assert result.status == ProbeStatus.OK
            assert "CLI found on PATH" in result.detail
            assert "AGENT GUIDANCE" in result.error_message
            assert "--version" in result.error_message
    
    def test_tool_not_found(self):
        """Test when CLI tool is not on PATH."""
        with patch("shutil.which", return_value=None):
            result = validate_cli_availability(ToolName.COPILOT)
            
            assert result.status == ProbeStatus.UNAVAILABLE
            assert "not found on PATH" in result.error_message
            assert "AGENT GUIDANCE" in result.error_message


class TestValidateMcpServer:
    """Test MCP server configuration validation."""
    
    def test_http_server_valid(self):
        """Test valid HTTP server configuration."""
        server = McpServer(
            name="test-http",
            server_type=McpServerType.HTTP,
            url="http://localhost:8000",
        )
        
        result = validate_mcp_server(server)
        
        assert result.status == ProbeStatus.OK
        assert result.target == "test-http"
        assert result.target_type == ProbeTargetType.MCP_HTTP
        assert "URL configured" in result.detail
        assert "AGENT GUIDANCE" in result.error_message
        assert "curl" in result.error_message
