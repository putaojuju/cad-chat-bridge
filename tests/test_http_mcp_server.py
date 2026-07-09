import asyncio
import inspect
import json
import sys
import types

import pytest

import cad_chat_bridge.mcp_server as mcp_server_module
from cad_chat_bridge.http_mcp_server import (
    ALLOW_PUBLIC_BIND_ENV,
    CORS_HEADERS,
    DEFAULT_HOST,
    DEFAULT_MCP_PATH,
    DEFAULT_PORT,
    FULL_NAME_ENV,
    HTTP_CAD_GET_ACTIVE_DOCUMENT_ACCEPTS_ALLOW_START,
    HTTP_REGISTERED_TOOLS,
    ROOT_TEXT,
    create_apps_sdk_http_app,
    create_http_mcp_server,
    http_exposes_full_name,
    redact_active_document_payload,
    redact_diagnostic_payload,
    validate_host,
)
from cad_chat_bridge.mcp_server import DANGEROUS_TOOLS_NOT_REGISTERED, REGISTERED_TOOLS


def _install_fake_fastmcp(monkeypatch: pytest.MonkeyPatch):
    class FakeFastMCP:
        last_instance = None

        def __init__(self, name: str):
            self.name = name
            self.tools = {}
            self.settings = types.SimpleNamespace()
            FakeFastMCP.last_instance = self

        def tool(self):
            def decorator(func):
                self.tools[func.__name__] = func
                return func

            return decorator

        def run(self, *args, **kwargs):
            return None

        def streamable_http_app(self):
            async def app(scope, receive, send):  # noqa: ANN001
                if scope["type"] != "http":
                    return
                headers = [(b"content-type", b"text/plain")]
                await send({"type": "http.response.start", "status": 418, "headers": headers})
                await send({"type": "http.response.body", "body": b"fake mcp endpoint"})

            return app

    mcp_mod = types.ModuleType("mcp")
    server_mod = types.ModuleType("mcp.server")
    fastmcp_mod = types.ModuleType("mcp.server.fastmcp")
    fastmcp_mod.FastMCP = FakeFastMCP
    server_mod.fastmcp = fastmcp_mod
    mcp_mod.server = server_mod

    monkeypatch.setitem(sys.modules, "mcp", mcp_mod)
    monkeypatch.setitem(sys.modules, "mcp.server", server_mod)
    monkeypatch.setitem(sys.modules, "mcp.server.fastmcp", fastmcp_mod)
    return FakeFastMCP


async def _asgi_request(app, method: str, path: str):  # noqa: ANN001
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):  # noqa: ANN001
        messages.append(message)

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [(b"host", b"testserver")],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        },
        receive,
        send,
    )
    start = next(message for message in messages if message["type"] == "http.response.start")
    body = b"".join(
        message.get("body", b"") for message in messages if message["type"] == "http.response.body"
    )
    headers = {key.decode().lower(): value.decode() for key, value in start.get("headers", [])}
    return start["status"], headers, body


def _request(app, method: str, path: str):  # noqa: ANN001
    return asyncio.run(_asgi_request(app, method, path))


def test_http_server_module_imports_with_expected_defaults():
    assert DEFAULT_HOST == "127.0.0.1"
    assert DEFAULT_PORT == 3333
    assert DEFAULT_MCP_PATH == "/mcp"


def test_http_server_uses_only_five_mvp_tools():
    assert HTTP_REGISTERED_TOOLS == REGISTERED_TOOLS
    assert set(HTTP_REGISTERED_TOOLS) == {
        "cad_ping",
        "cad_diagnose_access",
        "cad_get_active_document",
        "cad_list_catalog",
        "cad_describe_catalog_item",
    }


def test_http_server_does_not_register_dangerous_tools():
    for tool in DANGEROUS_TOOLS_NOT_REGISTERED:
        assert tool not in HTTP_REGISTERED_TOOLS


def test_validate_host_rejects_public_wildcard_by_default():
    with pytest.raises(ValueError):
        validate_host("0.0.0.0", environ={})

    assert validate_host("0.0.0.0", environ={ALLOW_PUBLIC_BIND_ENV: "1"}) == "0.0.0.0"


def test_active_document_default_redacts_full_name():
    payload = {
        "success": True,
        "application": "AutoCAD",
        "name": "demo.dwg",
        "full_name": r"C:\private\client\demo.dwg",
        "quiescent": True,
    }

    redacted = redact_active_document_payload(payload)

    assert redacted == {
        "success": True,
        "application": "AutoCAD",
        "name": "demo.dwg",
        "quiescent": True,
    }
    assert "full_name" not in redacted


def test_active_document_can_expose_full_name_when_explicitly_enabled():
    payload = {
        "success": True,
        "application": "AutoCAD",
        "name": "demo.dwg",
        "full_name": r"C:\private\client\demo.dwg",
        "quiescent": False,
    }

    exposed = redact_active_document_payload(payload, expose_full_name=True)

    assert exposed["full_name"] == payload["full_name"]


def test_http_full_name_env_flag_is_off_by_default():
    assert http_exposes_full_name(environ={}) is False
    assert http_exposes_full_name(environ={FULL_NAME_ENV: "1"}) is True


