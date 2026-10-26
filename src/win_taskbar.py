"""
Native Windows System Tray (Notification Area) icon with right-click popup menu,
live animated progress icon updates, and Windows Taskbar button progress bar
(ITaskbarList3) using pure ctypes (zero external dependencies).
"""

import ctypes
from ctypes import wintypes
import threading
from typing import Callable


user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
shell32 = ctypes.windll.shell32
kernel32 = ctypes.windll.kernel32
ole32 = ctypes.windll.ole32

# Win32 Constants
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_COMMAND = 0x0111
WM_USER = 0x0400
WM_TRAYICON = WM_USER + 20

WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_CONTEXTMENU = 0x007B

NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_INFO = 0x00000010

MF_STRING = 0x00000000
MF_SEPARATOR = 0x00000800
MF_GRAYED = 0x00000001
MF_DEFAULT = 0x00001000
TPM_LEFTALIGN = 0x0000
TPM_RETURNCMD = 0x0100
TPM_NONOTIFY = 0x0080
TPM_RIGHTBUTTON = 0x0002

# Menu command IDs
ID_SHOW_HIDE = 1001
ID_EDIT_SCHEDULE = 1002
ID_RUN_FULL = 1003
ID_RUN_INCREMENTAL = 1004
ID_THEME_ZX = 1005
ID_THEME_C64 = 1006
ID_EXIT = 1009

WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)

user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_ssize_t


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uTimeoutOrVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", wintypes.HBITMAP),
        ("hbmColor", wintypes.HBITMAP),
    ]


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8),
    ]

    def __init__(self, d1, d2, d3, *d4):
        super().__init__(d1, d2, d3, (wintypes.BYTE * 8)(*d4))


CLSID_TaskbarList = GUID(0x56FDF344, 0xFD6D, 0x11D0, 0x95, 0x8A, 0x00, 0x60, 0x97, 0xC9, 0xA0, 0x90)
IID_ITaskbarList3 = GUID(0xEA1AFB91, 0x9E28, 0x4B86, 0x90, 0xE9, 0x9E, 0x9F, 0x8A, 0x5E, 0xEF, 0xAF)


def create_hicon_from_rgba(rgba_bytes: bytes, width: int = 32, height: int = 32) -> int:
    """Creates a Win32 HICON from raw RGBA bytes."""
    bgra = bytearray(len(rgba_bytes))
    for i in range(0, len(rgba_bytes), 4):
        bgra[i] = rgba_bytes[i + 2]
        bgra[i + 1] = rgba_bytes[i + 1]
        bgra[i + 2] = rgba_bytes[i]
        bgra[i + 3] = rgba_bytes[i + 3]

    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = width
    bmi.biHeight = -height
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    bmi.biCompression = 0

    ppvBits = ctypes.c_void_p()
    hdc = user32.GetDC(0)
    hbmColor = gdi32.CreateDIBSection(hdc, ctypes.byref(bmi), 0, ctypes.byref(ppvBits), None, 0)
    user32.ReleaseDC(0, hdc)

    ctypes.memmove(ppvBits, bytes(bgra), len(bgra))
    hbmMask = gdi32.CreateBitmap(width, height, 1, 1, None)

    ii = ICONINFO()
    ii.fIcon = True
    ii.xHotspot = 0
    ii.yHotspot = 0
    ii.hbmMask = hbmMask
    ii.hbmColor = hbmColor

    hicon = user32.CreateIconIndirect(ctypes.byref(ii))
    gdi32.DeleteObject(hbmColor)
    gdi32.DeleteObject(hbmMask)
    return hicon


