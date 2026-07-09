"""White-listed GitHub repo registry for local sync operations."""

from __future__ import annotations

import fnmatch
import json
import os
from pathlib import Path
from typing import Any

from cad_chat_bridge.repo_manager.security import bridge_home, response_path, validate_name

REGISTRY_ENV = "CAD_CHAT_BRIDGE_REPO_REGISTRY"
DEFAULT_ALLOWED_EXTENSIONS = (".lsp", ".py", ".md", ".json", ".txt")
INVALID_REF_CHARS = set(":~^?*[\\")


class RegistryError(ValueError):
    """Raised when a repo registry entry is invalid or unavailable."""


def default_registry_path() -> Path:
    """Return the default local repo registry path."""

    raw = os.environ.get(REGISTRY_ENV)
    if raw:
        return Path(raw).expanduser().resolve()
    return bridge_home() / "registry" / "repos.json"


def load_registry(path: str | Path | None = None) -> dict[str, Any]:
    """Load registry JSON. Missing registry returns an empty enabled list."""

    registry_path = Path(path).expanduser().resolve() if path is not None else default_registry_path()
    if not registry_path.exists():
        return {"version": 1, "repos": [], "path": registry_path}
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RegistryError("registry must be a JSON object")
    data.setdefault("version", 1)
    data.setdefault("repos", [])
    data["path"] = registry_path
    validate_registry(data)
    return data


def validate_registry(data: dict[str, Any]) -> None:
    """Validate registry shape and reject unsafe repository definitions."""

    repos = data.get("repos")
    if not isinstance(repos, list):
        raise RegistryError("registry.repos must be a list")
    seen: set[str] = set()
    for index, entry in enumerate(repos):
        prefix = f"repos[{index}]"
        if not isinstance(entry, dict):
            raise RegistryError(f"{prefix} must be an object")
        repo_id = validate_name(str(entry.get("repo_id", "")), field=f"{prefix}.repo_id")
        if repo_id in seen:
            raise RegistryError(f"duplicate repo_id: {repo_id}")
        seen.add(repo_id)
        full_name = entry.get("full_name")
        clone_url = entry.get("clone_url")
        if not isinstance(full_name, str) or "/" not in full_name:
            raise RegistryError(f"{prefix}.full_name must be owner/name")
        if not isinstance(clone_url, str) or not clone_url.startswith("https://github.com/"):
            raise RegistryError(f"{prefix}.clone_url must be an https://github.com URL")
        if clone_url.rstrip("/").removesuffix(".git") != f"https://github.com/{full_name}":
            raise RegistryError(f"{prefix}.clone_url must match full_name")
        for forbidden in ("token", "password", "secret", "@"):
            if forbidden in clone_url.lower():
                raise RegistryError(f"{prefix}.clone_url must not include credentials or tokens")
        patterns = entry.get("allowed_ref_patterns", [])
        if not isinstance(patterns, list) or not all(isinstance(item, str) for item in patterns):
            raise RegistryError(f"{prefix}.allowed_ref_patterns must be a list of strings")
        if not patterns:
            raise RegistryError(f"{prefix}.allowed_ref_patterns cannot be empty")
        extensions = entry.get("allowed_file_extensions", list(DEFAULT_ALLOWED_EXTENSIONS))
        if not isinstance(extensions, list) or not all(isinstance(item, str) for item in extensions):
            raise RegistryError(f"{prefix}.allowed_file_extensions must be a list of strings")


def get_repo_entry(repo_id: str, *, path: str | Path | None = None) -> dict[str, Any]:
    """Return an enabled registry entry by repo_id."""

    requested = validate_name(repo_id, field="repo_id")
    registry = load_registry(path)
    for entry in registry.get("repos", []):
        if entry.get("repo_id") == requested:
            if not entry.get("enabled", True):
                raise RegistryError(f"repo is disabled: {requested}")
            normalized = dict(entry)
            normalized.setdefault("default_branch", "main")
            normalized.setdefault("allowed_file_extensions", list(DEFAULT_ALLOWED_EXTENSIONS))
            normalized.setdefault("forbidden_path_parts", [".git", "src"])
            return normalized
    raise RegistryError(f"repo is not in registry whitelist: {requested}")


def validate_git_branch_ref(ref: str) -> str:
    """Validate a branch name before using it in a git refspec."""

    if not isinstance(ref, str) or not ref:
        raise RegistryError("invalid ref")
    if ref != ref.strip():
        raise RegistryError("invalid ref: leading or trailing whitespace")
    if any(ord(ch) < 32 or ord(ch) == 127 or ch.isspace() for ch in ref):
        raise RegistryError("invalid ref: whitespace/control characters are not allowed")
    if ref.startswith("-"):
        raise RegistryError("invalid ref: cannot start with '-'")
    if ref.startswith("/") or ref.endswith("/"):
        raise RegistryError("invalid ref: cannot start or end with '/'")
    if ref.startswith("refs/"):
        raise RegistryError("pass branch names, not raw refs")
    if ".." in ref or "//" in ref or "@{" in ref:
        raise RegistryError("invalid ref")
    if ref.endswith(".") or ref.endswith(".lock"):
        raise RegistryError("invalid ref")
    if any(ch in INVALID_REF_CHARS for ch in ref):
        raise RegistryError("invalid ref: contains a forbidden git ref character")
    for component in ref.split("/"):
        if not component or component.startswith(".") or component.endswith("."):
            raise RegistryError("invalid ref component")
    return ref


def ref_allowed(entry: dict[str, Any], ref: str) -> bool:
    """Return whether a ref matches the repo allowlist."""

    return any(fnmatch.fnmatchcase(ref, pattern) for pattern in entry.get("allowed_ref_patterns", []))


def ensure_ref_allowed(entry: dict[str, Any], ref: str) -> str:
    """Validate a branch/ref string against a registry entry."""

    validated = validate_git_branch_ref(ref)
    if not ref_allowed(entry, validated):
        raise RegistryError(f"ref is not allowed for repo {entry['repo_id']}: {validated}")
    return validated


def repo_registry_list(*, path: str | Path | None = None) -> dict[str, Any]:
    """Return the configured repo whitelist without local secrets or full local paths."""

    try:
        registry = load_registry(path)
        repos = []
        for entry in registry.get("repos", []):
            repos.append(
                {
                    "repo_id": entry.get("repo_id"),
                    "full_name": entry.get("full_name"),
                    "enabled": bool(entry.get("enabled", True)),
                    "default_branch": entry.get("default_branch", "main"),
                    "allowed_ref_patterns": list(entry.get("allowed_ref_patterns", [])),
                    "allowed_file_extensions": list(
                        entry.get("allowed_file_extensions", DEFAULT_ALLOWED_EXTENSIONS)
                    ),
                }
            )
        return {
            "success": True,
            "version": registry.get("version", 1),
            "registry": response_path(Path(registry["path"]), logical="registry/repos.json"),
            "repos": repos,
        }
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error_type": type(exc).__name__, "error": str(exc), "repos": []}
