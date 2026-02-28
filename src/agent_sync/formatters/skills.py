"""Skill distribution and symlink management."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from agent_sync.config import (
    AGENTS_DIR,
    CANONICAL_SKILLS_DIR,
    CLAUDE_DIR,
    CLAUDE_SETTINGS_JSON,
    CLAUDE_SYMLINK_SKILLS,
)
from agent_sync.scanner import _read_json


# ---------------------------------------------------------------------------
# Symlink / junction helpers
# ---------------------------------------------------------------------------


def _is_junction(path: Path) -> bool:
    """Check if a path is a directory junction (Windows) or symlink."""
    if path.is_symlink():
        return True
    # On Windows, check for junction
    if sys.platform == "win32":
        try:
            import ctypes

            FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))  # type: ignore[attr-defined]
            return bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT)
        except (AttributeError, OSError):
            pass
    return False


def _create_junction(target: Path, link: Path) -> None:
    """Create a directory junction (Windows) or symlink (Unix)."""
    link.parent.mkdir(parents=True, exist_ok=True)

    if sys.platform == "win32":
        # Use mklink /J for Windows junctions (no admin required)
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=True,
            capture_output=True,
        )
    else:
        link.symlink_to(target, target_is_directory=True)


# ---------------------------------------------------------------------------
# Skill sync operations
# ---------------------------------------------------------------------------


def check_claude_skills_symlink() -> tuple[bool, str]:
    """Check if .agents/.claude/skills/ symlink exists and points correctly.

    Returns (is_valid, detail_message).
    """
    if not CLAUDE_SYMLINK_SKILLS.exists():
        return False, f"Missing: {CLAUDE_SYMLINK_SKILLS} does not exist"

    if _is_junction(CLAUDE_SYMLINK_SKILLS):
        resolved = CLAUDE_SYMLINK_SKILLS.resolve()
        canonical = CANONICAL_SKILLS_DIR.resolve()
        if resolved == canonical:
            return True, f"OK: {CLAUDE_SYMLINK_SKILLS} → {canonical}"
        return False, f"Wrong target: {CLAUDE_SYMLINK_SKILLS} → {resolved} (expected {canonical})"

    return False, f"Not a symlink: {CLAUDE_SYMLINK_SKILLS} is a regular directory"


def fix_claude_skills_symlink(*, dry_run: bool = False) -> str:
    """Create or fix the .agents/.claude/skills/ → .agents/skills/ junction."""
    is_valid, detail = check_claude_skills_symlink()
    if is_valid:
        return f"Already valid: {detail}"

    if dry_run:
        return f"Would create junction {CLAUDE_SYMLINK_SKILLS} → {CANONICAL_SKILLS_DIR}"

    # Remove existing if it's wrong
    if CLAUDE_SYMLINK_SKILLS.exists():
        if CLAUDE_SYMLINK_SKILLS.is_dir() and not _is_junction(CLAUDE_SYMLINK_SKILLS):
            # Regular directory — don't delete, might have content
            return f"Skipped: {CLAUDE_SYMLINK_SKILLS} is a real directory, won't overwrite"
        elif _is_junction(CLAUDE_SYMLINK_SKILLS) or CLAUDE_SYMLINK_SKILLS.is_symlink():
            os.remove(str(CLAUDE_SYMLINK_SKILLS))

    _create_junction(CANONICAL_SKILLS_DIR, CLAUDE_SYMLINK_SKILLS)
    return f"Created junction {CLAUDE_SYMLINK_SKILLS} → {CANONICAL_SKILLS_DIR}"


def check_claude_additional_dirs() -> tuple[bool, str]:
    """Check if Claude settings.json has .agents in additionalDirectories."""
    settings = _read_json(CLAUDE_SETTINGS_JSON)
    additional = settings.get("permissions", {}).get("additionalDirectories", [])

    agents_str = str(AGENTS_DIR)
    # Normalize for comparison
    for d in additional:
        if Path(d).resolve() == AGENTS_DIR.resolve():
            return True, f"OK: {agents_str} in additionalDirectories"

    return False, f"Missing: {agents_str} not in Claude additionalDirectories"
