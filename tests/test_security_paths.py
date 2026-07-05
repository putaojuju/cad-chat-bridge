from pathlib import Path

import pytest

from cad_chat_bridge.security.paths import ensure_safe_artifact_path


def test_relative_artifact_path_resolves_under_root(tmp_path: Path):
    result = ensure_safe_artifact_path("probe.json", root=tmp_path)
    assert result == (tmp_path / "probe.json").resolve()


def test_absolute_path_inside_root_allowed(tmp_path: Path):
    result = ensure_safe_artifact_path(tmp_path / "nested" / "probe.json", root=tmp_path)
    assert result == (tmp_path / "nested" / "probe.json").resolve()


def test_parent_traversal_rejected(tmp_path: Path):
    with pytest.raises(ValueError):
        ensure_safe_artifact_path("../escape.json", root=tmp_path)


def test_absolute_path_outside_root_rejected(tmp_path: Path):
    with pytest.raises(ValueError):
        ensure_safe_artifact_path(tmp_path.parent / "escape.json", root=tmp_path)
