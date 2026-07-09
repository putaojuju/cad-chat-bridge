"""Local git mirror and task worktree operations for white-listed repos."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cad_chat_bridge.repo_manager.registry import RegistryError, ensure_ref_allowed, get_repo_entry
from cad_chat_bridge.repo_manager.security import bridge_home, response_path, validate_name


class GitOperationError(RuntimeError):
    """Raised when a local git operation fails."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def repos_root() -> Path:
    return bridge_home() / "repos"


def tasks_root() -> Path:
    return bridge_home() / "tasks"


def mirror_path(repo_id: str) -> Path:
    return repos_root() / validate_name(repo_id, field="repo_id") / "mirror.git"


def task_root(task_id: str) -> Path:
    return tasks_root() / validate_name(task_id, field="task_id")


def task_repo_path(task_id: str) -> Path:
    return task_root(task_id) / "repo"


def task_workspace_path(task_id: str) -> Path:
    return task_root(task_id) / "workspace"


def task_manifest_path(task_id: str) -> Path:
    return task_root(task_id) / "task.json"


def run_git(args: list[str], *, cwd: Path | None = None) -> str:
    """Run git with shell=False and return stdout."""

    command = ["git", *args]
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            check=False,
            shell=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise GitOperationError("git executable was not found on PATH") from exc
    if completed.returncode != 0:
        raise GitOperationError(completed.stderr.strip() or completed.stdout.strip() or "git failed")
    return completed.stdout.strip()


def ref_commit(repo_id: str, ref: str) -> str:
    """Return commit SHA for a fetched ref in a local mirror."""

    mirror = mirror_path(repo_id)
    return run_git(["--git-dir", str(mirror), "rev-parse", f"refs/remotes/origin/{ref}^{{commit}"])


def _make_repo_read_only(path: Path) -> None:
    """Best-effort mark worktree files as read-only.

    This is defense-in-depth. Workspace tools also reject repo/ writes.
    """

    if not path.exists():
        return
    for root, dirs, files in os.walk(path):
        root_path = Path(root)
        for name in files:
            file_path = root_path / name
            try:
                file_path.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
            except OSError:
                pass
        for name in dirs:
            dir_path = root_path / name
            try:
                dir_path.chmod(stat.S_IREAD | stat.S_IEXEC | stat.S_IRGRP | stat.S_IXGRP)
            except OSError:
                pass


def _create_workspace_dirs(task_id: str) -> None:
    workspace = task_workspace_path(task_id)
    for subdir in ("lisp", "python", "backups", "artifacts", "logs"):
        (workspace / subdir).mkdir(parents=True, exist_ok=True)


