"""Local AutoCAD access diagnostics for the MCP bridge."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import platform
from typing import Any

from cad_chat_bridge.autocad import com_client


def _process_integrity(pid: int | None = None) -> dict[str, Any]:
    """Best-effort Windows integrity-level lookup."""

    if not com_client.is_windows():
        return {"supported": False, "reason": "Windows integrity levels are Windows-only."}

    token_query = 0x0008
    process_query_limited_information = 0x1000
    token_integrity_level = 25

    wintypes = ctypes.wintypes
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class SidAndAttributes(ctypes.Structure):
        _fields_ = [("Sid", wintypes.LPVOID), ("Attributes", wintypes.DWORD)]

    class TokenMandatoryLabel(ctypes.Structure):
        _fields_ = [("Label", SidAndAttributes)]

    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetSidSubAuthorityCount.argtypes = [wintypes.LPVOID]
    advapi32.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
    advapi32.GetSidSubAuthority.argtypes = [wintypes.LPVOID, wintypes.DWORD]
    advapi32.GetSidSubAuthority.restype = ctypes.POINTER(wintypes.DWORD)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    def level_name(rid: int) -> str:
        if rid >= 0x4000:
            return "System"
        if rid >= 0x3000:
            return "High"
        if rid >= 0x2000:
            return "Medium"
        if rid >= 0x1000:
            return "Low"
        return f"Unknown({rid})"

    process_handle = kernel32.GetCurrentProcess()
    close_process = False
    if pid is not None:
        process_handle = kernel32.OpenProcess(process_query_limited_information, False, int(pid))
        close_process = True
        if not process_handle:
            return {"error": f"OpenProcess failed: {ctypes.get_last_error()}"}

    token = wintypes.HANDLE()
    try:
        if not advapi32.OpenProcessToken(process_handle, token_query, ctypes.byref(token)):
            return {"error": f"OpenProcessToken failed: {ctypes.get_last_error()}"}

        needed = wintypes.DWORD(0)
        advapi32.GetTokenInformation(token, token_integrity_level, None, 0, ctypes.byref(needed))
        buffer = ctypes.create_string_buffer(needed.value)
        if not advapi32.GetTokenInformation(
            token, token_integrity_level, buffer, needed, ctypes.byref(needed)
        ):
            return {"error": f"GetTokenInformation failed: {ctypes.get_last_error()}"}

        label = ctypes.cast(buffer, ctypes.POINTER(TokenMandatoryLabel)).contents
        count = advapi32.GetSidSubAuthorityCount(label.Label.Sid).contents.value
        rid = advapi32.GetSidSubAuthority(label.Label.Sid, count - 1).contents.value
        return {"rid": hex(rid), "level": level_name(rid)}
    finally:
        if token:
            kernel32.CloseHandle(token)
        if close_process and process_handle:
            kernel32.CloseHandle(process_handle)


def _window_titles_by_pid() -> dict[int, str]:
    """Best-effort map of process id to visible top-level window title."""

    if not com_client.is_windows():
        return {}

    try:
        wintypes = ctypes.wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        titles: dict[int, str] = {}

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.IsWindowVisible.argtypes = [wintypes.HWND]

        def callback(hwnd: int, _lparam: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            text = buffer.value
            if text and (pid.value not in titles or len(text) > len(titles[pid.value])):
                titles[int(pid.value)] = text
            return True

        user32.EnumWindows(WNDENUMPROC(callback), 0)
        return titles
    except Exception:  # noqa: BLE001
        return {}


def _acad_processes() -> list[dict[str, Any]]:
    """List running acad.exe processes using in-process Windows APIs."""

    if not com_client.is_windows():
        return []

    try:
        wintypes = ctypes.wintypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        TH32CS_SNAPPROCESS = 0x00000002
        invalid_handle = ctypes.c_void_p(-1).value

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_wchar * 260),
            ]

        kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

        snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if not snapshot or snapshot == invalid_handle:
            return [{"error": f"CreateToolhelp32Snapshot failed: {ctypes.get_last_error()}"}]

        results: list[dict[str, Any]] = []
        try:
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
            while ok:
                name = entry.szExeFile
                if name and name.lower() == "acad.exe":
                    results.append({"pid": int(entry.th32ProcessID), "name": name})
                ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
        finally:
            kernel32.CloseHandle(snapshot)

        titles = _window_titles_by_pid()
        for process in results:
            process["window_title"] = titles.get(process["pid"], "")
            process["integrity"] = _process_integrity(process["pid"])

        return results
    except Exception as exc:  # noqa: BLE001
        return [{"error": str(exc)}]


def diagnose_access(*, timeout_sec: float = 5.0) -> dict[str, Any]:
    """Return local AutoCAD access diagnostics without raising through MCP."""

    py_integrity = _process_integrity()
    processes = _acad_processes()
    com_result = com_client.get_active_document(allow_start=False, timeout_sec=timeout_sec)

    likely_issue = None
    if com_client.is_windows():
        py_level = py_integrity.get("level")
        for process in processes:
            acad_level = (process.get("integrity") or {}).get("level")
            if acad_level == "High" and py_level in {"Medium", "Low"}:
                likely_issue = (
                    "AutoCAD appears to be elevated while this Python/MCP process is not. "
                    "Run both at the same integrity level."
                )
                break

    return {
        "success": bool(com_result.get("success")),
        "platform": platform.platform(),
        "is_windows": com_client.is_windows(),
        "pywin32_available": com_client.has_pywin32() if com_client.is_windows() else False,
        "python_integrity": py_integrity,
        "autocad_processes": processes,
        "registered_progids": com_client.autocad_progids() if com_client.is_windows() else [],
        "com": com_result,
        "likely_issue": likely_issue,
    }
