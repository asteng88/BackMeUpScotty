"""
Retro themes and 8x8 bitmap fonts (Sinclair ZX Spectrum and Commodore 64),
and dynamic tray/app icon generators for BackMeUpScotty.
"""

import ctypes
import os

import os
from PIL import Image, ImageDraw, ImageFilter

_MASTER_ICON_CACHE: dict[int, Image.Image] = {}


def _get_master_icon(size: int = 32) -> Image.Image | None:
    if size in _MASTER_ICON_CACHE:
        return _MASTER_ICON_CACHE[size].copy()
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    master_path = os.path.join(root_dir, "assets", "app_icon_master.png")
    if os.path.exists(master_path):
        try:
            img = Image.open(master_path).convert("RGBA")
            resized = img.resize((size, size), Image.Resampling.LANCZOS)
            if size <= 48:
                resized = resized.filter(ImageFilter.UnsharpMask(radius=0.8, percent=130, threshold=2))
            _MASTER_ICON_CACHE[size] = resized
            return resized.copy()
        except Exception:
            pass
    return None


_FONT_FILES = (
    "Speccy.ttf",       # ZX Spectrum, Kreative Software
    "PetMe64.ttf",      # Commodore 64, Kreative Software
)


def register_embedded_fonts() -> None:
    """Make the bundled system fonts available to this Windows process only."""
    if os.name != "nt":
        return

    font_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts"
    )
    try:
        add_font = ctypes.windll.gdi32.AddFontResourceExW
        add_font.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
        add_font.restype = ctypes.c_int
        private_font = 0x10  # FR_PRIVATE: no system-wide installation required
        for filename in _FONT_FILES:
            path = os.path.join(font_dir, filename)
            if os.path.isfile(path):
                add_font(path, private_font, None)
    except (AttributeError, OSError):
        # Tk will use its normal fallback font if private registration is unavailable.
        pass

THEMES = {
    "ZX Spectrum": {
        "id": "zx",
        "name": "ZX Spectrum 48K",
        "boot_banner": "© 1982 Sinclair Research Ltd",
        "ready_prompt": "0 OK, 0:1",
        "border_idle": "#D7D7D7", # Grey border
        "border_active_1": ["#D70000", "#00D7D7"],  # Red / Cyan pilot stripes
        "border_active_2": ["#0000D7", "#D7D700"],  # Blue / Yellow data stripes
        "paper": "#D7D7D7", # Grey background
        "panel_bg": "#000000", # Black panel background
        "panel_fg": "#FFFFFF", # White panel text
        "ink": "#000000", # Black text
        "accent": "#0000D7", # Blue accent
        "accent_bright": "#00FFFF", # Cyan bright
        "highlight": "#D700D7", # Magenta highlight
        "success": "#00D700", # Green success
        "warning": "#D7D700", # Yellow warning
        "danger": "#D70000", # Red danger
        "button_bg": "#0000D7", # Blue button background
        "button_fg": "#FFFFFF", # White button text
        "button_active_bg": "#D700D7", # Magenta button active background
        "button_active_fg": "#FFFF00", # Yellow button active text
        "input_bg": "#FFFFFF", # White input background
        "input_fg": "#000000", # Black input text
        "bar_bg": "#000000", # Black bar background
        "bar_fg": "#00FFFF", # Cyan bar foreground
        "bar_alt": "#FFFF00", # Yellow bar alternate
        "rainbow": ["#D70000", "#D7D700", "#00D700", "#00D7D7", "#0000D7", "#D700D7"], # Rainbow colors
        "font_family": "Speccy",
        "scanline_alpha": 22, # Scanline transparency
    },
    "Commodore 64": {
        "id": "c64",
        "name": "Commodore 64",
        "boot_banner": "**** COMMODORE 64 BASIC V2 ****\n64K RAM SYSTEM  38911 BASIC BYTES FREE",
        "ready_prompt": "READY.",
        "border_idle": "#70A4B2",  # C64 Light Blue
        "border_active_1": ["#6C5EB5", "#70A4B2", "#B8C76F", "#883932"],  # Raster bars
        "border_active_2": ["#9AD284", "#352879", "#6F3D86", "#588D43"],
        "paper": "#352879",        # C64 Dark Blue
        "panel_bg": "#221955", # Dark blue panel background
        "panel_fg": "#70A4B2", # Light blue panel text
        "ink": "#70A4B2",          # Light Blue text
        "accent": "#B8C76F",       # C64 Yellow
        "accent_bright": "#FFFFFF", # White bright
        "highlight": "#6F3D86", # Magenta highlight
        "success": "#9AD284",      # Light Green
        "warning": "#B8C76F",      # Yellow
        "danger": "#9A6759",       # Light Red
        "button_bg": "#70A4B2", # Light blue button background
        "button_fg": "#352879", # Dark blue button text
        "button_active_bg": "#FFFFFF", # White button active background
        "button_active_fg": "#352879", # Dark blue button active text
        "input_bg": "#221955", # Dark blue input background
        "input_fg": "#FFFFFF", # White input text
        "bar_bg": "#1A1244", # Dark blue bar background
        "bar_fg": "#9AD284", # Light green bar foreground
        "bar_alt": "#70A4B2", # Light blue bar alternate
        "rainbow": ["#883932", "#675200", "#B8C76F", "#588D43", "#70A4B2", "#6F3D86"], # Rainbow colors
        "font_family": "Pet Me 64",
        "scanline_alpha": 35, # Scanline transparency
    },
}