def test_diagnostic_default_redacts_full_name_and_window_title():
    payload = {
        "success": True,
        "com": {
            "success": True,
            "name": "demo.dwg",
            "full_name": r"C:\private\client\demo.dwg",
        },
        "autocad_processes": [
            {"pid": 123, "name": "acad.exe", "window_title": "Client Project - demo.dwg"},
            {"pid": 456, "name": "acad.exe", "window_title": ""},
        ],
    }

    redacted = redact_diagnostic_payload(payload)

    assert "full_name" not in redacted["com"]
    assert redacted["autocad_processes"][0]["has_window_title"] is True
    assert redacted["autocad_processes"][1]["has_window_title"] is False
    assert "window_title" not in redacted["autocad_processes"][0]
    assert "window_title" not in redacted["autocad_processes"][1]


def test_diagnostic_can_expose_com_full_name_only_when_explicitly_enabled():
    payload = {
        "success": True,
        "com": {
            "success": True,
            "name": "demo.dwg",
            "full_name": r"C:\private\client\demo.dwg",
        },
        "autocad_processes": [
            {"pid": 123, "name": "acad.exe", "window_title": "Client Project - demo.dwg"},
        ],
    }

    redacted = redact_diagnostic_payload(payload, expose_full_name=True)

    assert redacted["com"]["full_name"] == payload["com"]["full_name"]
    assert "window_title" not in redacted["autocad_processes"][0]
    assert redacted["autocad_processes"][0]["has_window_title"] is True


def test_http_get_active_document_schema_omits_allow_start_and_forces_false(monkeypatch):
    _install_fake_fastmcp(monkeypatch)
    calls = []

    def fake_get_active_document(*, allow_start: bool, timeout_sec: float):
        calls.append({"allow_start": allow_start, "timeout_sec": timeout_sec})
        return {
            "success": True,
            "application": "AutoCAD",
            "name": "demo.dwg",
            "full_name": r"C:\private\client\demo.dwg",
            "quiescent": True,
        }

    monkeypatch.setattr(mcp_server_module, "get_active_document", fake_get_active_document)

    server = create_http_mcp_server(expose_full_name=False)
    tool = server.tools["cad_get_active_document"]

    assert HTTP_CAD_GET_ACTIVE_DOCUMENT_ACCEPTS_ALLOW_START is False
    assert "allow_start" not in inspect.signature(tool).parameters

    response = json.loads(tool(timeout_sec=2.5))

    assert calls == [{"allow_start": False, "timeout_sec": 2.5}]
    assert response == {
        "success": True,
        "application": "AutoCAD",
        "name": "demo.dwg",
        "quiescent": True,
    }


def test_http_diagnose_access_tool_redacts_diagnostics_by_default(monkeypatch):
    _install_fake_fastmcp(monkeypatch)

    def fake_diagnose_access(*, timeout_sec: float):
        return {
            "success": True,
            "com": {
                "success": True,
                "name": "demo.dwg",
                "full_name": r"C:\private\client\demo.dwg",
            },
            "autocad_processes": [
                {"pid": 123, "name": "acad.exe", "window_title": "Client Project - demo.dwg"},
            ],
        }

    monkeypatch.setattr(mcp_server_module, "diagnose_access", fake_diagnose_access)

    server = create_http_mcp_server(expose_full_name=False)
    response = json.loads(server.tools["cad_diagnose_access"]())

    assert "full_name" not in response["com"]
    assert "window_title" not in response["autocad_processes"][0]
    assert response["autocad_processes"][0]["has_window_title"] is True


def test_apps_sdk_http_get_root_returns_text(monkeypatch):
    _install_fake_fastmcp(monkeypatch)
    app = create_apps_sdk_http_app()

    status, headers, body = _request(app, "GET", "/")

    assert status == 200
    assert headers["content-type"].startswith("text/plain")
    assert body.decode() == ROOT_TEXT


def test_apps_sdk_http_options_mcp_returns_cors(monkeypatch):
    _install_fake_fastmcp(monkeypatch)
    app = create_apps_sdk_http_app()

    status, headers, body = _request(app, "OPTIONS", "/mcp")

    assert status == 204
    assert body == b""
    for key, value in CORS_HEADERS.items():
        assert headers[key.lower()] == value


def test_apps_sdk_http_options_mcp_actions_returns_cors(monkeypatch):
    _install_fake_fastmcp(monkeypatch)
    app = create_apps_sdk_http_app()

    status, headers, body = _request(app, "OPTIONS", "/mcp/actions")

    assert status == 204
    assert body == b""
    for key, value in CORS_HEADERS.items():
        assert headers[key.lower()] == value


def test_apps_sdk_http_oauth_discovery_returns_404(monkeypatch):
    _install_fake_fastmcp(monkeypatch)
    app = create_apps_sdk_http_app()

    for path in (
        "/.well-known/oauth-authorization-server",
        "/.well-known/oauth-protected-resource",
        "/.well-known/openid-configuration",
    ):
        status, _headers, body = _request(app, "GET", path)
        assert status == 404
        assert body == b"Not Found"


def test_apps_sdk_http_mcp_path_still_reaches_mcp_endpoint(monkeypatch):
    _install_fake_fastmcp(monkeypatch)
    app = create_apps_sdk_http_app()

    status, headers, body = _request(app, "POST", "/mcp")

    assert status == 418
    assert body == b"fake mcp endpoint"
    assert headers["access-control-allow-origin"] == "*"
    assert headers["access-control-expose-headers"] == "Mcp-Session-Id"
