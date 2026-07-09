"""Safe catalog loading and read-only discovery helpers."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

from cad_chat_bridge.catalog.schema import validate_catalog


def default_catalog_path() -> Path:
    """Return the installed default public catalog path."""

    with resources.as_file(resources.files("cad_chat_bridge.catalog") / "default_catalog.json") as path:
        return Path(path)


def load_catalog(path: str | Path | None = None) -> dict[str, Any]:
    """Load and validate a catalog manifest."""

    catalog_path = Path(path) if path is not None else default_catalog_path()
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": f"failed to read catalog: {exc}", "items": []}

    validation = validate_catalog(catalog)
    if not validation.ok:
        return {
            "success": False,
            "error": "catalog validation failed",
            "validation_errors": list(validation.errors),
            "items": [],
        }

    return {"success": True, "path": str(catalog_path), **catalog}


def list_catalog(*, category: str | None = None, path: str | Path | None = None) -> dict[str, Any]:
    """Return a compact, read-only catalog listing."""

    catalog = load_catalog(path)
    items = []
    for item in catalog.get("items", []):
        if category and item.get("category") != category:
            continue
        items.append(
            {
                "id": item["id"],
                "title": item["title"],
                "category": item["category"],
                "description": item["description"],
                "effect": item["effect"],
                "enabled": item["enabled"],
                "runnable": item["runnable"],
            }
        )

    return {
        "success": bool(catalog.get("success")),
        "version": catalog.get("version"),
        "path": catalog.get("path"),
        "count": len(items),
        "items": items,
        "error": catalog.get("error"),
        "validation_errors": catalog.get("validation_errors"),
    }


def describe_catalog_item(item_id: str, *, path: str | Path | None = None) -> dict[str, Any]:
    """Return the full manifest entry for one catalog item."""

    catalog = load_catalog(path)
    if not catalog.get("success"):
        return {
            "success": False,
            "error": catalog.get("error", "catalog failed to load"),
            "validation_errors": catalog.get("validation_errors"),
        }

    for item in catalog.get("items", []):
        if item.get("id") == item_id:
            return {"success": True, "item": item}

    return {
        "success": False,
        "error": f"unknown catalog item id: {item_id}",
        "known_ids": [item.get("id") for item in catalog.get("items", [])],
    }
