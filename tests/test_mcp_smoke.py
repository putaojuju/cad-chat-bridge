import json

from cad_chat_bridge.jsonutil import dumps
from cad_chat_bridge.mcp_server import REGISTERED_TOOLS, ping_payload


def test_ping_payload_documents_registered_mvp_tools():
    payload = ping_payload()
    assert payload["success"] is True
    assert payload["local_only"] is True
    assert tuple(payload["tools"]) == REGISTERED_TOOLS
    assert set(payload["tools"]) == {
        "cad_ping",
        "cad_diagnose_access",
        "cad_get_active_document",
        "cad_list_catalog",
        "cad_describe_catalog_item",
    }


def test_dumps_returns_json_string():
    text = dumps(ping_payload())
    decoded = json.loads(text)
    assert decoded["server"] == "cad-chat-bridge"
