"""Small JSON response helpers for MCP tools."""

from __future__ import annotations

import json
from typing import Any


def dumps(payload: Any) -> str:
    """Return a stable, human-readable JSON string."""

    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def ok(**data: Any) -> dict[str, Any]:
    """Build a successful response payload."""

    return {"success": True, **data}


def error(message: str, *, error_type: str | None = None, **data: Any) -> dict[str, Any]:
    """Build an error response payload without raising through the MCP boundary."""

    payload: dict[str, Any] = {"success": False, "error": message}
    if error_type:
        payload["error_type"] = error_type
    payload.update(data)
    return payload
