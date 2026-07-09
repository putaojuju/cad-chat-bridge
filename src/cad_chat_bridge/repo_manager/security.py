"""Path and hash safety helpers for repo manager workspaces."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import Any

HOME_ENV = "CAD_CHAT_BRIDGE_HOME"
DEBUG_PATHS_ENV = "CAD_CHAT_BRIDGE_DEBUG_PATHS"
ALLOWED_WORKSPACE_PREFIXES = (
    "workspace/lisp",
    "workspace/python",
    "workspace/backups",
    "workspace/artifacts",
    "workspace/logs",
)
WINDOWS_DRIVE_RE = re.compile(r"^[a-zA-Z]:[\\/]")


def bridge_home() -> Path:
    """Return the local bridge home directory."""

    raw = os.environ.get(HOME_ENV)
    if raw:
        return Path(raw).expanduser().resolve()
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return (Path(local_app_data) / "cad-chat-bridge").resolve()
    return (Path(tempfile.gettempdir()) / "cad-chat-bridge").resolve()


def debug_paths_enabled() -> bool:
    """Return whether responses may include absolute local paths."""

    return os.environ.get(DEBUG_PATHS_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def response_path(path: Path, *, root: Path | None = None, logical: str | None = None) -> dict[str, Any]:
    """Return logical path by default and local path only in debug mode."""

    result: dict[str, Any] = {}
    if logical is not None:
        result["logical_path"] = logical.replace("\\", "/")
    elif root is not None:
        result["logical_path"] = path.resolve().relative_to(root.resolve()).as_posix()
    else:
        result["logical_path"] = path.name
    if debug_paths_enabled():
        result["local_path"] = str(path.resolve())
    return result


def sha256_file(path: Path) -> str:
    """Return SHA-256 for a file."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_name(value: str, *, field: str) -> str:
    """Validate a user-visible id segment such as repo_id or task_id."""

    if not value or not all(ch.isalnum() or ch in {"-", "_", "."} for ch in value):
        raise ValueError(f"{field} must contain only letters, numbers, '-', '_' or '.'")
    if value in {".", ".."}:
        raise ValueError(f"{field} cannot be '.' or '..'")
    return value


def _reject_network_or_absolute_path(raw: str) -> None:
    normalized = raw.replace("\\", "/")
    if normalized.startswith("//") or raw.startswith("\\\\"):
        raise ValueError("network paths are not allowed")
    if WINDOWS_DRIVE_RE.match(raw):
        raise ValueError("absolute paths are not allowed")


def safe_relative_path(raw_path: str | Path, *, allow_src: bool = False) -> Path:
    """Validate and normalize a caller-provided relative path."""

    raw = str(raw_path)
    _reject_network_or_absolute_path(raw)
    candidate = Path(raw)
    if candidate.is_absolute():
        raise ValueError("absolute paths are not allowed")
    parts = candidate.parts
    if not parts:
        raise ValueError("path cannot be empty")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("'.' and '..' path segments are not allowed")
    for part in parts:
        if part == ".git":
            raise ValueError(".git paths are not allowed")
        if part == "src" and not allow_src:
            raise ValueError("src paths are not writable through the AutoCAD connector")
    return Path(*parts)


def ensure_under_root(root: Path, relative_path: str | Path, *, allow_src: bool = False) -> Path:
    """Resolve a relative path under root and prove it stays there."""

    relative = safe_relative_path(relative_path, allow_src=allow_src)
    root_resolved = root.resolve()
    candidate = (root_resolved / relative).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("path escapes root") from exc
    return candidate


def ensure_workspace_write_path(task_root: Path, relative_path: str | Path) -> Path:
    """Return a safe writable workspace path for workspace_apply_patch."""

    relative = safe_relative_path(relative_path, allow_src=False).as_posix()
    if not any(relative == prefix or relative.startswith(prefix + "/") for prefix in ALLOWED_WORKSPACE_PREFIXES):
        raise ValueError(
            "writes are only allowed inside workspace/lisp, workspace/python, "
            "workspace/backups, workspace/artifacts or workspace/logs"
        )
    return ensure_under_root(task_root, relative, allow_src=False)


def ensure_workspace_read_path(task_root: Path, relative_path: str | Path) -> Path:
    """Return a safe readable workspace path."""

    relative = safe_relative_path(relative_path, allow_src=False).as_posix()
    if not relative.startswith("workspace/"):
        raise ValueError("workspace reads must stay under workspace/")
    return ensure_under_root(task_root, relative, allow_src=False)


def logical_from_task_root(task_root: Path, path: Path) -> str:
    """Return logical task-relative path."""

    return path.resolve().relative_to(task_root.resolve()).as_posix()
