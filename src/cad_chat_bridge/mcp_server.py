"""MCP server entry point for CAD Chat Bridge."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cad_chat_bridge import __version__
from cad_chat_bridge.autocad.com_client import get_active_document
from cad_chat_bridge.autocad.diagnostics import diagnose_access
from cad_chat_bridge.catalog.loader import describe_catalog_item, list_catalog
from cad_chat_bridge.jsonutil import dumps, ok
from cad_chat_bridge.repo_manager.git_ops import (
    repo_create_task_worktree as repo_create_task_worktree_payload,
)
from cad_chat_bridge.repo_manager.git_ops import repo_status as repo_status_payload
from cad_chat_bridge.repo_manager.git_ops import repo_sync as repo_sync_payload
from cad_chat_bridge.repo_manager.registry import repo_registry_list as repo_registry_list_payload
from cad_chat_bridge.repo_manager.workspace import (
    workspace_apply_patch as workspace_apply_patch_payload,
)
from cad_chat_bridge.repo_manager.workspace import workspace_list_artifacts as workspace_list_artifacts_payload
from cad_chat_bridge.repo_manager.workspace import workspace_list_files as workspace_list_files_payload
from cad_chat_bridge.repo_manager.workspace import workspace_read_file as workspace_read_file_payload
from cad_chat_bridge.repo_manager.workspace import workspace_read_log as workspace_read_log_payload
from cad_chat_bridge.repo_manager.workspace import workspace_status as workspace_status_payload


MVP_TOOLS = (
    "cad_ping",
    "cad_diagnose_access",
    "cad_get_active_document",
    "cad_list_catalog",
    "cad_describe_catalog_item",
)

REPO_WORKSPACE_TOOLS = (
    "repo_registry_list",
    "repo_status",
    "repo_sync",
    "repo_create_task_worktree",
    "workspace_status",
    "workspace_list_files",
    "workspace_read_file",
    "workspace_apply_patch",
    "workspace_list_artifacts",
    "workspace_read_log",
)

REGISTERED_TOOLS = (*MVP_TOOLS, *REPO_WORKSPACE_TOOLS)

DANGEROUS_TOOLS_NOT_REGISTERED = (
    "cad_run_lisp",
    "cad_send_command",
    "cad_load_lisp",
    "cad_save_as",
    "cad_write_file",
    "lisp_load_staged",
    "lisp_run_registry_item",
    "python_run_registered",
    "python_exec",
)

PayloadFilter = Callable[[dict[str, Any]], dict[str, Any]]


def registered_tools_for(*, enable_workspace_tools: bool = True) -> tuple[str, ...]:
    """Return the actual tool set for a transport instance."""

    if enable_workspace_tools:
        return REGISTERED_TOOLS
    return MVP_TOOLS


def ping_payload(
    *,
    transport: str = "stdio",
    tools: tuple[str, ...] | None = None,
    workspace_tools_enabled: bool = True,
) -> dict[str, Any]:
    """Return the static server capability payload used by cad_ping."""

    active_tools = tools if tools is not None else registered_tools_for(
        enable_workspace_tools=workspace_tools_enabled
    )
    return ok(
        server="cad-chat-bridge",
        version=__version__,
        transport=transport,
        local_only=transport == "stdio",
        workspace_tools_enabled=workspace_tools_enabled,
        tools=list(active_tools),
        explicitly_not_registered=list(DANGEROUS_TOOLS_NOT_REGISTERED),
    )


def create_mcp_server(
    *,
    transport_label: str = "stdio",
    active_document_filter: PayloadFilter | None = None,
    diagnostic_filter: PayloadFilter | None = None,
    expose_allow_start_param: bool = True,
    enable_workspace_tools: bool = True,
) -> Any:
    """Create the FastMCP server.

    Importing FastMCP is delayed so unit tests and non-MCP installs can import
    this module without the optional dependency. HTTP callers can disable the
    ``allow_start`` tool parameter so a cloud request can never start AutoCAD.
    HTTP callers can also disable workspace tools to avoid exposing local
    mutating operations through an unauthenticated public tunnel.
    """

    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - exercised manually by setup.
        raise RuntimeError(
            "The 'mcp' extra is required to run the server: "
            "python -m pip install -e '.[mcp]'"
        ) from exc

    mcp = FastMCP("cad-chat-bridge")
    active_tools = registered_tools_for(enable_workspace_tools=enable_workspace_tools)

    @mcp.tool()
    def cad_ping() -> str:
        """Check that the CAD Chat Bridge MCP server is reachable."""

        return dumps(
            ping_payload(
                transport=transport_label,
                tools=active_tools,
                workspace_tools_enabled=enable_workspace_tools,
            )
        )

    @mcp.tool()
    def cad_diagnose_access(timeout_sec: float = 5.0) -> str:
        """Diagnose whether this local process can access a running AutoCAD instance."""

        payload = diagnose_access(timeout_sec=timeout_sec)
        if diagnostic_filter is not None:
            payload = diagnostic_filter(payload)
        return dumps(payload)

    def _active_document_payload(*, allow_start: bool, timeout_sec: float) -> str:
        payload = get_active_document(allow_start=allow_start, timeout_sec=timeout_sec)
        if active_document_filter is not None:
            payload = active_document_filter(payload)
        return dumps(payload)

    if expose_allow_start_param:

        @mcp.tool()
        def cad_get_active_document(
            allow_start: bool = False, timeout_sec: float = 10.0
        ) -> str:
            """Return active AutoCAD document metadata when local COM access is available."""

            return _active_document_payload(allow_start=allow_start, timeout_sec=timeout_sec)

    else:

        @mcp.tool()
        def cad_get_active_document(timeout_sec: float = 10.0) -> str:
            """Return active AutoCAD document metadata without starting AutoCAD."""

            return _active_document_payload(allow_start=False, timeout_sec=timeout_sec)

    @mcp.tool()
    def cad_list_catalog(category: str | None = None) -> str:
        """List safe public catalog entries. This MVP does not run catalog items."""

        return dumps(list_catalog(category=category))

    @mcp.tool()
    def cad_describe_catalog_item(item_id: str) -> str:
        """Describe one safe public catalog entry by id."""

        return dumps(describe_catalog_item(item_id))

    if enable_workspace_tools:

        @mcp.tool()
        def repo_registry_list() -> str:
            """List GitHub repositories allowed for local sync."""

            return dumps(repo_registry_list_payload())

        @mcp.tool()
        def repo_status(repo_id: str) -> str:
            """Return local mirror and task worktree status for one white-listed repo."""

            return dumps(repo_status_payload(repo_id))

        @mcp.tool()
        def repo_sync(
            repo_id: str,
            ref: str,
            expected_remote: str | None = None,
            expected_commit: str | None = None,
        ) -> str:
            """Fetch a white-listed GitHub repo/ref into the local mirror."""

            return dumps(
                repo_sync_payload(
                    repo_id,
                    ref,
                    expected_remote=expected_remote,
                    expected_commit=expected_commit,
                )
            )

        @mcp.tool()
        def repo_create_task_worktree(
            repo_id: str,
            ref: str,
            task_id: str,
            expected_commit: str | None = None,
        ) -> str:
            """Create a read-only task worktree and script workspace."""

            return dumps(
                repo_create_task_worktree_payload(
                    repo_id,
                    ref,
                    task_id,
                    expected_commit=expected_commit,
                )
            )

        @mcp.tool()
        def workspace_status(task_id: str) -> str:
            """Return workspace directory status for a task."""

            return dumps(workspace_status_payload(task_id))

        @mcp.tool()
        def workspace_list_files(
            task_id: str,
            subdir: str = "workspace",
            pattern: str = "*",
            max_results: int = 100,
        ) -> str:
            """List files under a task workspace."""

            return dumps(
                workspace_list_files_payload(
                    task_id,
                    subdir=subdir,
                    pattern=pattern,
                    max_results=max_results,
                )
            )

        @mcp.tool()
        def workspace_read_file(
            task_id: str,
            relative_path: str,
            max_bytes: int = 262144,
        ) -> str:
            """Read a UTF-8 text file from a task workspace."""

            return dumps(workspace_read_file_payload(task_id, relative_path, max_bytes=max_bytes))

        @mcp.tool()
        def workspace_apply_patch(
            task_id: str,
            relative_path: str,
            expected_sha256: str,
            content: str,
        ) -> str:
            """Replace one workspace file when the expected SHA-256 matches."""

            return dumps(
                workspace_apply_patch_payload(
                    task_id,
                    relative_path,
                    expected_sha256=expected_sha256,
                    content=content,
                )
            )

        @mcp.tool()
        def workspace_list_artifacts(task_id: str, max_results: int = 100) -> str:
            """List files under workspace/artifacts."""

            return dumps(workspace_list_artifacts_payload(task_id, max_results=max_results))

        @mcp.tool()
        def workspace_read_log(task_id: str, relative_path: str, max_bytes: int = 262144) -> str:
            """Read a file under workspace/logs."""

            return dumps(workspace_read_log_payload(task_id, relative_path, max_bytes=max_bytes))

    return mcp


def main() -> None:
    """Run the stdio MCP server."""

    create_mcp_server().run()


if __name__ == "__main__":
    main()
