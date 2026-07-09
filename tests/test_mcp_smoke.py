import json

from cad_chat_bridge.jsonutil import dumps
from cad_chat_bridge.mcp_server import DANGEROUS_TOOLS_NOT_REGISTERED, REGISTERED_TOOLS, ping_payload


PR_2A_TOOLS = {
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
}


def test_ping_payload_documents_registered_mvp_and_repo_workspace_tools():
    payload = ping_payload()
    assert payload["success"] is True
    assert payload["local_only"] is True
    assert tuple(payload["tools"]) == REGISTERED_TOOLS
    assert {
        "cad_ping",
        "cad_diagnose_access",
        "cad_get_active_document",
        "cad_list_catalog",
        "cad_describe_catalog_item",
    }.issubset(set(payload["tools"]))
    assert PR_2A_TOOLS.issubset(set(payload["tools"]))


def test_ping_payload_documents_dangerous_tools_not_registered():
    payload = ping_payload()
    for tool in DANGEROUS_TOOLS_NOT_REGISTERED:
        assert tool not in payload["tools"]
        assert tool in payload["explicitly_not_registered"]


def test_dumps_returns_json_string():
    text = dumps(ping_payload())
    decoded = json.loads(text)
    assert decoded["server"] == "cad-chat-bridge"