class TaskbarProgressOverlay:
    """Controls the Windows 10/11 Taskbar button progress bar via ITaskbarList3 COM."""

    TBPF_NOPROGRESS = 0x0
    TBPF_INDETERMINATE = 0x1
    TBPF_NORMAL = 0x2
    TBPF_ERROR = 0x4
    TBPF_PAUSED = 0x8

    def __init__(self):
        self.ptr = ctypes.c_void_p()
        try:
            ole32.CoInitialize(None)
            hr = ole32.CoCreateInstance(
                ctypes.byref(CLSID_TaskbarList),
                None,
                1,  # CLSCTX_INPROC_SERVER
                ctypes.byref(IID_ITaskbarList3),
                ctypes.byref(self.ptr),
            )
            if hr == 0 and self.ptr.value:
                vtable = ctypes.cast(self.ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                HrInit = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(vtable[3])
                HrInit(self.ptr)
        except Exception:
            self.ptr = ctypes.c_void_p()

    def set_state(self, hwnd: int, state: int) -> None:
        if not self.ptr.value or not hwnd:
            return
        try:
            vtable = ctypes.cast(self.ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
            SetProgressState = ctypes.WINFUNCTYPE(
                ctypes.c_long, ctypes.c_void_p, wintypes.HWND, ctypes.c_int
            )(vtable[10])
            SetProgressState(self.ptr, hwnd, state)
        except Exception:
            pass

    def set_value(self, hwnd: int, completed: int, total: int = 1000) -> None:
        if not self.ptr.value or not hwnd:
            return
        try:
            vtable = ctypes.cast(self.ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
            SetProgressValue = ctypes.WINFUNCTYPE(
                ctypes.c_long,
                ctypes.c_void_p,
                wintypes.HWND,
                ctypes.c_ulonglong,
                ctypes.c_ulonglong,
            )(vtable[9])
            SetProgressValue(self.ptr, hwnd, max(0, completed), max(1, total))
        except Exception:
            pass


class SystemTrayIcon:
    """
    Runs a dedicated lightweight Win32 message-only window for the Notification Area (System Tray) icon.
    Right-click opens the context menu with:
      - Show / Restore Interface
      - Edit Schedule...
      - Run Full Backup
      - Run Incremental Backup
      - Theme Switcher (ZX Spectrum / C64)
      - Exit Application
    """

    def __init__(
        self,
        initial_rgba: bytes,
        tooltip: str,
        on_show_window: Callable[[], None],
        on_edit_schedule: Callable[[], None],
        on_run_full: Callable[[], None],
        on_run_incremental: Callable[[], None],
        on_change_theme: Callable[[str], None],
        on_exit: Callable[[], None],
    ):
        self._initial_rgba = initial_rgba
        self._tooltip = tooltip
        self.on_show_window = on_show_window
        self.on_edit_schedule = on_edit_schedule
        self.on_run_full = on_run_full
        self.on_run_incremental = on_run_incremental
        self.on_change_theme = on_change_theme
        self.on_exit = on_exit

        self.hwnd = None
        self.hicon = None
        self._nid = None
        self._ready = threading.Event()
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._message_loop, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=3.0)

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAYICON:
            event = lparam & 0xFFFF
            if event in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                self.on_show_window()
                return 0
            elif event in (WM_RBUTTONUP, WM_CONTEXTMENU):
                self._show_popup_menu(hwnd)
                return 0
        elif msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _show_popup_menu(self, hwnd):
        hmenu = user32.CreatePopupMenu()
        user32.AppendMenuW(hmenu, MF_STRING | MF_DEFAULT, ID_SHOW_HIDE, "Open BackMeUpScotty")
        user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(hmenu, MF_STRING, ID_EDIT_SCHEDULE, "Edit Schedule...")
        user32.AppendMenuW(hmenu, MF_STRING, ID_RUN_FULL, "Run Full Backup")
        user32.AppendMenuW(hmenu, MF_STRING, ID_RUN_INCREMENTAL, "Run Incremental Backup")
        user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(hmenu, MF_STRING, ID_THEME_ZX, "Theme: ZX Spectrum 48K")
        user32.AppendMenuW(hmenu, MF_STRING, ID_THEME_C64, "Theme: Commodore 64")
        user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(hmenu, MF_STRING, ID_EXIT, "Exit Application")

        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(hwnd)
        cmd = user32.TrackPopupMenu(
            hmenu,
            TPM_LEFTALIGN | TPM_RETURNCMD | TPM_NONOTIFY | TPM_RIGHTBUTTON,
            pt.x,
            pt.y,
            0,
            hwnd,
            None,
        )
        user32.PostMessageW(hwnd, 0, 0, 0)
        user32.DestroyMenu(hmenu)

        if cmd == ID_SHOW_HIDE:
            self.on_show_window()
        elif cmd == ID_EDIT_SCHEDULE:
            self.on_edit_schedule()
        elif cmd == ID_RUN_FULL:
            self.on_run_full()
        elif cmd == ID_RUN_INCREMENTAL:
            self.on_run_incremental()
        elif cmd == ID_THEME_ZX:
            self.on_change_theme("ZX Spectrum")
        elif cmd == ID_THEME_C64:
            self.on_change_theme("C64")
        elif cmd == ID_EXIT:
            self.on_exit()

    def _message_loop(self):
        self._wnd_proc_cb = WNDPROC(self._wnd_proc)
        hinst = kernel32.GetModuleHandleW(None)
        class_name = f"BackMeUpScottyTray_{id(self)}"

        wc = WNDCLASSW()
        wc.style = 0
        wc.lpfnWndProc = self._wnd_proc_cb
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = hinst
        wc.hIcon = 0
        wc.hCursor = 0
        wc.hbrBackground = 0
        wc.lpszMenuName = None
        wc.lpszClassName = class_name

        user32.RegisterClassW(ctypes.byref(wc))
        self.hwnd = user32.CreateWindowExW(
            0, class_name, "BackMeUpScottyTrayWindow", 0, 0, 0, 0, 0, 0, 0, hinst, None
        )

        self.hicon = create_hicon_from_rgba(self._initial_rgba, 32, 32)
        self._nid = NOTIFYICONDATAW()
        self._nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        self._nid.hWnd = self.hwnd
        self._nid.uID = 1
        self._nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        self._nid.uCallbackMessage = WM_TRAYICON
        self._nid.hIcon = self.hicon
        self._nid.szTip = self._tooltip[:127]

        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._nid))
        self._ready.set()

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def update_icon_and_tip(self, rgba_bytes: bytes, tooltip: str) -> None:
        with self._lock:
            if not self.hwnd or not self._nid:
                return
            new_hicon = create_hicon_from_rgba(rgba_bytes, 32, 32)
            old_hicon = self.hicon
            self.hicon = new_hicon
            self._nid.hIcon = new_hicon
            self._nid.szTip = tooltip[:127]
            self._nid.uFlags = NIF_ICON | NIF_TIP
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._nid))
            if old_hicon:
                user32.DestroyIcon(old_hicon)

    def show_balloon(self, title: str, message: str) -> None:
        with self._lock:
            if not self.hwnd or not self._nid:
                return
            self._nid.uFlags = NIF_INFO
            self._nid.szInfoTitle = title[:63]
            self._nid.szInfo = message[:255]
            self._nid.dwInfoFlags = 0x00000001  # NIIF_INFO
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._nid))

    def destroy(self) -> None:
        with self._lock:
            if self._nid and self.hwnd:
                shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
                self._nid = None
            if self.hicon:
                user32.DestroyIcon(self.hicon)
                self.hicon = None
            if self.hwnd:
                user32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)
                self.hwnd = None
