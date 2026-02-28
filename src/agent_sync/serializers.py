"""JSON serialization for agent-sync dataclass models.

Provides ``to_dict`` and ``to_json`` that handle Enum, Path, and
computed ``@property`` fields — everything needed for ``--json``
output without adding extra dependencies.
"""

from __future__ import annotations

import dataclasses
import json
from enum import Enum
from pathlib import Path
from typing import Any


def _normalize(obj: Any) -> Any:
    """Recursively convert Enum → ``.value`` and Path → ``str``.

    Works on the nested dict/list tree produced by
    ``dataclasses.asdict``, reaching into lists and dict keys.
    """
    if isinstance(obj, dict):
        return {_normalize(k): _normalize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_normalize(v) for v in obj]
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, Path):
        return str(obj)
    return obj


# Map of (dataclass type name) → list of @property names to include in
# serialised output.  Keeps the serialiser generic — just add a new entry
# when a model gains computed properties.
_COMPUTED_PROPERTIES: dict[str, list[str]] = {
    "SyncReport": [
        "synced_count",
        "drift_count",
        "missing_count",
        "extra_count",
        "fixable_count",
        "overall_status",
    ],
    "ProbeReport": [
        "ok_count",
        "error_count",
        "timeout_count",
        "skipped_count",
        "overall_status",
    ],
    "PluginValidation": [
        "status",
    ],
    "LogReport": [
        "connected_servers",
        "errored_servers",
        "auth_errors",
    ],
}


def to_dict(obj: Any) -> dict[str, Any]:
    """Convert a dataclass instance to a plain dict.

    * Enum values → their ``.value`` string.
    * Path objects → ``str(path)``.
    * ``@property`` fields listed in ``_COMPUTED_PROPERTIES`` are injected
      into a top-level ``"summary"`` key so consumers don't need to
      recompute them.
    """
    if not dataclasses.is_dataclass(obj) or isinstance(obj, type):
        msg = f"Expected a dataclass instance, got {type(obj).__name__}"
        raise TypeError(msg)

    raw = dataclasses.asdict(obj)
    result = _normalize(raw)

    # Inject computed properties
    cls_name = type(obj).__name__
    prop_names = _COMPUTED_PROPERTIES.get(cls_name)
    if prop_names:
        summary: dict[str, Any] = {}
        for name in prop_names:
            val = getattr(obj, name, None)
            summary[name] = _normalize(val) if isinstance(val, (Enum, Path)) else val
            # Handle sets from LogReport computed props
            if isinstance(summary[name], (set, frozenset)):
                summary[name] = sorted(summary[name])
        result["summary"] = summary

    return result


def to_json(obj: Any, **kwargs: Any) -> str:
    """Serialize a dataclass instance to a JSON string.

    Accepts any extra keyword arguments for ``json.dumps``
    (e.g. ``indent=2``).  Defaults to ``indent=2`` when not specified.
    """
    kwargs.setdefault("indent", 2)
    return json.dumps(to_dict(obj), **kwargs)
