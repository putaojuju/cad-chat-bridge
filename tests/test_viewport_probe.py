from pathlib import Path

import pytest

from cad_chat_bridge.autocad.viewport_probe import ViewWindow, build_viewport_probe


def test_selection_probe_contains_implied_selection():
    result = build_viewport_probe(mode="selection", layer_filter="0", entity_types=["LINE"])
    assert result["success"] is True
    assert '(ssget "_I"' in result["lisp"]
    assert '(8 . "0")' in result["lisp"]
    assert '(0 . "LINE")' in result["lisp"]


def test_current_view_probe_contains_view_window_helper():
    result = build_viewport_probe(mode="current_view")
    assert "ccb:current-view-window" in result["lisp"]
    assert result["request"]["mode"] == "current_view"


def test_window_probe_requires_window():
    with pytest.raises(ValueError):
        build_viewport_probe(mode="window")


def test_window_probe_contains_coordinates():
    window = ViewWindow.from_points((10, 20), (1, 2))
    result = build_viewport_probe(mode="window", window=window)
    assert "'(1.0 2.0 0.0)" in result["lisp"]
    assert "'(10.0 20.0 0.0)" in result["lisp"]


def test_output_path_must_be_inside_artifact_root(tmp_path: Path):
    result = build_viewport_probe(
        mode="selection",
        output_path="probe.json",
        artifact_root=tmp_path,
    )
    assert str(tmp_path.resolve()) in result["request"]["output_path"]

    with pytest.raises(ValueError):
        build_viewport_probe(
            mode="selection",
            output_path="../probe.json",
            artifact_root=tmp_path,
        )
