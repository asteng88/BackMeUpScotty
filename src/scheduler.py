"""
Persistent configuration and lightweight background backup scheduler for BackMeUpScotty.
Stores settings in a local JSON file (`config.json` next to the app or in `%APPDATA%\\BackMeUpScotty`).
"""

from dataclasses import dataclass, field, asdict
import datetime
import json
import os
import sys
import threading
import time
from typing import Callable


def get_config_path() -> str:
    # A PyInstaller one-file executable runs from a temporary extraction
    # directory.  Settings written there disappear after it exits, so always
    # use the per-user application-data directory for packaged builds.
    if getattr(sys, "frozen", False):
        return _appdata_config_path()

    # Prefer a workspace config while developing, fallback to APPDATA.
    local_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_cfg = os.path.join(local_dir, "backmeupscotty_config.json")
    try:
        if os.path.exists(local_cfg) or os.access(local_dir, os.W_OK):
            return local_cfg
    except OSError:
        pass
    return _appdata_config_path()


def _appdata_config_path() -> str:
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    cfg_dir = os.path.join(appdata, "BackMeUpScotty")
    os.makedirs(cfg_dir, exist_ok=True)
    return os.path.join(cfg_dir, "config.json")


@dataclass
class AppConfig:
    theme: str = "ZX Spectrum"            # "ZX Spectrum" or "C64"
    source_folders: list[str] = field(default_factory=list)
    destination_folder: str = ""
    backup_mode: str = "incremental"      # "full" or "incremental"
    compare_criteria: str = "both"        # "both", "size", "timestamp"
    worker_threads: int = 8
    sound_effects: bool = False
    minimize_to_tray_on_close: bool = True

    # Schedule settings
    schedule_enabled: bool = False
    schedule_type: str = "interval"       # "interval" or "daily"
    interval_minutes: int = 60            # e.g., every 60 minutes
    daily_time: str = "02:00"             # HH:MM (24-hour)
    scheduled_backup_mode: str = "incremental"  # "full" or "incremental"
    last_scheduled_run: str = ""

    def save(self) -> None:
        path = get_config_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2)
        except OSError:
            pass

    @classmethod
    def load(cls) -> "AppConfig":
        path = get_config_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                valid_keys = {k for k in cls.__dataclass_fields__}
                filtered = {k: v for k, v in data.items() if k in valid_keys}
                return cls(**filtered)
            except Exception:
                pass
        return cls()


class BackupScheduler:
    """
    Lightweight, zero-polling-overhead background scheduler thread.
    Checks once per second using an Event wait whether a scheduled backup is due.
    """

    def __init__(self, get_config: Callable[[], AppConfig], trigger_backup: Callable[[str], None]):
        self.get_config = get_config
        self.trigger_backup = trigger_backup
        self._stop_event = threading.Event()
        self._last_interval_ts = time.time()
        self._last_daily_date = ""
        self.next_run_display: str = "OFF"
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def reset_timer(self) -> None:
        self._last_interval_ts = time.time()
        self._update_next_display(self.get_config())

    def stop(self) -> None:
        self._stop_event.set()

    def _update_next_display(self, cfg: AppConfig) -> None:
        if not cfg.schedule_enabled:
            self.next_run_display = "OFF"
            return
        if cfg.schedule_type == "interval":
            mins = max(1, int(cfg.interval_minutes))
            rem = max(0, int((self._last_interval_ts + mins * 60) - time.time()))
            m, s = divmod(rem, 60)
            h, m = divmod(m, 60)
            if h > 0:
                self.next_run_display = f"IN {h:02d}:{m:02d}:{s:02d} ({cfg.scheduled_backup_mode[:4].upper()})"
            else:
                self.next_run_display = f"IN {m:02d}m {s:02d}s ({cfg.scheduled_backup_mode[:4].upper()})"
        else:
            self.next_run_display = f"DAILY @ {cfg.daily_time} ({cfg.scheduled_backup_mode[:4].upper()})"

    def _loop(self) -> None:
        while not self._stop_event.wait(1.0):
            cfg = self.get_config()
            self._update_next_display(cfg)
            if not cfg.schedule_enabled:
                self._last_interval_ts = time.time()
                continue

            now = time.time()
            if cfg.schedule_type == "interval":
                interval_sec = max(1, int(cfg.interval_minutes)) * 60
                if now - self._last_interval_ts >= interval_sec:
                    self._last_interval_ts = now
                    self.trigger_backup(cfg.scheduled_backup_mode)
            elif cfg.schedule_type == "daily":
                dt = datetime.datetime.now()
                hhmm = dt.strftime("%H:%M")
                today_str = dt.strftime("%Y-%m-%d")
                if hhmm == cfg.daily_time.strip() and self._last_daily_date != today_str:
                    self._last_daily_date = today_str
                    self.trigger_backup(cfg.scheduled_backup_mode)
