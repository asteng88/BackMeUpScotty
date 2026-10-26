"""Application version loaded from the repository and packaged VERSION file."""

from __future__ import annotations

from pathlib import Path
import sys


def _version_file() -> Path:
    """Locate VERSION in source runs and PyInstaller one-file builds."""
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "VERSION"
    return Path(__file__).resolve().parent.parent / "VERSION"


def _read_version() -> str:
    try:
        version = _version_file().read_text(encoding="utf-8").strip()
        if version:
            return version
    except OSError:
        pass
    return "0.0.0+unknown"


APP_VERSION = _read_version()
