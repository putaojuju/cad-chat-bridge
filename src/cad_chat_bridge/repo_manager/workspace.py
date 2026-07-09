"""Task script workspace file operations."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cad_chat_bridge.repo_manager.git_ops import get_existing_task, task_workspace_path
from cad_chat_bridge.repo_manager.security import (
    ensure_workspace_read_path,
    ensure_workspace_write_path,
    logical_from_task_root,
    response_path,
    sha256_file,
)

MAX_READ_BYTES = 256 * 1024


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _file_entry(task_root: Path, path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "logical_path": logical_from_task_root(task_root, path),
        "size_bytes": stat.st_size,
        "sha256": sha256_file(path),
        "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }


def workspace_status(task_id: str) -> dict[str, Any]:
    """Return workspace directory status."""

    try:
        task_root, manifest = get_existing_task(task_id)
        workspace = task_workspace_path(task_id)
        dirs = {}
        for name in ("lisp", "python", "backups", "artifacts", "logs"):
            path = workspace / name
            path.mkdir(parents=True, exist_ok=True)
            dirs[name] = response_path(path, root=task_root)
        return {
            "success": True,
            "task_id": task_id,
            "repo_id": manifest.get("repo_id"),
            "ref": manifest.get("ref"),
            "commit": manifest.get("commit"),
            "repo_read_only": bool(manifest.get("repo_read_only", True)),
            "workspace": response_path(workspace, root=task_root),
            "dirs": dirs,
        }
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error_type": type(exc).__name__, "error": str(exc)}


def workspace_list_files(
    task_id: str,
    *,
    subdir: str = "workspace",
    pattern: str = "*",
    max_results: int = 100,
) -> dict[str, Any]:
    """List files under workspace only."""

    try:
        task_root, _manifest = get_existing_task(task_id)
        base = ensure_workspace_read_path(task_root, subdir)
        if not base.exists():
            return {"success": True, "task_id": task_id, "files": []}
        results = []
        for path in sorted(base.rglob(pattern)):
            if not path.is_file():
                continue
            results.append(_file_entry(task_root, path))
            if len(results) >= max(1, int(max_results)):
                break
        return {"success": True, "task_id": task_id, "files": results}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error_type": type(exc).__name__, "error": str(exc)}


def workspace_read_file(
    task_id: str,
    relative_path: str,
    *,
    max_bytes: int = MAX_READ_BYTES,
) -> dict[str, Any]:
    """Read a UTF-8 text file from workspace."""

    try:
        task_root, _manifest = get_existing_task(task_id)
        path = ensure_workspace_read_path(task_root, relative_path)
        if not path.is_file():
            raise FileNotFoundError(relative_path)
        size = path.stat().st_size
        if size > int(max_bytes):
            raise ValueError(f"file exceeds max_bytes: {size} > {max_bytes}")
        content = path.read_text(encoding="utf-8")
        return {
            "success": True,
            "task_id": task_id,
            "file": _file_entry(task_root, path),
            "content": content,
        }
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error_type": type(exc).__name__, "error": str(exc)}


def workspace_apply_patch(
    task_id: str,
    relative_path: str,
    *,
    expected_sha256: str,
    content: str,
) -> dict[str, Any]:
    """Apply a replace patch inside workspace with hash check and backup."""

    try:
        if not expected_sha256:
            raise ValueError("expected_sha256 is required")
        task_root, _manifest = get_existing_task(task_id)
        target = ensure_workspace_write_path(task_root, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        exists = target.exists()
        old_sha = sha256_file(target) if exists else ""
        if old_sha != expected_sha256:
            return {
                "success": False,
                "error_type": "HashMismatch",
                "error": "expected_sha256 does not match current file",
                "expected_sha256": expected_sha256,
                "actual_sha256": old_sha,
            }

        backup_info = None
        if exists:
            backup_dir = task_workspace_path(task_id) / "backups" / _now_stamp()
            backup_dir.mkdir(parents=True, exist_ok=True)
            safe_name = logical_from_task_root(task_root, target).replace("/", "__")
            backup_path = backup_dir / f"{safe_name}.bak"
            shutil.copy2(target, backup_path)
            backup_info = _file_entry(task_root, backup_path)

        target.write_text(content, encoding="utf-8")
        new_sha = sha256_file(target)
        return {
            "success": True,
            "task_id": task_id,
            "patch_type": "replace",
            "file": _file_entry(task_root, target),
            "old_sha256": old_sha,
            "new_sha256": new_sha,
            "backup": backup_info,
        }
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error_type": type(exc).__name__, "error": str(exc)}


def workspace_list_artifacts(task_id: str, *, max_results: int = 100) -> dict[str, Any]:
    """List workspace artifacts."""

    return workspace_list_files(
        task_id, subdir="workspace/artifacts", pattern="*", max_results=max_results
    )


def workspace_read_log(task_id: str, relative_path: str, *, max_bytes: int = MAX_READ_BYTES) -> dict[str, Any]:
    """Read a log file under workspace/logs."""

    try:
        if not relative_path.startswith("workspace/logs/"):
            relative_path = f"workspace/logs/{relative_path}"
        return workspace_read_file(task_id, relative_path, max_bytes=max_bytes)
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error_type": type(exc).__name__, "error": str(exc)}


def workspace_manifest(task_id: str) -> dict[str, Any]:
    """Return a compact manifest for future staging tools."""

    try:
        task_root, manifest = get_existing_task(task_id)
        manifest_path = task_root / "workspace" / "manifest.json"
        if not manifest_path.exists():
            manifest_path.write_text(
                json.dumps({"version": 1, "task_id": task_id, "items": []}, indent=2),
                encoding="utf-8",
            )
        return {
            "success": True,
            "task_id": task_id,
            "repo_id": manifest.get("repo_id"),
            "manifest": _file_entry(task_root, manifest_path),
        }
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error_type": type(exc).__name__, "error": str(exc)}
