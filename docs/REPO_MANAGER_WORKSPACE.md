# Repo Manager + Script Workspace

This document describes PR #2A: Repo Manager + Script Workspace basics.

## Scope

PR #2A adds controlled local repository synchronization and task workspaces. It does not add CAD command execution or script execution.

Included tools:

- `repo_registry_list`
- `repo_status`
- `repo_sync`
- `repo_create_task_worktree`
- `workspace_status`
- `workspace_list_files`
- `workspace_read_file`
- `workspace_apply_patch`
- `workspace_list_artifacts`
- `workspace_read_log`

Explicitly not included:

- `lisp_load_staged`
- `lisp_run_registry_item`
- `python_run_registered`
- `cad_send_command`
- `cad_run_lisp`
- arbitrary Python execution
- arbitrary LISP execution

## Architecture

GitHub remains responsible for remote code and documentation changes. CAD Chat Bridge only syncs white-listed repository branches into local task worktrees and manages a script workspace.

```text
GitHub branch
  -> repo_sync
local mirror.git
  -> repo_create_task_worktree
repo/  (read-only source)
workspace/  (controlled writable area)
```

## Repo registry

The registry is local machine configuration and should not contain tokens. Private GitHub repository access must rely on the machine's existing git credential helper or `gh auth`, not on secrets stored in this registry.

Default registry path:

```text
%LOCALAPPDATA%/cad-chat-bridge/registry/repos.json
```

Override for tests or local development:

```powershell
$env:CAD_CHAT_BRIDGE_REPO_REGISTRY = "C:\path\to\repos.json"
```

Example:

```json
{
  "version": 1,
  "repos": [
    {
      "repo_id": "cad-chat-bridge",
      "full_name": "putaojuju/cad-chat-bridge",
      "clone_url": "https://github.com/putaojuju/cad-chat-bridge.git",
      "default_branch": "main",
      "allowed_ref_patterns": ["main", "repo-manager-*", "task/*"],
      "enabled": true
    }
  ]
}
```

## Local layout

Default bridge home:

```text
%LOCALAPPDATA%/cad-chat-bridge/
```

Override:

```powershell
$env:CAD_CHAT_BRIDGE_HOME = "D:\cad-chat-bridge-dev"
```

Layout:

```text
cad-chat-bridge/
  registry/
    repos.json

  repos/
    cad-chat-bridge/
      mirror.git/
      sync-status.json

  tasks/
    task-001/
      task.json
      repo/
      workspace/
        lisp/
        python/
        backups/
        artifacts/
        logs/
        manifest.json
```

## Repo read-only rule

The `repo/` directory is a synchronized task worktree and is treated as read-only by CAD Chat Bridge.

- Workspace tools reject writes outside `workspace/`.
- `workspace_apply_patch` cannot write into `repo/`.
- `repo_create_task_worktree` marks files read-only as a best-effort guard.

## Workspace write rules

`workspace_apply_patch` supports only `replace` semantics in PR #2A.

Allowed write roots:

```text
workspace/lisp/**
workspace/python/**
workspace/backups/**
workspace/artifacts/**
workspace/logs/**
```

Rejected paths:

```text
absolute paths
.. path traversal
network paths / UNC paths
.git
src
repo
```

Every write requires `expected_sha256`. Existing files are backed up before replacement.

For a new file, use an empty expected hash:

```text
""
```

## Example flow

1. List white-listed repos:

```json
{"tool": "repo_registry_list"}
```

2. Sync a branch:

```json
{
  "tool": "repo_sync",
  "repo_id": "cad-chat-bridge",
  "ref": "repo-manager-workspace-2a",
  "expected_remote": "putaojuju/cad-chat-bridge"
}
```

3. Create a task worktree:

```json
{
  "tool": "repo_create_task_worktree",
  "repo_id": "cad-chat-bridge",
  "ref": "repo-manager-workspace-2a",
  "task_id": "task-001"
}
```

4. Write a workspace file:

```json
{
  "tool": "workspace_apply_patch",
  "task_id": "task-001",
  "relative_path": "workspace/lisp/demo.lsp",
  "expected_sha256": "",
  "content": "(princ)"
}
```

## Path disclosure

Tool outputs return logical paths by default. Full local paths are only included when debug mode is explicitly enabled:

```powershell
$env:CAD_CHAT_BRIDGE_DEBUG_PATHS = "1"
```

Do not enable debug path output when sharing logs or screenshots.
