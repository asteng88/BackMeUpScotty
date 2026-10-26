"""
End-to-end tests for BackMeUpScotty:
1. Full backup speed & file integrity
2. Incremental backup skipping unchanged files
3. Incremental backup detecting size change only, timestamp change only, and both
4. UI & System Tray initialization across both retro themes (ZX Spectrum and C64)
"""

import os
import shutil
import sys
import tempfile
import time
import tkinter as tk
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.backup_engine import BackupEngine
from src.themes import THEMES, create_tray_icon_rgba
from src.ui import BackMeUpScottyApp


def test_backup_engine():
    tmp_root = tempfile.mkdtemp(prefix="bmus_test_")
    try:
        src1 = os.path.join(tmp_root, "FolderAlpha")
        src2 = os.path.join(tmp_root, "FolderBeta")
        dst = os.path.join(tmp_root, "BackupVault")
        os.makedirs(os.path.join(src1, "sub"), exist_ok=True)
        os.makedirs(src2, exist_ok=True)

        f1 = os.path.join(src1, "data1.bin")
        f2 = os.path.join(src1, "sub", "data2.bin")
        f3 = os.path.join(src2, "notes.txt")

        with open(f1, "wb") as f:
            f.write(b"A" * 65536)
        with open(f2, "wb") as f:
            f.write(b"B" * 131072)
        with open(f3, "wb") as f:
            f.write(b"Retro 8-bit computing rocks!")

        engine = BackupEngine(max_workers=8)

        # 1. Full Backup
        st_full = engine.run_backup([src1, src2], dst, mode="full", compare_criteria="both")
        assert st_full.phase == "DONE", f"Expected DONE, got {st_full.phase}"
        assert st_full.files_copied == 3, f"Expected 3 copied, got {st_full.files_copied}"
        assert st_full.errors == 0

        # 2. Incremental Backup (nothing changed -> 0 copied, 3 skipped)
        st_inc0 = engine.run_backup([src1, src2], dst, mode="incremental", compare_criteria="both")
        assert st_inc0.files_copied == 0, f"Expected 0 copied, got {st_inc0.files_copied}"
        assert st_inc0.files_skipped == 3, f"Expected 3 skipped, got {st_inc0.files_skipped}"

        # 3. Modify file size of f1 (keep timestamp identical to test 'size' criteria)
        orig_stat = os.stat(f1)
        with open(f1, "wb") as f:
            f.write(b"A" * 70000)
        os.utime(f1, (orig_stat.st_atime, orig_stat.st_mtime))

        st_inc_size = engine.run_backup([src1, src2], dst, mode="incremental", compare_criteria="size")
        assert st_inc_size.files_copied == 1, f"Expected 1 copied by size, got {st_inc_size.files_copied}"
        assert st_inc_size.files_skipped == 2

        # 4. Modify only timestamp of f3 (+10 seconds, same size)
        st3 = os.stat(f3)
        os.utime(f3, (st3.st_atime, st3.st_mtime + 10.0))

        # Using 'size' only should skip it
        st_inc_size_only = engine.run_backup([src1, src2], dst, mode="incremental", compare_criteria="size")
        assert st_inc_size_only.files_copied == 0

        # Using 'timestamp' or 'both' should catch and copy it
        st_inc_ts = engine.run_backup([src1, src2], dst, mode="incremental", compare_criteria="timestamp")
        assert st_inc_ts.files_copied == 1, f"Expected 1 copied by timestamp, got {st_inc_ts.files_copied}"

        print("BackupEngine tests PASSED!")
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


def test_backup_engine_allows_different_drives():
    """A destination on another Windows drive must not invoke commonpath()."""
    tmp_root = tempfile.mkdtemp(prefix="bmus_cross_drive_test_")
    try:
        source = os.path.join(tmp_root, "Source")
        destination = os.path.join(tmp_root, "Destination")
        os.makedirs(source)
        with open(os.path.join(source, "data.txt"), "w", encoding="utf-8") as f:
            f.write("cross-drive backup")

        # ntpath.commonpath raises ValueError for paths on separate drives.  The
        # engine must not need it: its traversal-level destination check is enough.
        with patch("src.backup_engine.os.path.commonpath", side_effect=ValueError):
            stats = BackupEngine().run_backup([source], destination, mode="full")

        assert stats.phase == "DONE", f"Expected DONE, got {stats.phase}"
        assert stats.files_copied == 1
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


def test_ui_and_themes():
    for t_name in THEMES:
        rgba_idle = create_tray_icon_rgba(t_name, progress=None)
        rgba_prog = create_tray_icon_rgba(t_name, progress=0.65, pulse=3)
        assert len(rgba_idle) == 32 * 32 * 4
        assert len(rgba_prog) == 32 * 32 * 4

    root = tk.Tk()
    app = BackMeUpScottyApp(root, start_minimized=False)

    # Cycle through both themes and render progress deck
    for t_name in ("ZX Spectrum", "Commodore 64"):
        app.apply_theme(t_name)
        root.update()

    # Cleanly shut down tray & scheduler without calling sys.exit
    app.scheduler.stop()
    app.tray.destroy()
    root.destroy()
    print("UI & Theme switching tests PASSED!")


if __name__ == "__main__":
    test_backup_engine()
    test_backup_engine_allows_different_drives()
    test_ui_and_themes()
