"""Schema helpers for the public safe catalog manifest."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ALLOWED_EFFECTS = {"read_only", "view_only", "draw_modify", "file_write"}


@dataclass(frozen=True)
class CatalogValidationResult:
    """Result of validating a catalog manifest."""

    ok: bool
    errors: tuple[str, ...]


def validate_catalog(catalog: dict[str, Any]) -> CatalogValidationResult:
    """Validate the minimal public catalog manifest shape."""

    errors: list[str] = []
    if not isinstance(catalog, dict):
        return CatalogValidationResult(False, ("catalog must be an object",))

    if not isinstance(catalog.get("version"), int):
        errors.append("version must be an integer")

    items = catalog.get("items")
    if not isinstance(items, list):
        errors.append("items must be a list")
        items = []

    seen_ids: set[str] = set()
    for index, item in enumerate(items):
        prefix = f"items[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue

        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            errors.append(f"{prefix}.id must be a non-empty string")
        elif item_id in seen_ids:
            errors.append(f"{prefix}.id is duplicated: {item_id}")
        else:
            seen_ids.add(item_id)

        for field in ("title", "description", "category"):
            if not isinstance(item.get(field), str) or not item.get(field):
                errors.append(f"{prefix}.{field} must be a non-empty string")

        effect = item.get("effect")
        if effect not in ALLOWED_EFFECTS:
            errors.append(f"{prefix}.effect must be one of {sorted(ALLOWED_EFFECTS)}")

        for field in ("enabled", "runnable"):
            if not isinstance(item.get(field), bool):
                errors.append(f"{prefix}.{field} must be a boolean")

        safety = item.get("safety")
        if not isinstance(safety, dict):
            errors.append(f"{prefix}.safety must be an object")
        else:
            for field in ("modifies_drawing", "writes_files", "loads_lisp", "requires_quiescent"):
                if not isinstance(safety.get(field), bool):
                    errors.append(f"{prefix}.safety.{field} must be a boolean")

        parameters = item.get("parameters")
        if not isinstance(parameters, dict):
            errors.append(f"{prefix}.parameters must be an object")

    return CatalogValidationResult(not errors, tuple(errors))
