"""Build a self-contained Windows executable with PyInstaller.

The executable created by this script can be copied on its own to another
Windows computer.  It does not depend on a nearby ``main.py`` or on Python
being installed on that computer.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.themes import create_tray_icon_rgba


def generate_ico(ico_path: Path) -> None:
    """Generate the application icon used by Windows and PyInstaller."""
    ico_path.parent.mkdir(exist_ok=True)
    master_png = ico_path.parent / "app_icon_master.png"
    if master_png.exists():
        with Image.open(master_png) as source:
            source.convert("RGBA").save(
                ico_path,
                format="ICO",
                sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
            )
        print(f"Generated multi-resolution icon: {ico_path}")
        return

    base_rgba = create_tray_icon_rgba("ZX Spectrum", progress=None, size=32)
    image = Image.frombytes("RGBA", (32, 32), base_rgba)
    image.resize((256, 256), Image.Resampling.NEAREST).save(
        ico_path, format="ICO", sizes=[(32, 32), (64, 64), (128, 128), (256, 256)]
    )
    print(f"Generated retro icon: {ico_path}")


def build_exe() -> None:
    root_dir = Path(__file__).resolve().parent
    ico_path = root_dir / "assets" / "app_icon.ico"
    generate_ico(ico_path)

    try:
        import PyInstaller  # noqa: F401  # Check before launching the build.
    except ImportError as error:
        raise SystemExit(
            "PyInstaller is required to create a portable executable. Install build "
            "dependencies with:\n\n"
            f'  "{sys.executable}" -m pip install -r requirements-build.txt'
        ) from error

    separator = ";"  # PyInstaller uses a semicolon to separate source and destination on Windows.
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        "BackMeUpScotty",
        "--icon",
        str(ico_path),
        "--add-data",
        f"{root_dir / 'assets'}{separator}assets",
        "--distpath",
        str(root_dir),
        "--workpath",
        str(root_dir / "build"),
        "--specpath",
        str(root_dir / "build"),
        str(root_dir / "main.py"),
    ]
    print("Building portable BackMeUpScotty.exe with PyInstaller...")
    subprocess.run(command, check=True, cwd=root_dir)
    print(f"Portable executable created: {root_dir / 'BackMeUpScotty.exe'}")


if __name__ == "__main__":
    build_exe()
