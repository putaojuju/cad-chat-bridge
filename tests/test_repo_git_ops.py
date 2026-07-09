import json
from pathlib import Path

import cad_chat_bridge.repo_manager.git_ops as git_ops
from cad_chat_bridge.repo_manager.security import HOME_ENV


ENTRY = {
    "repo_id": "demo",
    "full_name": "putaojuju/demo",
    "clone_url": "https://github.com/putaojuju/demo.git",
    "allowed_ref_patterns": ["main", "task/*", "repo-manager-*"],
    "enabled": True,
}


def test_repo_sync_uses_registry_and_shell_false(tmp_path, monkeypatch):
    monkeypatch.setenv(HOME_ENV, str(tmp_path))
    calls = []

    def fake_get_repo_entry(repo_id):
        assert repo_id == "demo"
        return ENTRY

    def fake_run_git(args, *, cwd=None):
        calls.append({"args": args, "cwd": cwd})
        if "rev-parse" in args:
            return "abc123"
        return ""

    monkeypatch.setattr(git_ops, "get_repo_entry", fake_get_repo_entry)
    monkeypatch.setattr(git_ops, "run_git", fake_run_git)

    result = git_ops.repo_sync("demo", "main", expected_remote="putaojuju/demo")

    assert result["success"] is True
    assert result["commit"] == "abc123"
    assert any(call["args"][:2] == ["clone", "--mirror"] for call in calls)
    assert all(isinstance(call["args"], list) for call in calls)
    assert "clone_url" not in result
    assert (tmp_path / "repos" / "demo" / "sync-status.json").exists()


def test_repo_sync_rejects_non_whitelisted_ref(tmp_path, monkeypatch):
    monkeypatch.setenv(HOME_ENV, str(tmp_path))
    monkeypatch.setattr(git_ops, "get_repo_entry", lambda repo_id: ENTRY)

    result = git_ops.repo_sync("demo", "feature/not-allowed")

    assert result["success"] is False
    assert result["error_type"] == "RegistryError"


def test_repo_sync_expected_commit_mismatch(tmp_path, monkeypatch):
    monkeypatch.setenv(HOME_ENV, str(tmp_path))
    monkeypatch.setattr(git_ops, "get_repo_entry", lambda repo_id: ENTRY)
    monkeypatch.setattr(git_ops, "run_git", lambda args, cwd=None: "actual" if "rev-parse" in args else "")

    result = git_ops.repo_sync("demo", "main", expected_commit="expected")

    assert result["success"] is False
    assert result["error_type"] == "GitOperationError"


def test_repo_create_task_worktree_creates_read_only_repo_and_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv(HOME_ENV, str(tmp_path))
    mirror = git_ops.mirror_path("demo")
    mirror.mkdir(parents=True)
    calls = []

    def fake_run_git(args, *, cwd=None):
        calls.append(args)
        if "rev-parse" in args:
            return "abc123"
        if "worktree" in args and "add" in args:
            repo_path = Path(args[-2])
            repo_path.mkdir(parents=True)
            (repo_path / "README.md").write_text("repo", encoding="utf-8")
        return ""

    monkeypatch.setattr(git_ops, "get_repo_entry", lambda repo_id: ENTRY)
    monkeypatch.setattr(git_ops, "run_git", fake_run_git)

    result = git_ops.repo_create_task_worktree("demo", "main", "task-001", expected_commit="abc123")

    assert result["success"] is True
    assert result["repo_read_only"] is True
    root = tmp_path / "tasks" / "task-001"
    assert (root / "repo" / "README.md").exists()
    for subdir in ("lisp", "python", "backups", "artifacts", "logs"):
        assert (root / "workspace" / subdir).is_dir()
    manifest = json.loads((root / "task.json").read_text(encoding="utf-8"))
    assert manifest["repo_read_only"] is True
    assert manifest["commit"] == "abc123"
    assert any("worktree" in call for call in calls)


def test_repo_create_task_worktree_requires_existing_mirror(tmp_path, monkeypatch):
    monkeypatch.setenv(HOME_ENV, str(tmp_path))
    monkeypatch.setattr(git_ops, "get_repo_entry", lambda repo_id: ENTRY)

    result = git_ops.repo_create_task_worktree("demo", "main", "task-001")

    assert result["success"] is False
    assert result["error_type"] == "GitOperationError"
