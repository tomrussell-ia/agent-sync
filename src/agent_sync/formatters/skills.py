"""Skill distribution and symlink management."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from agent_sync.config import (
    AGENTS_DIR,
    CANONICAL_SKILLS_DIR,
    CLAUDE_SETTINGS_JSON,
    CLAUDE_SYMLINK_SKILLS,
    COPILOT_CONFIG_JSON,
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
        if _is_junction(CLAUDE_SYMLINK_SKILLS) or CLAUDE_SYMLINK_SKILLS.is_symlink():
            os.remove(str(CLAUDE_SYMLINK_SKILLS))

    _create_junction(CANONICAL_SKILLS_DIR, CLAUDE_SYMLINK_SKILLS)
    return f"Created junction {CLAUDE_SYMLINK_SKILLS} → {CANONICAL_SKILLS_DIR}"


def check_claude_additional_dirs() -> tuple[bool, str]:
    """Check if Claude settings.json has .agents in additionalDirectories.
    
    Returns (is_valid, detail_message).
    """
    settings = _read_json(CLAUDE_SETTINGS_JSON)
    additional = settings.get("permissions", {}).get("additionalDirectories", [])

    if not additional:
        return False, "Missing: No additionalDirectories configured"

    agents_str = str(AGENTS_DIR)
    # Normalize for comparison and validate
    for d in additional:
        d_path = Path(d)
        
        # Check if path exists
        if not d_path.exists():
            return False, f"Invalid: Path does not exist: {d}"
        
        # Check if it points to canonical skills (could be .agents or .agents/skills)
        resolved = d_path.resolve()
        canonical_skills = CANONICAL_SKILLS_DIR.resolve()
        canonical_agents = AGENTS_DIR.resolve()
        
        if resolved == canonical_skills:
            # Count skills in directory
            skill_count = sum(1 for sd in canonical_skills.iterdir() 
                            if sd.is_dir() and (sd / "SKILL.md").exists())
            return True, f"OK: {d} → {skill_count} skills accessible"
        
        if resolved == canonical_agents:
            # Points to .agents root (skills are in .agents/skills subdirectory)
            if canonical_skills.exists():
                skill_count = sum(1 for sd in canonical_skills.iterdir() 
                                if sd.is_dir() and (sd / "SKILL.md").exists())
                return True, f"OK: {d} (root) → {skill_count} skills accessible via subdirectory"
            return False, f"Invalid: {d} exists but skills subdirectory missing"

    return False, f"Missing: {agents_str} not in Claude additionalDirectories"


def check_copilot_additional_dirs() -> tuple[bool, str]:
    """Check if Copilot config.json has .agents/skills in additionalDirectories.
    
    Returns (is_valid, detail_message).
    """
    config = _read_json(COPILOT_CONFIG_JSON)
    additional = config.get("additionalDirectories", [])

    if not additional:
        return False, "Missing: No additionalDirectories configured"

    canonical_skills_str = str(CANONICAL_SKILLS_DIR)
    # Normalize for comparison and validate
    for d in additional:
        d_path = Path(d)
        
        # Check if path exists
        if not d_path.exists():
            return False, f"Invalid: Path does not exist: {d}"
        
        # Check if it points to canonical skills
        resolved = d_path.resolve()
        canonical_skills = CANONICAL_SKILLS_DIR.resolve()
        
        if resolved == canonical_skills:
            # Count skills in directory
            skill_count = sum(1 for sd in canonical_skills.iterdir() 
                            if sd.is_dir() and (sd / "SKILL.md").exists())
            return True, f"OK: {d} → {skill_count} skills accessible"

    return False, f"Missing: {canonical_skills_str} not in Copilot additionalDirectories"


def count_skills_in_additional_dirs(additional_dirs: list[str]) -> int:
    """Count skills accessible through additionalDirectories paths.
    
    Returns total count of accessible skills across all configured paths.
    """
    total_skills = 0
    canonical_skills = CANONICAL_SKILLS_DIR.resolve()
    
    for d in additional_dirs:
        d_path = Path(d)
        if not d_path.exists():
            continue
            
        resolved = d_path.resolve()
        
        # If pointing to canonical skills directory directly
        if resolved == canonical_skills:
            total_skills += sum(1 for sd in canonical_skills.iterdir() 
                              if sd.is_dir() and (sd / "SKILL.md").exists())
        # If pointing to .agents root, check skills subdirectory
        elif resolved == AGENTS_DIR.resolve() and canonical_skills.exists():
            total_skills += sum(1 for sd in canonical_skills.iterdir() 
                              if sd.is_dir() and (sd / "SKILL.md").exists())
    
    return total_skills


def fix_claude_additional_dirs(*, dry_run: bool = False) -> str:
    """Add .agents/skills to Claude additionalDirectories if missing.
    
    Returns description of action taken.
    """
    is_valid, detail = check_claude_additional_dirs()
    if is_valid:
        return f"Already valid: {detail}"
    
    canonical_skills_str = str(CANONICAL_SKILLS_DIR)
    
    if dry_run:
        return f"Would add {canonical_skills_str} to Claude additionalDirectories"
    
    import json
    
    settings = _read_json(CLAUDE_SETTINGS_JSON)
    
    # Ensure permissions section exists
    if "permissions" not in settings:
        settings["permissions"] = {}
    
    # Ensure additionalDirectories exists
    if "additionalDirectories" not in settings["permissions"]:
        settings["permissions"]["additionalDirectories"] = []
    
    # Add canonical skills path if not present
    additional = settings["permissions"]["additionalDirectories"]
    if canonical_skills_str not in additional:
        additional.append(canonical_skills_str)
    
    # Write back to file
    CLAUDE_SETTINGS_JSON.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    
    return f"Added {canonical_skills_str} to Claude additionalDirectories"


def fix_copilot_additional_dirs(*, dry_run: bool = False) -> str:
    """Add .agents/skills to Copilot additionalDirectories if missing.
    
    Returns description of action taken.
    """
    is_valid, detail = check_copilot_additional_dirs()
    if is_valid:
        return f"Already valid: {detail}"
    
    canonical_skills_str = str(CANONICAL_SKILLS_DIR)
    
    if dry_run:
        return f"Would add {canonical_skills_str} to Copilot additionalDirectories"
    
    import json
    
    config = _read_json(COPILOT_CONFIG_JSON)
    
    # Ensure additionalDirectories exists
    if "additionalDirectories" not in config:
        config["additionalDirectories"] = []
    
    # Add canonical skills path if not present
    additional = config["additionalDirectories"]
    if canonical_skills_str not in additional:
        additional.append(canonical_skills_str)
    
    # Write back to file
    COPILOT_CONFIG_JSON.parent.mkdir(parents=True, exist_ok=True)
    COPILOT_CONFIG_JSON.write_text(json.dumps(config, indent=2), encoding="utf-8")
    
    return f"Added {canonical_skills_str} to Copilot additionalDirectories"
