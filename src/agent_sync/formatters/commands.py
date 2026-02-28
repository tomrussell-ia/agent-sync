"""Command/prompt format translators.

Handles frontmatter translation between canonical, Claude, and Codex formats.
"""

from __future__ import annotations

from pathlib import Path

from agent_sync.config import CLAUDE_COMMANDS_DIR, CODEX_PROMPTS_DIR
from agent_sync.models import Command, ToolName


# ---------------------------------------------------------------------------
# Frontmatter rendering
# ---------------------------------------------------------------------------


def _render_yaml_list(items: list[str]) -> str:
    """Render a YAML inline list: [a, b, c]."""
    return "[" + ", ".join(items) + "]"


def render_claude_frontmatter(cmd: Command) -> str:
    """Render frontmatter in Claude's format (name, description, category, tags)."""
    lines = ["---"]
    if cmd.name:
        lines.append(f"name: {cmd.name}")
    if cmd.description:
        lines.append(f"description: {cmd.description}")
    if cmd.category:
        lines.append(f"category: {cmd.category}")
    if cmd.tags:
        lines.append(f"tags: {_render_yaml_list(cmd.tags)}")
    lines.append("---")
    return "\n".join(lines)


def render_codex_frontmatter(cmd: Command) -> str:
    """Render frontmatter in Codex's format (description, argument-hint)."""
    lines = ["---"]
    if cmd.description:
        lines.append(f"description: {cmd.description}")
    if cmd.argument_hint:
        lines.append(f"argument-hint: {cmd.argument_hint}")
    lines.append("---")
    return "\n".join(lines)


def render_canonical_frontmatter(cmd: Command) -> str:
    """Render frontmatter in canonical superset format."""
    lines = ["---"]
    if cmd.name:
        lines.append(f"name: {cmd.name}")
    if cmd.description:
        lines.append(f"description: {cmd.description}")
    if cmd.category:
        lines.append(f"category: {cmd.category}")
    if cmd.tags:
        lines.append(f"tags: {_render_yaml_list(cmd.tags)}")
    if cmd.argument_hint:
        lines.append(f"argument-hint: {cmd.argument_hint}")
    if cmd.sync_to:
        lines.append(f"sync_to: {_render_yaml_list([t.value for t in cmd.sync_to])}")
    lines.append("---")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# File path helpers
# ---------------------------------------------------------------------------


def claude_command_path(cmd: Command) -> Path:
    """Compute the target path for a Claude command file."""
    if cmd.namespace:
        return CLAUDE_COMMANDS_DIR / cmd.namespace / f"{cmd.slug}.md"
    return CLAUDE_COMMANDS_DIR / f"{cmd.slug}.md"


def codex_prompt_path(cmd: Command) -> Path:
    """Compute the target path for a Codex prompt file."""
    if cmd.namespace:
        return CODEX_PROMPTS_DIR / f"{cmd.namespace}-{cmd.slug}.md"
    return CODEX_PROMPTS_DIR / f"{cmd.slug}.md"


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------


def write_claude_command(cmd: Command, *, dry_run: bool = False) -> str:
    """Write a command file in Claude format."""
    target = claude_command_path(cmd)
    content = render_claude_frontmatter(cmd) + "\n\n" + cmd.body + "\n"

    if dry_run:
        return f"Would write {target}"

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Wrote {target}"


def write_codex_prompt(cmd: Command, *, dry_run: bool = False) -> str:
    """Write a prompt file in Codex format."""
    target = codex_prompt_path(cmd)
    content = render_codex_frontmatter(cmd) + "\n\n" + cmd.body + "\n"

    if dry_run:
        return f"Would write {target}"

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Wrote {target}"


def sync_commands(
    canonical_commands: list[Command],
    *,
    dry_run: bool = False,
) -> list[str]:
    """Sync all canonical commands to Claude and Codex formats.

    Returns list of action descriptions.
    """
    actions: list[str] = []
    for cmd in canonical_commands:
        targets = cmd.sync_to or [ToolName.CLAUDE, ToolName.CODEX]
        if ToolName.CLAUDE in targets:
            actions.append(write_claude_command(cmd, dry_run=dry_run))
        if ToolName.CODEX in targets:
            actions.append(write_codex_prompt(cmd, dry_run=dry_run))
    return actions
