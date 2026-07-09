import json

from cad_chat_bridge.repo_manager.git_ops import task_root, task_workspace_path
from cad_chat_bridge.repo_manager.security import HOME_ENV, sha256_file
from cad_chat_bridge.repo_manager.workspace import (
    workspace_apply_patch,
    workspace_list_artifacts,
    workspace_list_files,
    workspace_read_file,
    workspace_read_log,
    workspace_status,
)


def _make_task(tmp_path, monkeypatch, task_id="task-001"):
    monkeypatch.setenv(HOME_ENV, str(tmp_path))
    root = task_root(task_id)
    workspace = task_workspace_path(task_id)
    for subdir in ("lisp", "python", "backups", "artifacts", "logs"):
        (workspace / subdir).mkdir(parents=True, exist_ok=True)
    (root / "repo").mkdir(parents=True, exist_ok=True)
    (root / "task.json").write_text(
        json.dumps(
            {
                "version": 1,
                "task_id": task_id,
                "repo_id": "demo",
                "ref": "main",
                "commit": "abc123",
                "repo_read_only": True,
            }
        ),
        encoding="utf-8",
    )
    return root, workspace


def test_workspace_status_creates_logical_paths(tmp_path, monkeypatch):
    _root, _workspace = _make_task(tmp_path, monkeypatch)

    result = workspace_status("task-001")

    assert result["success"] is True
    assert result["repo_read_only"] is True
    assert result["workspace"]["logical_path"] == "workspace"
    assert "local_path" not in result["workspace"]


def test_workspace_apply_patch_new_file_with_empty_expected_hash(tmp_path, monkeypatch):
    _root, _workspace = _make_task(tmp_path, monkeypatch)

    result = workspace_apply_patch(
        "task-001",
        "workspace/lisp/demo.lsp",
        expected_sha256="",
        content="(princ)",
    )

    assert result["success"] is True
    assert result["file"]["logical_path"] == "workspace/lisp/demo.lsp"
    assert result["backup"] is None


def test_workspace_apply_patch_hash_mismatch(tmp_path, monkeypatch):
    _root, workspace = _make_task(tmp_path, monkeypatch)
    target = workspace / "lisp" / "demo.lsp"
    target.write_text("old", encoding="utf-8")

    result = workspace_apply_patch(
        "task-001",
        "workspace/lisp/demo.lsp",
        expected_sha256="wrong",
        content="new",
    )

    assert result["success"] is False
    assert result["error_type"] == "HashMismatch"
    assert target.read_text(encoding="utf-8") == "old"


def test_workspace_apply_patch_creates_backup_before_replace(tmp_path, monkeypatch):
    _root, workspace = _make_task(tmp_path, monkeypatch)
    target = workspace / "lisp" / "demo.lsp"
    target.write_text("old", encoding="utf-8")
    old_sha = sha256_file(target)

    result = workspace_apply_patch(
        "task-001",
        "workspace/lisp/demo.lsp",
        expected_sha256=old_sha,
        content="new",
    )

    assert result["success"] is True
    assert result["backup"] is not None
    backup_path = tmp_path / "tasks" / "task-001" / result["backup"]["logical_path"]
    assert backup_path.read_text(encoding="utf-8") == "old"
    assert target.read_text(encoding="utf-8") == "new"


def test_workspace_apply_patch_rejects_repo_and_src_and_path_escape(tmp_path, monkeypatch):
    _make_task(tmp_path, monkeypatch)

    assert workspace_apply_patch(
        "task-001", "repo/file.lsp", expected_sha256="", content="x"
    )["success"] is False
    assert workspace_apply_patch(
        "task-001", "workspace/src/file.py", expected_sha256="", content="x"
    )["success"] is False
    assert workspace_apply_patch(
        "task-001", "workspace/lisp/../escape.lsp", expected_sha256="", content="x"
    )["success"] is False


def test_workspace_apply_patch_rejects_absolute_and_network_paths(tmp_path, monkeypatch):
    _make_task(tmp_path, monkeypatch)

    assert workspace_apply_patch(
        "task-001", "/tmp/escape.lsp", expected_sha256="", content="x"
    )["success"] is False
    assert workspace_apply_patch(
        "task-001", r"\\server\share\x.lsp", expected_sha256="", content="x"
    )["success"] is False


def test_workspace_list_and_read_files_artifacts_logs(tmp_path, monkeypatch):
    _root, workspace = _make_task(tmp_path, monkeypatch)
    (workspace / "artifacts" / "result.json").write_text("{}", encoding="utf-8")
    (workspace / "logs" / "run.log").write_text("log", encoding="utf-8")

    artifacts = workspace_list_artifacts("task-001")
    assert artifacts["success"] is True
    assert artifacts["files"][0]["logical_path"] == "workspace/artifacts/result.json"

    log = workspace_read_log("task-001", "run.log")
    assert log["success"] is True
    assert log["content"] == "log"

    files = workspace_list_files("task-001", subdir="workspace")
    assert files["success"] is True
    assert any(item["logical_path"] == "workspace/logs/run.log" for item in files["files"])

    read = workspace_read_file("task-001", "workspace/artifacts/result.json")
    assert read["content"] == "{}"
