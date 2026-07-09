"""Development-only HTTP MCP server fallback.

This module is intended for Apps SDK server URL testing through a local tunnel.
It keeps only the five MVP read/diagnostic tools by default. Repo/workspace
mutating tools require an explicit local environment opt-in.
"""

from __future__ import annotations

import argparse
import os
from typing import Any

from cad_chat_bridge.mcp_server import MVP_TOOLS, REGISTERED_TOOLS, create_mcp_server

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 3333
DEFAULT_MCP_PATH = "/mcp"
ROOT_TEXT = "CAD Chat Bridge MCP server"
FULL_NAME_ENV = "CAD_CHAT_BRIDGE_HTTP_EXPOSE_FULLNAME"
ALLOW_PUBLIC_BIND_ENV = "CAD_CHAT_BRIDGE_HTTP_ALLOW_PUBLIC_BIND"
WORKSPACE_TOOLS_ENV = "CAD_CHAT_BRIDGE_HTTP_ENABLE_WORKSPACE_TOOLS"
HTTP_REGISTERED_TOOLS = MVP_TOOLS
HTTP_CAD_GET_ACTIVE_DOCUMENT_ACCEPTS_ALLOW_START = False
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, GET, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "content-type, mcp-session-id",
    "Access-Control-Expose-Headers": "Mcp-Session-Id",
}
OAUTH_DISCOVERY_PREFIXES = (
    "/.well-known/oauth-authorization-server",
    "/.well-known/oauth-protected-resource",
    "/.well-known/openid-configuration",
)


def env_flag(name: str, *, environ: dict[str, str] | None = None) -> bool:
    """Return whether an environment variable is an enabled boolean flag."""

    source = os.environ if environ is None else environ
    return source.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def http_exposes_full_name(*, environ: dict[str, str] | None = None) -> bool:
    """Return whether HTTP mode may include AutoCAD document FullName."""

    return env_flag(FULL_NAME_ENV, environ=environ)


def http_workspace_tools_enabled(*, environ: dict[str, str] | None = None) -> bool:
    """Return whether HTTP mode may register repo/workspace tools."""

    return env_flag(WORKSPACE_TOOLS_ENV, environ=environ)


def public_bind_allowed(*, environ: dict[str, str] | None = None) -> bool:
    """Return whether HTTP mode may bind to non-loopback wildcard addresses."""

    return env_flag(ALLOW_PUBLIC_BIND_ENV, environ=environ)


def redact_active_document_payload(
    payload: dict[str, Any], *, expose_full_name: bool = False
) -> dict[str, Any]:
    """Redact active-document path details for dev HTTP mode by default."""

    if not payload.get("success"):
        return dict(payload)

    redacted = {
        "success": True,
        "application": payload.get("application", "AutoCAD"),
        "name": payload.get("name", ""),
        "quiescent": payload.get("quiescent"),
    }
    if expose_full_name:
        redacted["full_name"] = payload.get("full_name", "")
    return redacted


def redact_diagnostic_payload(
    payload: dict[str, Any], *, expose_full_name: bool = False
) -> dict[str, Any]:
    """Redact diagnostic path and window-title details for dev HTTP mode."""

    redacted = dict(payload)

    com = redacted.get("com")
    if isinstance(com, dict):
        safe_com = dict(com)
        if not expose_full_name:
            safe_com.pop("full_name", None)
        redacted["com"] = safe_com

    processes = redacted.get("autocad_processes")
    if isinstance(processes, list):
        safe_processes = []
        for process in processes:
            if not isinstance(process, dict):
                safe_processes.append(process)
                continue
            safe_process = dict(process)
            title = safe_process.pop("window_title", None)
            if title is not None:
                safe_process["has_window_title"] = bool(title)
            safe_processes.append(safe_process)
        redacted["autocad_processes"] = safe_processes

    return redacted


def validate_host(host: str, *, environ: dict[str, str] | None = None) -> str:
    """Validate the bind host for the dev HTTP fallback."""

    normalized = host.strip() or DEFAULT_HOST
    if normalized in {"0.0.0.0", "::"} and not public_bind_allowed(environ=environ):
        raise ValueError(
            f"Refusing to bind to {normalized!r} by default. "
            f"Use {ALLOW_PUBLIC_BIND_ENV}=1 only for an explicit local dev tunnel test."
        )
    return normalized


