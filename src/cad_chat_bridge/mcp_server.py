"""MCP server entry point for CAD Chat Bridge."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cad_chat_bridge import __version__
from cad_chat_bridge.autocad.com_client import get_active_document
from cad_chat_bridge.autocad.diagnostics import diagnose_access
from cad_chat_bridge.catalog.loader import describe_catalog_item, list_catalog
from cad_chat_bridge.jsonutil import dumps, ok


REGISTERED_TOOLS = (
    "cad_ping",
    "cad_diagnose_access",
    "cad_get_active_document",
    "cad_list_catalog",
    "cad_describe_catalog_item",
)

DANGEROUS_TOOLS_NOT_REGISTERED = (
    "cad_run_lisp",
    "cad_send_command",
    "cad_load_lisp",
    "cad_save_as",
    "cad_write_file",
)

PayloadFilter = Callable[[dict[str, Any]], dict[str, Any]]


def ping_payload(*, transport: str = "stdio") -> dict[str, Any]:
    """Return the static server capability payload used by cad_ping."""

    return ok(
        server="cad-chat-bridge",
        version=__version__,
        transport=transport,
        local_only=transport == "stdio",
        tools=list(REGISTERED_TOOLS),
        explicitly_not_registered=list(DANGEROUS_TOOLS_NOT_REGISTERED),
    )


def create_mcp_server(
    *,
    transport_label: str = "stdio",
    active_document_filter: PayloadFilter | None = None,
    diagnostic_filter: PayloadFilter | None = None,
    expose_allow_start_param: bool = True,
) -> Any:
    """Create the FastMCP server.

    Importing FastMCP is delayed so unit tests and non-MCP installs can import
    this module without the optional dependency. HTTP callers can disable the
    ``allow_start`` tool parameter so a cloud request can never start AutoCAD.
    """

    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - exercised manually by setup.
        raise RuntimeError(
            "The 'mcp' extra is required to run the server: "
            "python -m pip install -e '.[mcp]'"
        ) from exc

    mcp = FastMCP("cad-chat-bridge")

    @mcp.tool()
    def cad_ping() -> str:
        """Check that the CAD Chat Bridge MCP server is reachable."""

        return dumps(ping_payload(transport=transport_label))

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

    return mcp


def main() -> None:
    """Run the stdio MCP server."""

    create_mcp_server().run()


if __name__ == "__main__":
    main()
