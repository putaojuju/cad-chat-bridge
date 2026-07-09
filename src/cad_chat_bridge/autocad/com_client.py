"""Minimal AutoCAD COM client helpers.

This module intentionally contains no arbitrary command or AutoLISP execution
entry points. The MVP only reads active-document metadata and exposes reusable
connection diagnostics.
"""

from __future__ import annotations

import platform
import queue
import threading
from collections.abc import Callable
from typing import Any

DEFAULT_COM_TIMEOUT_SEC = 10.0


class AutoCadUnavailableError(RuntimeError):
    """Raised when AutoCAD is not reachable through local COM."""


class AutoCadBusyError(RuntimeError):
    """Raised when AutoCAD reports that it is not quiescent."""


def is_windows() -> bool:
    """Return whether the current platform can support AutoCAD COM."""

    return platform.system() == "Windows"


def autocad_progids() -> list[str]:
    """Return common AutoCAD COM ProgIDs plus registered variants when available."""

    progids = [
        "AutoCAD.Application",
        "AutoCAD.Application.25",
        "AutoCAD.Application.24.3",
        "AutoCAD.Application.24.2",
        "AutoCAD.Application.24.1",
        "AutoCAD.Application.24",
        "AutoCAD.Application.23.1",
        "AutoCAD.Application.23",
        "AutoCAD.Application.22",
        "AutoCAD.Application.21",
        "AutoCAD.Application.20",
    ]

    if not is_windows():
        return progids

    try:
        import winreg
    except ImportError:
        return progids

    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "") as root:
            index = 0
            while True:
                try:
                    name = winreg.EnumKey(root, index)
                except OSError:
                    break
                if name.startswith("AutoCAD.Application") and name not in progids:
                    progids.append(name)
                index += 1
    except OSError:
        pass

    return progids


def has_pywin32() -> bool:
    """Return whether pywin32 imports are available."""

    try:
        import pythoncom  # noqa: F401
        import win32com.client  # noqa: F401
    except ImportError:
        return False
    return True


def _get_autocad(*, allow_start: bool = False) -> Any:
    """Get a running AutoCAD COM application.

    By default this only attaches to an existing AutoCAD instance. Starting
    AutoCAD must be an explicit opt-in by the caller.
    """

    if not is_windows():
        raise AutoCadUnavailableError("AutoCAD COM is only supported on Windows.")

    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise AutoCadUnavailableError("pywin32 is required for AutoCAD COM access.") from exc

    pythoncom.CoInitialize()
    last_error: Exception | None = None

    for progid in autocad_progids():
        try:
            return win32com.client.GetActiveObject(progid)
        except Exception as exc:  # noqa: BLE001 - COM errors vary by AutoCAD version.
            last_error = exc

    if allow_start:
        for progid in autocad_progids():
            try:
                return win32com.client.Dispatch(progid)
            except Exception as exc:  # noqa: BLE001
                last_error = exc

    raise AutoCadUnavailableError(f"AutoCAD is not available via COM. Last error: {last_error}")


def _run_with_timeout(func: Callable[[], Any], timeout_sec: float) -> tuple[str, Any]:
    """Run a COM operation on a worker thread and bound how long stdio can wait."""

    result_q: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=1)

    def worker() -> None:
        try:
            import pythoncom

            pythoncom.CoInitialize()
        except Exception:  # noqa: BLE001 - let the operation report the real error.
            pass
        try:
            result_q.put(("ok", func()))
        except Exception as exc:  # noqa: BLE001 - surface errors as structured payloads.
            result_q.put(("error", exc))
        finally:
            try:
                import pythoncom

                pythoncom.CoUninitialize()
            except Exception:  # noqa: BLE001
                pass

    thread = threading.Thread(target=worker, name="cad-chat-bridge-com", daemon=True)
    thread.start()

    try:
        return result_q.get(timeout=max(0.1, float(timeout_sec)))
    except queue.Empty:
        return ("timeout", None)


def acad_is_quiescent(acad: Any) -> bool | None:
    """Return AutoCAD's quiescent state, or None if the API is unavailable."""

    try:
        return bool(acad.GetAcadState().IsQuiescent)
    except Exception:  # noqa: BLE001
        return None


def with_autocad(
    operation: Callable[[Any], Any],
    *,
    allow_start: bool = False,
    require_quiescent: bool = False,
    timeout_sec: float = DEFAULT_COM_TIMEOUT_SEC,
) -> Any:
    """Run an AutoCAD operation with timeout and optional quiescent guard."""

    def task() -> Any:
        acad = _get_autocad(allow_start=allow_start)
        if require_quiescent and acad_is_quiescent(acad) is False:
            raise AutoCadBusyError(
                "AutoCAD is busy or in the middle of a command. Press Esc, close dialogs, and retry."
            )
        return operation(acad)

    kind, value = _run_with_timeout(task, timeout_sec)
    if kind == "timeout":
        raise TimeoutError(
            f"AutoCAD COM call did not return within {timeout_sec:.1f}s. "
            "AutoCAD may be waiting at a prompt or showing a modal dialog."
        )
    if kind == "error":
        raise value
    return value


def get_active_document(
    *, allow_start: bool = False, timeout_sec: float = DEFAULT_COM_TIMEOUT_SEC
) -> dict[str, Any]:
    """Return active-document metadata as a structured response."""

    if not is_windows():
        return {
            "success": False,
            "error": "AutoCAD COM is only supported on Windows.",
            "error_type": "UnsupportedPlatform",
            "platform": platform.platform(),
        }

    if not has_pywin32():
        return {
            "success": False,
            "error": "pywin32 is required for AutoCAD COM access.",
            "error_type": "MissingDependency",
        }

    def op(acad: Any) -> dict[str, Any]:
        doc = acad.ActiveDocument
        return {
            "success": True,
            "application": getattr(acad, "Name", "AutoCAD"),
            "name": getattr(doc, "Name", ""),
            "full_name": getattr(doc, "FullName", ""),
            "quiescent": acad_is_quiescent(acad),
        }

    try:
        return with_autocad(op, allow_start=allow_start, timeout_sec=timeout_sec)
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc), "error_type": type(exc).__name__}