def create_http_mcp_server(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    mcp_path: str = DEFAULT_MCP_PATH,
    expose_full_name: bool | None = None,
    enable_workspace_tools: bool | None = None,
) -> Any:
    """Create a FastMCP server configured for streamable HTTP on /mcp."""

    resolved_host = validate_host(host)
    resolved_path = mcp_path if mcp_path.startswith("/") else f"/{mcp_path}"
    should_expose_full_name = http_exposes_full_name() if expose_full_name is None else expose_full_name
    should_enable_workspace_tools = (
        http_workspace_tools_enabled() if enable_workspace_tools is None else enable_workspace_tools
    )

    mcp = create_mcp_server(
        transport_label="http",
        active_document_filter=lambda payload: redact_active_document_payload(
            payload, expose_full_name=should_expose_full_name
        ),
        diagnostic_filter=lambda payload: redact_diagnostic_payload(
            payload, expose_full_name=should_expose_full_name
        ),
        expose_allow_start_param=HTTP_CAD_GET_ACTIVE_DOCUMENT_ACCEPTS_ALLOW_START,
        enable_workspace_tools=should_enable_workspace_tools,
    )
    configure_http_settings(mcp, host=resolved_host, port=port, mcp_path=resolved_path)
    return mcp


def configure_http_settings(mcp: Any, *, host: str, port: int, mcp_path: str) -> None:
    """Apply FastMCP streamable HTTP settings without importing FastMCP at module import."""

    settings = getattr(mcp, "settings", None)
    if settings is None:
        return

    for name, value in {
        "host": host,
        "port": int(port),
        "streamable_http_path": mcp_path,
    }.items():
        try:
            setattr(settings, name, value)
        except Exception:  # noqa: BLE001 - FastMCP settings implementations may vary.
            pass


def create_apps_sdk_http_app(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    mcp_path: str = DEFAULT_MCP_PATH,
    expose_full_name: bool | None = None,
    enable_workspace_tools: bool | None = None,
) -> Any:
    """Create an Apps SDK friendly ASGI app around the FastMCP streamable app."""

    from starlette.applications import Starlette
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import PlainTextResponse, Response
    from starlette.routing import Mount, Route

    mcp = create_http_mcp_server(
        host=host,
        port=port,
        mcp_path=mcp_path,
        expose_full_name=expose_full_name,
        enable_workspace_tools=enable_workspace_tools,
    )
    if not hasattr(mcp, "streamable_http_app"):
        raise RuntimeError(
            "The installed mcp package does not expose streamable_http_app(). "
            "Upgrade the 'mcp' dependency before using the dev HTTP fallback."
        )

    streamable_app = mcp.streamable_http_app()
    resolved_path = mcp_path if mcp_path.startswith("/") else f"/{mcp_path}"

    async def health(_request: Request) -> Response:
        return PlainTextResponse(ROOT_TEXT, status_code=200)

    async def cors_preflight(_request: Request) -> Response:
        return Response(status_code=204, headers=CORS_HEADERS)

    async def not_found(_request: Request) -> Response:
        return PlainTextResponse("Not Found", status_code=404)

    class McpCorsMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):  # noqa: ANN001
            response = await call_next(request)
            if request.url.path == resolved_path or request.url.path.startswith(resolved_path + "/"):
                response.headers.setdefault("Access-Control-Allow-Origin", "*")
                response.headers.setdefault("Access-Control-Expose-Headers", "Mcp-Session-Id")
            return response

    routes = [
        Route("/", health, methods=["GET"]),
        Route(resolved_path, cors_preflight, methods=["OPTIONS"]),
        Route(f"{resolved_path}/{{path:path}}", cors_preflight, methods=["OPTIONS"]),
    ]
    for prefix in OAUTH_DISCOVERY_PREFIXES:
        routes.append(Route(prefix, not_found, methods=["GET", "POST", "OPTIONS"]))
        routes.append(Route(f"{prefix}/{{path:path}}", not_found, methods=["GET", "POST", "OPTIONS"]))
    routes.append(Mount("/", streamable_app))

    return Starlette(routes=routes, middleware=[McpCorsMiddleware])


def run_http_mcp_server(
    *, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, mcp_path: str = DEFAULT_MCP_PATH
) -> None:
    """Run the development HTTP MCP server."""

    import uvicorn

    resolved_host = validate_host(host)
    app = create_apps_sdk_http_app(host=resolved_host, port=port, mcp_path=mcp_path)
    uvicorn.run(app, host=resolved_host, port=int(port))


def build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI parser for the dev HTTP fallback."""

    parser = argparse.ArgumentParser(description="Run CAD Chat Bridge dev HTTP MCP server.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Bind host, default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Bind port, default: 3333")
    parser.add_argument("--path", default=DEFAULT_MCP_PATH, help="MCP endpoint path, default: /mcp")
    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""

    args = build_arg_parser().parse_args(argv)
    run_http_mcp_server(host=args.host, port=args.port, mcp_path=args.path)


if __name__ == "__main__":
    main()
