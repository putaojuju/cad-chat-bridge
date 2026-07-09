from cad_chat_bridge.catalog.loader import describe_catalog_item, list_catalog, load_catalog
from cad_chat_bridge.catalog.schema import validate_catalog


def test_default_catalog_validates():
    catalog = load_catalog()
    assert catalog["success"] is True
    result = validate_catalog({"version": catalog["version"], "items": catalog["items"]})
    assert result.ok, result.errors


def test_catalog_listing_is_compact():
    listing = list_catalog()
    assert listing["success"] is True
    assert listing["count"] >= 1
    first = listing["items"][0]
    assert "id" in first
    assert "safety" not in first


def test_describe_catalog_item_by_id():
    listing = list_catalog()
    item_id = listing["items"][0]["id"]
    described = describe_catalog_item(item_id)
    assert described["success"] is True
    assert described["item"]["id"] == item_id
    assert described["item"]["safety"]["writes_files"] is False


def test_unknown_catalog_item_returns_known_ids():
    described = describe_catalog_item("missing.item")
    assert described["success"] is False
    assert "known_ids" in described
