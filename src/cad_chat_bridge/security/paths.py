"""Path security helpers for future artifact-producing tools."""

from __future__ import annotations

import tempfile
from pathlib import Path


def default_artifact_root() -> Path:
    """Return the controlled local artifact directory for future generated files."""

    return Path(tempfile.gettempdir()) / "cad-chat-bridge" / "artifacts"


def ensure_safe_artifact_path(path: str | Path, *, root: str | Path | None = None) -> Path:
    """Resolve ``path`` and ensure it stays under the controlled artifact root.

    Relative paths are interpreted relative to the artifact root. Absolute paths
    are accepted only when they already point inside the artifact root.
    """

    artifact_root = Path(root) if root is not None else default_artifact_root()
    artifact_root = artifact_root.expanduser().resolve()

    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = artifact_root / candidate
    candidate = candidate.resolve()

    try:
        candidate.relative_to(artifact_root)
    except ValueError as exc:
        raise ValueError(f"path escapes artifact root: {candidate}") from exc

    if candidate.name in {"", ".", ".."}:
        raise ValueError("artifact path must include a file name")

    return candidate
