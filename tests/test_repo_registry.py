import json

import pytest

from cad_chat_bridge.repo_manager.registry import (
    RegistryError,
    ensure_ref_allowed,
    get_repo_entry,
    repo_registry_list,
    validate_registry,
)


def _registry(tmp_path):
    path = tmp_path / "repos.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "repos": [
                    {
                        "repo_id": "demo",
                        "full_name": "putaojuju/demo",
                        "clone_url": "https://github.com/putaojuju/demo.git",
                        "default_branch": "main",
                        "allowed_ref_patterns": ["main", "task/*", "repo-manager-*"],
                        "enabled": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_repo_registry_list_returns_whitelisted_repos(tmp_path):
    path = _registry(tmp_path)

    result = repo_registry_list(path=path)

    assert result["success"] is True
    assert result["repos"][0]["repo_id"] == "demo"
    assert "clone_url" not in result["repos"][0]


def test_get_repo_entry_rejects_unknown_repo(tmp_path):
    path = _registry(tmp_path)

    with pytest.raises(RegistryError):
        get_repo_entry("missing", path=path)


def test_get_repo_entry_rejects_disabled_repo(tmp_path):
    path = tmp_path / "repos.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "repos": [
                    {
                        "repo_id": "demo",
                        "full_name": "putaojuju/demo",
                        "clone_url": "https://github.com/putaojuju/demo.git",
                        "allowed_ref_patterns": ["main"],
                        "enabled": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RegistryError):
        get_repo_entry("demo", path=path)


def test_validate_registry_rejects_clone_url_that_does_not_match_full_name():
    with pytest.raises(RegistryError):
        validate_registry(
            {
                "version": 1,
                "repos": [
                    {
                        "repo_id": "demo",
                        "full_name": "putaojuju/demo",
                        "clone_url": "https://github.com/other/demo.git",
                        "allowed_ref_patterns": ["main"],
                    }
                ],
            }
        )


def test_validate_registry_rejects_credentials_in_clone_url():
    with pytest.raises(RegistryError):
        validate_registry(
            {
                "version": 1,
                "repos": [
                    {
                        "repo_id": "demo",
                        "full_name": "putaojuju/demo",
                        "clone_url": "https://token@github.com/putaojuju/demo.git",
                        "allowed_ref_patterns": ["main"],
                    }
                ],
            }
        )


def test_ref_allowlist():
    entry = {
        "repo_id": "demo",
        "allowed_ref_patterns": ["main", "task/*", "repo-manager-*"],
    }

    assert ensure_ref_allowed(entry, "main") == "main"
    assert ensure_ref_allowed(entry, "task/abc") == "task/abc"
    with pytest.raises(RegistryError):
        ensure_ref_allowed(entry, "refs/heads/main")
    with pytest.raises(RegistryError):
        ensure_ref_allowed(entry, "feature/abc")
