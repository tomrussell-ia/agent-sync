"""Configuration validation and guidance for external agents.

This module provides file-based validation of agent configurations and outputs
agent-friendly guidance for connectivity checks. It does NOT attempt runtime
connectivity - external agents should use this output to perform their own checks.

Philosophy: This is a tool FOR agents, not a tool WITH agents embedded.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from agent_sync.models import (
    McpServer,
    McpServerType,
    ProbeReport,
    ProbeResult,
    ProbeStatus,
    ProbeTargetType,
    ToolName,
)

if TYPE_CHECKING:
    from agent_sync.models import CanonicalState


# ---------------------------------------------------------------------------
# CLI version validation (file-based, no execution)
# ---------------------------------------------------------------------------


def validate_cli_availability(tool: ToolName) -> ProbeResult:
    """Check if a CLI tool is available on PATH and provide guidance.
    
    This does NOT execute the tool - it only checks if it exists.
    External agents can use the guidance to perform actual connectivity checks.
    """
    commands = {
        ToolName.COPILOT: "copilot",
        ToolName.CLAUDE: "claude",
        ToolName.CODEX: "codex",
    }
    
    cmd = commands.get(tool)
    result = ProbeResult(
        target=f"{tool.value}-cli",
        target_type=ProbeTargetType.CLI_VERSION,
        tool=tool,
    )
    
    if cmd is None:
        result.status = ProbeStatus.SKIPPED
        result.detail = "No CLI command defined"
        return result
    
    if shutil.which(cmd):
        result.status = ProbeStatus.OK
        result.detail = f"CLI found on PATH: {shutil.which(cmd)}"
        result.error_message = (
            f"AGENT GUIDANCE: Run `{cmd} --version` to verify installation"
        )
    else:
        result.status = ProbeStatus.UNAVAILABLE
        result.error_message = (
            f"CLI not found on PATH: {cmd}\n"
            f"AGENT GUIDANCE: Install the tool or check PATH environment variable"
        )
    
    return result


# ---------------------------------------------------------------------------
# MCP server configuration validation
# ---------------------------------------------------------------------------


def validate_mcp_server(server: McpServer) -> ProbeResult:
    """Validate MCP server configuration without connecting.
    
    Checks configuration validity and provides guidance for external agents
    to perform actual connectivity tests.
    """
    target_type = {
        McpServerType.HTTP: ProbeTargetType.MCP_HTTP,
        McpServerType.STDIO: ProbeTargetType.MCP_STDIO,
        McpServerType.LOCAL: ProbeTargetType.MCP_LOCAL,
    }.get(server.server_type, ProbeTargetType.MCP_HTTP)
    
    result = ProbeResult(
        target=server.name,
        target_type=target_type,
    )
    
    # Validate HTTP server configuration
    if server.server_type == McpServerType.HTTP:
        if not server.url:
            result.status = ProbeStatus.ERROR
            result.error_message = "No URL configured for HTTP server"
            return result
        
        result.status = ProbeStatus.OK
        result.detail = f"URL configured: {server.url}"
        result.error_message = (
            f"AGENT GUIDANCE: Test connectivity with:\n"
            f"  curl -X POST {server.url}/initialize -H 'Content-Type: application/json'\n"
            f"  or use an HTTP client to verify the endpoint is accessible"
        )
        return result
    
    # Validate stdio/local server configuration
    command = server.command
    if not command:
        result.status = ProbeStatus.ERROR
        result.error_message = "No command configured for stdio/local server"
        return result
    
    # Check if command exists
    if shutil.which(command):
        result.status = ProbeStatus.OK
        result.detail = f"Command found: {shutil.which(command)}"
        args_str = " ".join(server.args) if server.args else ""
        result.error_message = (
            f"AGENT GUIDANCE: Test the server with:\n"
            f"  {command} {args_str}\n"
            f"  Verify it starts without errors and responds to MCP protocol"
        )
    else:
        result.status = ProbeStatus.UNAVAILABLE
        result.error_message = (
            f"Command not found: {command}\n"
            f"AGENT GUIDANCE: Install the required binary or check PATH.\n"
            f"  Expected command: {command}\n"
            f"  Args: {server.args if server.args else 'none'}"
        )
    
    return result


# ---------------------------------------------------------------------------
# Configuration file validation
# ---------------------------------------------------------------------------


def validate_config_file(path: Path, tool: ToolName) -> ProbeResult:
    """Validate that a configuration file exists and is readable.
    
    Provides guidance on what the file should contain without parsing it.
    """
    result = ProbeResult(
        target=str(path),
        target_type=ProbeTargetType.CLI_VERSION,  # Reusing enum for config validation
        tool=tool,
    )
    
    if not path.exists():
        result.status = ProbeStatus.UNAVAILABLE
        result.error_message = (
            f"Configuration file not found: {path}\n"
            f"AGENT GUIDANCE: Create the file with proper {tool.value} configuration"
        )
        return result
    
    if not path.is_file():
        result.status = ProbeStatus.ERROR
        result.error_message = f"Path exists but is not a file: {path}"
        return result
    
    try:
        # Check if file is readable
        with path.open("r") as f:
            content_preview = f.read(200)
        
        result.status = ProbeStatus.OK
        result.detail = f"Configuration file exists ({path.stat().st_size} bytes)"
        result.error_message = (
            f"AGENT GUIDANCE: Validate configuration syntax:\n"
            f"  - Check JSON/TOML/YAML syntax is valid\n"
            f"  - Verify all required fields are present\n"
            f"  - Test with: {tool.value} --config {path} --validate"
        )
    except PermissionError:
        result.status = ProbeStatus.ERROR
        result.error_message = f"Permission denied reading: {path}"
    except Exception as exc:
        result.status = ProbeStatus.ERROR
        result.error_message = f"Error reading file: {exc}"
    
    return result


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def validate_all(canonical: CanonicalState) -> ProbeReport:
    """Validate all configurations and provide agent guidance.
    
    This performs NO runtime connectivity checks. It only validates:
    - CLI tools are on PATH
    - Configuration files exist and are readable
    - MCP server configurations are valid
    
    External agents should use the guidance messages to perform actual
    connectivity tests and verification.
    
    Parameters
    ----------
    canonical:
        The canonical state from scanning agent configurations.
    
    Returns
    -------
    ProbeReport
        Report with validation results and agent guidance for each component.
    """
    report = ProbeReport()
    
    # 1. Validate CLI tools are available
    for tool in (ToolName.COPILOT, ToolName.CLAUDE, ToolName.CODEX):
        report.results.append(validate_cli_availability(tool))
    
    # 2. Validate MCP server configurations
    for server in canonical.mcp_servers:
        report.results.append(validate_mcp_server(server))
    
    # 3. Validate key configuration files
    config_paths = {
        ToolName.COPILOT: Path.home() / ".copilot" / "config.json",
        ToolName.CLAUDE: Path.home() / ".claude" / "config.json",
    }
    
    for tool, path in config_paths.items():
        if path.parent.exists():  # Only check if base directory exists
            report.results.append(validate_config_file(path, tool))
    
    return report


def run_validation(canonical: CanonicalState) -> ProbeReport:
    """Synchronous wrapper for validation - used by the CLI.
    
    No async needed since we're not doing network calls or spawning processes.
    """
    return validate_all(canonical)

