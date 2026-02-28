"""Runtime probes for validating MCP servers and Copilot SDK connectivity.

Uses the ``github-copilot-sdk`` to check Copilot CLI health (ping, models,
tools) and the ``mcp`` Python SDK to directly connect to MCP servers via
HTTP or stdio transports.  Both packages are optional — the module degrades
gracefully when they are missing.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
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
# SDK availability flags
# ---------------------------------------------------------------------------

_HAS_COPILOT_SDK = False
_HAS_MCP_SDK = False

try:  # noqa: SIM105
    from copilot import CopilotClient  # type: ignore[import-untyped]

    _HAS_COPILOT_SDK = True
except ImportError:
    CopilotClient = None  # type: ignore[assignment, misc]

try:
    from mcp import ClientSession, StdioServerParameters  # type: ignore[import-untyped]
    from mcp.client.stdio import stdio_client  # type: ignore[import-untyped]
    from mcp.client.streamable_http import streamablehttp_client  # type: ignore[import-untyped]

    _HAS_MCP_SDK = True
except ImportError:
    pass


def has_copilot_sdk() -> bool:
    """Return True if ``github-copilot-sdk`` is installed."""
    return _HAS_COPILOT_SDK


def has_mcp_sdk() -> bool:
    """Return True if ``mcp`` Python SDK is installed."""
    return _HAS_MCP_SDK


# ---------------------------------------------------------------------------
# Copilot SDK probe
# ---------------------------------------------------------------------------


async def probe_copilot_sdk(timeout: float = 30.0) -> ProbeResult:
    """Ping the Copilot CLI via the SDK and enumerate models/tools.

    Spawns ``copilot --headless --stdio`` under the hood, verifies JSON-RPC
    connectivity, then queries ``models.list`` and ``tools.list``.
    """
    result = ProbeResult(
        target="copilot-sdk",
        target_type=ProbeTargetType.COPILOT_SDK,
        tool=ToolName.COPILOT,
    )

    if not _HAS_COPILOT_SDK:
        result.status = ProbeStatus.UNAVAILABLE
        result.error_message = (
            "github-copilot-sdk not installed — run: pip install agent-sync[probe]"
        )
        return result

    start = time.perf_counter()
    client = CopilotClient()

    try:
        await asyncio.wait_for(client.start(), timeout=timeout)

        # Ping
        ping_resp = await asyncio.wait_for(client.ping(), timeout=10.0)
        result.detail = f"protocol={getattr(ping_resp, 'protocol_version', '?')}"

        # Models
        try:
            models = await asyncio.wait_for(client.list_models(), timeout=10.0)
            result.models_discovered = [
                getattr(m, "id", str(m)) for m in (models or [])
            ]
        except Exception:  # noqa: BLE001
            pass  # non-fatal — some versions may not expose models

        # Tools
        try:
            tools = await asyncio.wait_for(client.list_tools(), timeout=10.0)
            result.tools_discovered = [
                getattr(t, "name", str(t)) for t in (tools or [])
            ]
        except Exception:  # noqa: BLE001
            pass  # non-fatal

        result.status = ProbeStatus.OK

    except TimeoutError:
        result.status = ProbeStatus.TIMEOUT
        result.error_message = f"Copilot SDK timed out after {timeout}s"
    except Exception as exc:  # noqa: BLE001
        result.status = ProbeStatus.ERROR
        result.error_message = str(exc)
    finally:
        try:
            await client.stop()
        except Exception:  # noqa: BLE001
            pass
        result.latency_ms = (time.perf_counter() - start) * 1000

    return result


# ---------------------------------------------------------------------------
# MCP HTTP probe
# ---------------------------------------------------------------------------


async def probe_mcp_http(
    server: McpServer,
    timeout: float = 15.0,
) -> ProbeResult:
    """Connect to an HTTP/SSE MCP server, initialize, and list tools."""
    result = ProbeResult(
        target=server.name,
        target_type=ProbeTargetType.MCP_HTTP,
    )

    if not _HAS_MCP_SDK:
        result.status = ProbeStatus.UNAVAILABLE
        result.error_message = "mcp SDK not installed — run: pip install agent-sync[probe]"
        return result

    if not server.url:
        result.status = ProbeStatus.ERROR
        result.error_message = "No URL configured"
        return result

    start = time.perf_counter()
    try:
        headers = dict(server.headers) if server.headers else {}
        async with streamablehttp_client(server.url, headers=headers) as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await asyncio.wait_for(session.initialize(), timeout=timeout)
                tools_resp = await asyncio.wait_for(
                    session.list_tools(), timeout=timeout
                )
                result.tools_discovered = [t.name for t in (tools_resp.tools or [])]
                result.status = ProbeStatus.OK
                result.detail = f"{len(result.tools_discovered)} tools"

    except TimeoutError:
        result.status = ProbeStatus.TIMEOUT
        result.error_message = f"Timed out after {timeout}s connecting to {server.url}"
    except Exception as exc:  # noqa: BLE001
        result.status = ProbeStatus.ERROR
        result.error_message = f"{type(exc).__name__}: {exc}"
    finally:
        result.latency_ms = (time.perf_counter() - start) * 1000

    return result


# ---------------------------------------------------------------------------
# MCP stdio / local probe
# ---------------------------------------------------------------------------


async def probe_mcp_stdio(
    server: McpServer,
    timeout: float = 20.0,
) -> ProbeResult:
    """Spawn a stdio/local MCP server process, initialize, and list tools."""
    target_type = (
        ProbeTargetType.MCP_LOCAL
        if server.server_type == McpServerType.LOCAL
        else ProbeTargetType.MCP_STDIO
    )
    result = ProbeResult(
        target=server.name,
        target_type=target_type,
    )

    if not _HAS_MCP_SDK:
        result.status = ProbeStatus.UNAVAILABLE
        result.error_message = "mcp SDK not installed — run: pip install agent-sync[probe]"
        return result

    command = server.command
    if not command:
        result.status = ProbeStatus.ERROR
        result.error_message = "No command configured"
        return result

    # Verify the command binary exists
    if not shutil.which(command):
        result.status = ProbeStatus.UNAVAILABLE
        result.error_message = f"Command not found: {command}"
        return result

    start = time.perf_counter()
    try:
        params = StdioServerParameters(
            command=command,
            args=list(server.args) if server.args else [],
            env=dict(server.env) if server.env else None,
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await asyncio.wait_for(session.initialize(), timeout=timeout)
                tools_resp = await asyncio.wait_for(
                    session.list_tools(), timeout=timeout
                )
                result.tools_discovered = [t.name for t in (tools_resp.tools or [])]
                result.status = ProbeStatus.OK
                result.detail = f"{len(result.tools_discovered)} tools"

    except TimeoutError:
        result.status = ProbeStatus.TIMEOUT
        result.error_message = f"Timed out after {timeout}s spawning {command}"
    except Exception as exc:  # noqa: BLE001
        result.status = ProbeStatus.ERROR
        result.error_message = f"{type(exc).__name__}: {exc}"
    finally:
        result.latency_ms = (time.perf_counter() - start) * 1000

    return result


# ---------------------------------------------------------------------------
# CLI version probes (lightweight — just subprocess)
# ---------------------------------------------------------------------------


def probe_cli_version(tool: ToolName) -> ProbeResult:
    """Check that a CLI tool is installed and returns a version string."""
    commands: dict[ToolName, list[str]] = {
        ToolName.COPILOT: ["copilot", "--version"],
        ToolName.CLAUDE: ["claude", "--version"],
        ToolName.CODEX: ["codex", "--version"],
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

    if not shutil.which(cmd[0]):
        result.status = ProbeStatus.UNAVAILABLE
        result.error_message = f"CLI not found: {cmd[0]}"
        return result

    start = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            shell=(os.name == "nt"),  # Windows needs shell for .cmd/.ps1 shims
        )
        result.latency_ms = (time.perf_counter() - start) * 1000
        output = (proc.stdout or proc.stderr or "").strip()
        if proc.returncode == 0:
            result.status = ProbeStatus.OK
            result.detail = output[:120]
        else:
            result.status = ProbeStatus.ERROR
            result.error_message = output[:200]
    except subprocess.TimeoutExpired:
        result.latency_ms = (time.perf_counter() - start) * 1000
        result.status = ProbeStatus.TIMEOUT
        result.error_message = f"{cmd[0]} --version timed out"
    except Exception as exc:  # noqa: BLE001
        result.latency_ms = (time.perf_counter() - start) * 1000
        result.status = ProbeStatus.ERROR
        result.error_message = str(exc)

    return result


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


async def probe_mcp_server(server: McpServer, timeout: float = 15.0) -> ProbeResult:
    """Route an MCP server to the correct probe function based on type."""
    if server.server_type == McpServerType.HTTP:
        return await probe_mcp_http(server, timeout=timeout)
    return await probe_mcp_stdio(server, timeout=timeout)


async def probe_all(
    canonical: CanonicalState,
    *,
    skip_copilot_sdk: bool = False,
    skip_stdio: bool = False,
    timeout: float = 15.0,
) -> ProbeReport:
    """Run all probes and return a consolidated report.

    Parameters
    ----------
    canonical:
        The canonical state from scanning ``~/.agents/``.
    skip_copilot_sdk:
        If True, skip the Copilot SDK ping/model/tools probe.
    skip_stdio:
        If True, skip probes for stdio/local MCP servers (they spawn processes).
    timeout:
        Per-probe timeout in seconds.
    """
    report = ProbeReport()

    # 1. CLI version checks (synchronous, fast)
    for tool in (ToolName.COPILOT, ToolName.CLAUDE, ToolName.CODEX):
        report.results.append(probe_cli_version(tool))

    # 2. Copilot SDK probe
    if skip_copilot_sdk:
        report.results.append(
            ProbeResult(
                target="copilot-sdk",
                target_type=ProbeTargetType.COPILOT_SDK,
                tool=ToolName.COPILOT,
                status=ProbeStatus.SKIPPED,
                detail="Skipped via --skip-copilot-sdk",
            )
        )
    else:
        report.results.append(await probe_copilot_sdk(timeout=timeout * 2))

    # 3. MCP server probes (parallel)
    mcp_tasks: list[asyncio.Task[ProbeResult]] = []
    for server in canonical.mcp_servers:
        if skip_stdio and server.server_type in (
            McpServerType.STDIO,
            McpServerType.LOCAL,
        ):
            report.results.append(
                ProbeResult(
                    target=server.name,
                    target_type=(
                        ProbeTargetType.MCP_LOCAL
                        if server.server_type == McpServerType.LOCAL
                        else ProbeTargetType.MCP_STDIO
                    ),
                    status=ProbeStatus.SKIPPED,
                    detail="Skipped via --skip-stdio",
                )
            )
            continue
        mcp_tasks.append(
            asyncio.create_task(probe_mcp_server(server, timeout=timeout))
        )

    if mcp_tasks:
        mcp_results = await asyncio.gather(*mcp_tasks, return_exceptions=True)
        for r in mcp_results:
            if isinstance(r, ProbeResult):
                report.results.append(r)
            else:
                # Unexpected exception from gather
                report.results.append(
                    ProbeResult(
                        target="unknown",
                        target_type=ProbeTargetType.MCP_HTTP,
                        status=ProbeStatus.ERROR,
                        error_message=str(r),
                    )
                )

    return report


def run_probe(
    canonical: CanonicalState,
    *,
    skip_copilot_sdk: bool = False,
    skip_stdio: bool = False,
    timeout: float = 15.0,
) -> ProbeReport:
    """Synchronous wrapper for ``probe_all`` — used by the CLI."""
    return asyncio.run(
        probe_all(
            canonical,
            skip_copilot_sdk=skip_copilot_sdk,
            skip_stdio=skip_stdio,
            timeout=timeout,
        )
    )
