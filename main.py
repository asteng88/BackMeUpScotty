"""
BackMeUpScotty — Entry Point.
Run with `python main.py` or `pythonw main.py` (or double-click `BackMeUpScotty.exe`).
Pass `--minimized` to start directly in the Windows System Tray.
"""

import os
import sys
import tkinter as tk

# Ensure workspace root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.ui import BackMeUpScottyApp


def main() -> None:
    # Enable High-DPI crisp pixel rendering on Windows
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    start_min = "--minimized" in sys.argv or "--tray" in sys.argv
    root = tk.Tk()
    _app = BackMeUpScottyApp(root, start_minimized=start_min)
    root.mainloop()


if __name__ == "__main__":
    main()
