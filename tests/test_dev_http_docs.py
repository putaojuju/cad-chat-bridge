from pathlib import Path


def test_dev_http_connector_doc_mentions_mcp_not_sse():
    text = Path("docs/DEV_HTTP_CONNECTOR_SETUP.md").read_text(encoding="utf-8")
    assert "/mcp" in text
    assert "/sse" not in text.lower()


def test_dev_http_connector_doc_limits_tool_scope():
    text = Path("docs/DEV_HTTP_CONNECTOR_SETUP.md").read_text(encoding="utf-8")
    for tool in (
        "cad_ping",
        "cad_diagnose_access",
        "cad_get_active_document",
        "cad_list_catalog",
        "cad_describe_catalog_item",
    ):
        assert tool in text
