import pytest

from cad_chat_bridge.http_mcp_server import (
    ALLOW_PUBLIC_BIND_ENV,
    DEFAULT_HOST,
    DEFAULT_MCP_PATH,
    DEFAULT_PORT,
    FULL_NAME_ENV,
    HTTP_REGISTERED_TOOLS,
    http_exposes_full_name,
    redact_active_document_payload,
    validate_host,
)
from cad_chat_bridge.mcp_server import DANGEROUS_TOOLS_NOT_REGISTERED, REGISTERED_TOOLS


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
        "full_name_redacted": True,
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
    assert exposed["full_name_redacted"] is False


def test_http_full_name_env_flag_is_off_by_default():
    assert http_exposes_full_name(environ={}) is False
    assert http_exposes_full_name(environ={FULL_NAME_ENV: "1"}) is True