def hex_to_rgba(h: str, alpha: int = 255) -> tuple[int, int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


def create_tray_icon_rgba(theme_name: str, progress: float | None = None, pulse: int = 0, size: int = 32) -> bytes:
    """
    Generates a crisp RGBA icon for the Windows System Tray & Window using the high-res
    master app icon (`assets/app_icon_master.png`), with live progress bar and pulsing activity
    overlays when a backup is running.
    """
    theme = THEMES.get(theme_name, THEMES["ZX Spectrum"])
    master = _get_master_icon(size)
    if master is not None:
        img = master
        draw = ImageDraw.Draw(img)
        if progress is not None:
            pct = max(0.0, min(1.0, float(progress)))
            # Draw high-contrast progress bar overlay across bottom of the master icon
            bar_h = max(6, size // 5)
            y1 = size - bar_h - 2
            y2 = size - 2
            draw.rectangle([2, y1, size - 3, y2], fill=(0, 0, 0, 235), outline=(255, 255, 255, 255))
            fill_w = int((size - 7) * pct)
            if fill_w > 0:
                draw.rectangle([3, y1 + 1, 3 + fill_w, y2 - 1], fill=hex_to_rgba(theme["bar_fg"]))
            # Pulsing neon activity LED in top-right corner
            dot_r = max(3, size // 8)
            dot_c = (0, 255, 255, 255) if (pulse % 2 == 0) else (57, 255, 20, 255)
            draw.ellipse([size - dot_r * 2 - 2, 2, size - 2, 2 + dot_r * 2], fill=dot_c, outline=(0, 0, 0, 255))
        return img.tobytes()

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Outer retro bezel
    if progress is not None:
        # Animated loading border stripes in the tray icon!
        stripes = theme["border_active_1"] if (pulse % 2 == 0) else theme["border_active_2"]
        stripe_h = 2
        for y in range(size):
            c = hex_to_rgba(stripes[(y // stripe_h + pulse) % len(stripes)])
            draw.line([(0, y), (size - 1, y)], fill=c)
        # Inner cavity
        draw.rectangle([3, 3, size - 4, size - 4], fill=hex_to_rgba(theme["paper"]))
    else:
        border_c = hex_to_rgba(theme["border_idle"])
        draw.rectangle([0, 0, size - 1, size - 1], fill=border_c)
        draw.rectangle([2, 2, size - 3, size - 3], fill=hex_to_rgba(theme["paper"]))

    if theme["id"] == "zx":
        # Draw iconic ZX Spectrum diagonal rainbow slash in top-right/bottom-right
        rainbow = theme["rainbow"]
        for i, col in enumerate(rainbow):
            c = hex_to_rgba(col)
            offset = 12 + i * 3
            draw.line([(offset, 3), (offset - 10, 17)], fill=c, width=2)
        # Draw "ZX" pixel emblem on top-left
        fg = hex_to_rgba(theme["ink"])
        draw.rectangle([4, 4, 15, 13], fill=hex_to_rgba("#000000"))
        # 'Z'
        draw.line([(6, 6), (11, 6)], fill=(255, 255, 255, 255))
        draw.line([(11, 6), (6, 11)], fill=(255, 255, 255, 255))
        draw.line([(6, 11), (11, 11)], fill=(255, 255, 255, 255))

    elif theme["id"] == "c64":
        # Draw C= Commodore chicken-lips pixel emblem
        c_blue = hex_to_rgba("#70A4B2")
        c_red = hex_to_rgba("#883932")
        c_white = (255, 255, 255, 255)
        draw.ellipse([5, 4, 17, 16], outline=c_white, width=2)
        draw.rectangle([13, 4, 24, 16], fill=hex_to_rgba(theme["paper"]))
        # Twin flags
        draw.rectangle([14, 6, 23, 8], fill=c_blue)
        draw.rectangle([14, 11, 23, 13], fill=c_red)

    # Bottom section: either cassette tape reels (idle) or live progress bar (active backup)
    if progress is not None:
        pct = max(0.0, min(1.0, float(progress)))
        # High-contrast progress track at bottom of icon (y=19..28)
        draw.rectangle([4, 18, size - 5, size - 5], fill=(0, 0, 0, 255), outline=(255, 255, 255, 255))
        fill_w = int((size - 10) * pct)
        if fill_w > 0:
            bar_color = hex_to_rgba(theme["bar_fg"])
            draw.rectangle([5, 19, 5 + fill_w, size - 6], fill=bar_color)
        # Spinning activity indicator dot in top-right
        dot_color = (255, 255, 0, 255) if (pulse % 2 == 0) else (0, 255, 255, 255)
        draw.ellipse([size - 9, 5, size - 5, 9], fill=dot_color)
    else:
        # Mini cassette deck / ready bar at bottom
        draw.rectangle([5, 20, size - 6, size - 5], fill=(0, 0, 0, 255))
        reel_c = hex_to_rgba(theme["accent_bright"])
        draw.rectangle([8, 22, 11, 25], fill=reel_c)
        draw.rectangle([size - 12, 22, size - 9, 25], fill=reel_c)
        draw.line([(13, 23), (size - 14, 23)], fill=hex_to_rgba(theme["success"]))

    return img.tobytes()
