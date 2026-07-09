# Current Project Handoff

This file is the durable handoff for continuing CAD Chat Bridge / AutoCAD MCP work across ChatGPT conversations. Keep it short, current, and safe to paste into a new chat.

## Current status

- `putaojuju/cad-chat-bridge` has a working ChatGPT connector path through the dev HTTP MCP fallback and an ngrok HTTPS URL ending in `/mcp`.
- The ChatGPT connector has successfully called these MVP tools:
  - `cad_ping`
  - `cad_list_catalog`
  - `cad_describe_catalog_item`
  - `cad_diagnose_access`
  - `cad_get_active_document`
- AutoCAD COM access works when AutoCAD and the Python/MCP process run at the same Windows integrity level.
- The HTTP connector mode does not expose `allow_start` for `cad_get_active_document`.
- The HTTP connector mode redacts `full_name` and diagnostic window titles by default.
- The current connector must not expose arbitrary AutoCAD commands, arbitrary AutoLISP execution, arbitrary Python execution, save/save-as operations, or unrestricted file writes.

## Active repositories

- `putaojuju/cad-chat-bridge`
  - Public connector project.
  - Current active branch/PR: `init-mvp-skeleton` / PR #1.
  - Purpose: ChatGPT-facing local bridge to AutoCAD.
- `putaojuju/autocad-mcp`
  - Private project with existing CAD automation, DXF analysis, internal retrieval, worklogs, and AutoLISP/plugin experiments.
  - `main` currently includes the CAD Index P3 shared explorer and a hardening/worklog commit.

## Current design direction

Do not build a general CAD command remote-control system. The preferred workflow is file-based and registry-based:

1. GitHub connector searches and edits remote code/docs on branches/PRs.
2. CAD Chat Bridge syncs only whitelisted repos/refs to a local task worktree.
3. LISP/Python files are staged into controlled workspace directories.
4. Files are analyzed/validated before load or run.
5. AutoLISP load/run must go through staged files and registry-approved commands.
6. Python execution, when added later, must go through registry-approved scripts, fixed cwd, `shell=False`, timeout, and logs/artifacts.
7. Logs and artifacts are read back into ChatGPT for the edit-run-read-log loop.

## Branch policy

- `main` should be treated as the stable line.
- Avoid direct pushes to `main`; use short-lived feature/fix/docs branches and PRs.
- Do not continue new development on `feature/cad-index-p3-shared-explorer`; its original purpose is complete.
- Use clear branch names such as:
  - `feature/script-workspace-mvp`
  - `feature/lisp-registry-runner`
  - `feature/repo-manager-workspace`
  - `fix/http-mcp-appsdk-headers`
- Each branch should do one task and be deleted after merge.

## Next planned work

The next implementation should be PR #2A: Repo Manager + Script Workspace foundation.

Recommended scope:

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

PR #2A should focus on local repo/task/workspace foundations only.

Do not implement in PR #2A:

- `cad_send_command(command)`
- `cad_run_lisp(lisp_code)`
- arbitrary Python execution
- arbitrary LISP execution
- `lisp_load_staged`
- `lisp_run_registry_item`
- `python_run_registered`

## Repo Manager / Workspace rules

- Repos must come from a local registry allowlist.
- Users pass `repo_id`, not arbitrary clone URLs.
- Private GitHub access should rely on local git credentials or `gh auth`, not tokens stored in MCP config or logs.
- Task worktrees should be created under connector-controlled task directories.
- `repo/` should be treated as a synced source and not directly modified by the AutoCAD connector.
- AI-writable files should live under `workspace/` only.

Recommended workspace layout:

```text
tasks/<task_id>/
  task.json
  repo/
  workspace/
    lisp/
    python/
    backups/
    artifacts/
    logs/
    manifest.json
trusted-lisp/<task_id>/
```

`workspace_apply_patch` rules:

- First version should support `replace` only; defer unified diff.
- Require `expected_sha256`.
- Write a backup before every write.
- Only allow writes under:
  - `workspace/lisp/**`
  - `workspace/python/**`
  - `workspace/backups/**`
  - `workspace/artifacts/**`
  - `workspace/logs/**`
- Reject absolute paths, `..`, network/UNC paths, `.git`, `src`, `repo`, `node_modules`, and `__pycache__`.
- Return logical paths by default, not full local user paths.

## Future stages

- PR #2B: LISP staging + validation + safe load.
- PR #2C: Python staging + static analysis only.
- Later PR: registry-approved LISP run with status/log/artifact readback.
- Later PR: registry-approved Python run with timeout, fixed cwd, `shell=False`, env whitelist, and artifacts/logs.

## Known operational notes

- AutoCAD and Python/MCP must run at the same Windows integrity level.
- The dev HTTP connector uses ngrok during testing; both the HTTP server and ngrok process must stay running.
- If ChatGPT connector creation fails, inspect `http://127.0.0.1:4040` for ngrok request paths/status codes.
- The initial connector wizard required Apps SDK HTTP compatibility: JSON response mode, stateless HTTP, and relaxed host/origin handling for the dev tunnel.
- Keep these dev HTTP compatibility changes committed in PR #1 so the connector can be recreated later.

## New conversation bootstrap prompt

Paste this into a new ChatGPT development/review conversation if the current chat reaches its length limit:

```text
This is a continuation of the CAD Chat Bridge / AutoCAD MCP project.

Please first inspect:
1. `putaojuju/cad-chat-bridge`, especially PR #1 and `docs/HANDOFF_CURRENT.md`.
2. `putaojuju/autocad-mcp`, especially `main`, `docs/CAD_AUTOMATION_WORKLOG.md`, and the recent AutoCAD MCP hardening/worklog commit.

Current status:
- ChatGPT can connect to CAD Chat Bridge through dev HTTP MCP + ngrok.
- `cad_ping`, `cad_list_catalog`, `cad_describe_catalog_item`, `cad_diagnose_access`, and `cad_get_active_document` were verified.
- AutoCAD COM works when AutoCAD and Python/MCP have matching Windows integrity levels.
- The project direction is not arbitrary CAD command execution. It is repo sync + script workspace + LISP/Python staging + registry-approved load/run + logs/artifacts.

Next task:
Design or implement PR #2A: Repo Manager + Script Workspace foundation.
Do not add `cad_send_command`, `cad_run_lisp`, arbitrary Python execution, arbitrary LISP execution, or direct writes outside the workspace.
```
