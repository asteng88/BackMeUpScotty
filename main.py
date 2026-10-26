"""
BackMeUpScotty — Entry Point.
Run with `python main.py` or `pythonw main.py` (or double-click `BackMeUpScotty.exe`).
Pass `--minimized` to start directly in the Windows System Tray.
"""

import ctypes
import os
import sys
import tkinter as tk

# Ensure workspace root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.ui import BackMeUpScottyApp
from src.version import APP_VERSION


APP_WINDOW_TITLE = f"BackMeUpScotty v{APP_VERSION} // Retro Style Turbo Backup System"
_SINGLE_INSTANCE_MUTEX = r"Local\BackMeUpScotty.SingleInstance.v1"
_ERROR_ALREADY_EXISTS = 183


def _acquire_single_instance_mutex() -> tuple[int | None, bool]:
    """Return a mutex handle and whether another instance already owns it."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_mutex = kernel32.CreateMutexW
    create_mutex.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p)
    create_mutex.restype = ctypes.c_void_p

    handle = create_mutex(None, False, _SINGLE_INSTANCE_MUTEX)
    if not handle:
        return None, False
    return handle, ctypes.get_last_error() == _ERROR_ALREADY_EXISTS


def _show_running_instance() -> bool:
    """Restore the existing window when the user launches the app again."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    find_window = user32.FindWindowW
    find_window.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p)
    find_window.restype = ctypes.c_void_p

    hwnd = find_window(None, APP_WINDOW_TITLE)
    if not hwnd:
        return False

    user32.ShowWindow(hwnd, 9)  # SW_RESTORE also makes a withdrawn Tk window visible.
    user32.SetForegroundWindow(hwnd)
    return True


def main() -> None:
    mutex_handle = None
    if os.name == "nt":
        mutex_handle, already_running = _acquire_single_instance_mutex()
        if already_running:
            if not _show_running_instance():
                ctypes.WinDLL("user32").MessageBoxW(
                    None,
                    "BackMeUpScotty is already running. Use its existing system tray icon.",
                    "BackMeUpScotty",
                    0x00000040,  # MB_ICONINFORMATION
                )
            ctypes.WinDLL("kernel32").CloseHandle(mutex_handle)
            return

    # Enable High-DPI crisp pixel rendering on Windows
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    try:
        start_min = "--minimized" in sys.argv or "--tray" in sys.argv
        root = tk.Tk()
        _app = BackMeUpScottyApp(root, start_minimized=start_min)
        root.mainloop()
    finally:
        if mutex_handle:
            ctypes.WinDLL("kernel32").CloseHandle(mutex_handle)


if __name__ == "__main__":
    main()