def _load_task_manifest(task_id: str) -> dict[str, Any] | None:
    path = task_manifest_path(task_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_task_manifest(task_id: str, data: dict[str, Any]) -> None:
    path = task_manifest_path(task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def repo_sync(
    repo_id: str,
    ref: str,
    *,
    expected_remote: str | None = None,
    expected_commit: str | None = None,
) -> dict[str, Any]:
    """Fetch a white-listed repo/ref into the local mirror."""

    try:
        entry = get_repo_entry(repo_id)
        ensure_ref_allowed(entry, ref)
        if expected_remote and expected_remote != entry["full_name"]:
            raise RegistryError("expected_remote does not match registry full_name")
        mirror = mirror_path(repo_id)
        mirror.parent.mkdir(parents=True, exist_ok=True)
        created = False
        if not mirror.exists():
            run_git(["clone", "--mirror", entry["clone_url"], str(mirror)])
            created = True
        else:
            run_git(["--git-dir", str(mirror), "remote", "set-url", "origin", entry["clone_url"]])
        run_git(["--git-dir", str(mirror), "fetch", "origin", ref])
        commit = ref_commit(repo_id, ref)
        if expected_commit and commit != expected_commit:
            raise GitOperationError("expected_commit does not match fetched ref")
        status = {
            "last_fetch_at": _now_iso(),
            "ref": ref,
            "commit": commit,
            "clone_url_redacted": True,
        }
        (mirror.parent / "sync-status.json").write_text(
            json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {
            "success": True,
            "repo_id": repo_id,
            "full_name": entry["full_name"],
            "ref": ref,
            "commit": commit,
            "mirror_created": created,
            "mirror": response_path(mirror, root=bridge_home()),
        }
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error_type": type(exc).__name__, "error": str(exc)}


def repo_status(repo_id: str) -> dict[str, Any]:
    """Return local mirror and task worktree status for a white-listed repo."""

    try:
        entry = get_repo_entry(repo_id)
        mirror = mirror_path(repo_id)
        refs: list[dict[str, str]] = []
        if mirror.exists():
            output = run_git(["--git-dir", str(mirror), "for-each-ref", "--format=%(refname:strip=3) %(objectname)", "refs/remotes/origin"])
            for line in output.splitlines():
                if not line.strip():
                    continue
                name, commit = line.split(maxsplit=1)
                refs.append({"ref": name, "commit": commit})
        worktrees = []
        root = tasks_root()
        if root.exists():
            for task_dir in sorted(root.iterdir()):
                manifest = task_dir / "task.json"
                if not manifest.exists():
                    continue
                data = json.loads(manifest.read_text(encoding="utf-8"))
                if data.get("repo_id") != repo_id:
                    continue
                worktrees.append(
                    {
                        "task_id": data.get("task_id"),
                        "ref": data.get("ref"),
                        "commit": data.get("commit"),
                        "repo_read_only": bool(data.get("repo_read_only", True)),
                    }
                )
        return {
            "success": True,
            "repo_id": repo_id,
            "full_name": entry["full_name"],
            "mirror_exists": mirror.exists(),
            "mirror": response_path(mirror, root=bridge_home()),
            "known_refs": refs,
            "task_worktrees": worktrees,
        }
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error_type": type(exc).__name__, "error": str(exc)}


def repo_create_task_worktree(
    repo_id: str,
    ref: str,
    task_id: str,
    *,
    expected_commit: str | None = None,
) -> dict[str, Any]:
    """Create a task worktree from a synced mirror and initialize workspace dirs."""

    try:
        entry = get_repo_entry(repo_id)
        ensure_ref_allowed(entry, ref)
        validate_name(task_id, field="task_id")
        mirror = mirror_path(repo_id)
        if not mirror.exists():
            raise GitOperationError("mirror does not exist; call repo_sync first")
        commit = ref_commit(repo_id, ref)
        if expected_commit and commit != expected_commit:
            raise GitOperationError("expected_commit does not match local ref")
        root = task_root(task_id)
        repo_path = root / "repo"
        if root.exists():
            raise GitOperationError(f"task already exists: {task_id}")
        root.mkdir(parents=True)
        run_git(["--git-dir", str(mirror), "worktree", "add", "--detach", str(repo_path), commit])
        _make_repo_read_only(repo_path)
        _create_workspace_dirs(task_id)
        manifest = {
            "version": 1,
            "task_id": task_id,
            "repo_id": repo_id,
            "full_name": entry["full_name"],
            "ref": ref,
            "commit": commit,
            "created_at": _now_iso(),
            "repo_read_only": True,
            "workspace": {
                "lisp": "workspace/lisp",
                "python": "workspace/python",
                "backups": "workspace/backups",
                "artifacts": "workspace/artifacts",
                "logs": "workspace/logs",
            },
        }
        _write_task_manifest(task_id, manifest)
        return {
            "success": True,
            "repo_id": repo_id,
            "task_id": task_id,
            "ref": ref,
            "commit": commit,
            "repo": response_path(repo_path, root=root),
            "workspace": response_path(task_workspace_path(task_id), root=root),
            "repo_read_only": True,
        }
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error_type": type(exc).__name__, "error": str(exc)}


def get_existing_task(task_id: str) -> tuple[Path, dict[str, Any]]:
    """Return task root and manifest, or raise."""

    validate_name(task_id, field="task_id")
    root = task_root(task_id)
    manifest = _load_task_manifest(task_id)
    if manifest is None:
        raise FileNotFoundError(f"unknown task_id: {task_id}")
    return root, manifest
