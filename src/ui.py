"""
BackMeUpScotty — Retro 8-Bit High-Speed Folder Backup Application.
Supports authentic ZX Spectrum 48K and Commodore 64 BASIC V2 themes,
animated tape-loading border & deck progress, Windows Taskbar + System Tray live progress,
Full & Incremental (Size / Timestamp / Both) multi-threaded kernel-DMA copying, and scheduling.
"""

import ctypes
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

from src.themes import THEMES, create_tray_icon_rgba, register_embedded_fonts
from src.backup_engine import BackupEngine, BackupStats
from src.scheduler import AppConfig, BackupScheduler
from src.win_taskbar import SystemTrayIcon, TaskbarProgressOverlay


def format_bytes(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    elif num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"


def center_popup(window: tk.Toplevel) -> None:
    """Place a fully laid-out popup in the center of the primary display."""
    window.update_idletasks()
    width = window.winfo_width()
    height = window.winfo_height()
    x = max(0, (window.winfo_screenwidth() - width) // 2)
    y = max(0, (window.winfo_screenheight() - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


class ScheduleDialog(tk.Toplevel):
    """Retro-themed modal dialog to edit the automated backup schedule."""

    def __init__(self, parent: "BackMeUpScottyApp", config: AppConfig, theme: dict, on_save):
        super().__init__(parent.root)
        self.parent = parent
        parent._apply_application_icon(self)
        self.config_obj = config
        self.theme = theme
        self.on_save = on_save

        self.title("SCHEDULE CONFIG // AUTO-TAPE TIMER")
        self.geometry("900x410")
        self.resizable(False, False)
        self.configure(bg=theme["paper"], highlightthickness=6, highlightbackground=theme["border_idle"])
        self.transient(parent.root)
        self.grab_set()

        font_fam = theme["font_family"]
        hdr_font = (font_fam, 12, "bold")
        lbl_font = (font_fam, 10, "bold")
        btn_font = (font_fam, 10, "bold")

        # Banner
        banner = tk.Label(
            self,
            text="[ AUTOMATED BACKUP SCHEDULER ]",
            font=hdr_font,
            bg=theme["panel_bg"],
            fg=theme["accent_bright"],
            pady=8,
        )
        banner.pack(fill=tk.X, padx=12, pady=(12, 8))

        body = tk.Frame(self, bg=theme["paper"])
        body.pack(fill=tk.BOTH, expand=True, padx=18, pady=6)

        self.enabled_var = tk.BooleanVar(value=config.schedule_enabled)
        chk = tk.Checkbutton(
            body,
            text="ENABLE SCHEDULED BACKGROUND BACKUPS",
            variable=self.enabled_var,
            font=lbl_font,
            bg=theme["paper"],
            fg=theme["ink"],
            selectcolor=theme["input_bg"],
            activebackground=theme["paper"],
            activeforeground=theme["accent"],
        )
        chk.pack(anchor="w", pady=(4, 12))

        # Trigger type
        tk.Label(
            body, text="SCHEDULE TRIGGER MODE:", font=lbl_font, bg=theme["paper"], fg=theme["ink"]
        ).pack(anchor="w")

        self.type_var = tk.StringVar(value=config.schedule_type)
        r_frame = tk.Frame(body, bg=theme["paper"])
        r_frame.pack(fill=tk.X, pady=(4, 10))

        tk.Radiobutton(
            r_frame,
            text="Every N Minutes",
            variable=self.type_var,
            value="interval",
            font=lbl_font,
            bg=theme["paper"],
            fg=theme["ink"],
            selectcolor=theme["input_bg"],
            activebackground=theme["paper"],
        ).pack(side=tk.LEFT, padx=(0, 16))

        tk.Radiobutton(
            r_frame,
            text="Daily at HH:MM (24h)",
            variable=self.type_var,
            value="daily",
            font=lbl_font,
            bg=theme["paper"],
            fg=theme["ink"],
            selectcolor=theme["input_bg"],
            activebackground=theme["paper"],
        ).pack(side=tk.LEFT)

        # Interval & Daily inputs
        grid_f = tk.Frame(body, bg=theme["paper"])
        grid_f.pack(fill=tk.X, pady=6)

        tk.Label(
            grid_f, text="Interval (Minutes):", font=lbl_font, bg=theme["paper"], fg=theme["ink"]
        ).grid(row=0, column=0, sticky="w", pady=6)
        self.interval_var = tk.StringVar(value=str(config.interval_minutes))
        tk.Entry(
            grid_f,
            textvariable=self.interval_var,
            width=10,
            font=lbl_font,
            bg=theme["input_bg"],
            fg=theme["input_fg"],
            insertbackground=theme["input_fg"],
            relief=tk.FLAT,
            highlightthickness=2,
            highlightbackground=theme["accent"],
        ).grid(row=0, column=1, sticky="w", padx=12, pady=6)

        tk.Label(
            grid_f, text="Daily Time (HH:MM):", font=lbl_font, bg=theme["paper"], fg=theme["ink"]
        ).grid(row=1, column=0, sticky="w", pady=6)
        self.daily_var = tk.StringVar(value=config.daily_time)
        tk.Entry(
            grid_f,
            textvariable=self.daily_var,
            width=10,
            font=lbl_font,
            bg=theme["input_bg"],
            fg=theme["input_fg"],
            insertbackground=theme["input_fg"],
            relief=tk.FLAT,
            highlightthickness=2,
            highlightbackground=theme["accent"],
        ).grid(row=1, column=1, sticky="w", padx=12, pady=6)

        # Scheduled Backup Type
        tk.Label(
            body,
            text="SCHEDULED BACKUP TYPE:",
            font=lbl_font,
            bg=theme["paper"],
            fg=theme["ink"],
        ).pack(anchor="w", pady=(10, 4))

        self.mode_var = tk.StringVar(value=config.scheduled_backup_mode)
        m_frame = tk.Frame(body, bg=theme["paper"])
        m_frame.pack(fill=tk.X)

        tk.Radiobutton(
            m_frame,
            text="Incremental (Fast Delta)",
            variable=self.mode_var,
            value="incremental",
            font=lbl_font,
            bg=theme["paper"],
            fg=theme["ink"],
            selectcolor=theme["input_bg"],
        ).pack(side=tk.LEFT, padx=(0, 16))

        tk.Radiobutton(
            m_frame,
            text="Full Backup",
            variable=self.mode_var,
            value="full",
            font=lbl_font,
            bg=theme["paper"],
            fg=theme["ink"],
            selectcolor=theme["input_bg"],
        ).pack(side=tk.LEFT)

        # Buttons
        btn_f = tk.Frame(self, bg=theme["paper"])
        btn_f.pack(fill=tk.X, padx=18, pady=14)

        tk.Button(
            btn_f,
            text="SAVE SCHEDULE",
            command=self._save,
            font=btn_font,
            bg=theme["button_bg"],
            fg=theme["button_fg"],
            activebackground=theme["button_active_bg"],
            activeforeground=theme["button_active_fg"],
            relief=tk.FLAT,
            padx=14,
            pady=6,
            cursor="hand2",
        ).pack(side=tk.RIGHT, padx=(8, 0))

        tk.Button(
            btn_f,
            text="CANCEL",
            command=self.destroy,
            font=btn_font,
            bg=theme["panel_bg"],
            fg=theme["panel_fg"],
            relief=tk.FLAT,
            padx=14,
            pady=6,
            cursor="hand2",
        ).pack(side=tk.RIGHT)

        center_popup(self)

    def _save(self):
        try:
            mins = max(1, int(self.interval_var.get().strip()))
        except ValueError:
            messagebox.showerror("Invalid Interval", "Please enter a valid number of minutes (>= 1).", parent=self)
            return

        daily = self.daily_var.get().strip()
        parts = daily.split(":")
        if len(parts) != 2 or not (parts[0].isdigit() and parts[1].isdigit()):
            messagebox.showerror("Invalid Time", "Please enter daily time in 24-hour HH:MM format (e.g. 02:30).", parent=self)
            return
        hh, mm = int(parts[0]), int(parts[1])
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            messagebox.showerror("Invalid Time", "Hours must be 00..23 and minutes 00..59.", parent=self)
            return

        self.config_obj.schedule_enabled = bool(self.enabled_var.get())
        self.config_obj.schedule_type = self.type_var.get()
        self.config_obj.interval_minutes = mins
        self.config_obj.daily_time = f"{hh:02d}:{mm:02d}"
        self.config_obj.scheduled_backup_mode = self.mode_var.get()
        self.config_obj.save()
        self.on_save()
        self.destroy()


class BackMeUpScottyApp:
    """Main application controller and authentic 8-bit retro UI."""

    def __init__(self, root: tk.Tk, start_minimized: bool = False):
        self.root = root
        register_embedded_fonts()
        self.config = AppConfig.load()
        self.engine = BackupEngine(max_workers=self.config.worker_threads)
        self.latest_stats = BackupStats()
        self._stats_lock = threading.Lock()
        # Set before the worker gets CPU time so a click immediately produces
        # visible feedback, even while the engine is opening folders.
        self._backup_ui_active = False
        self._completion_popup: tk.Toplevel | None = None
        self._cassette_tape_image: ImageTk.PhotoImage | None = None
        self._success_popup_image: ImageTk.PhotoImage | None = None
        self._window_icon_handles: list[int] = []
        self._native_icon_window_ids: set[int] = set()
        self._anim_tick = 0
        self._last_tray_update = 0.0
        self._schedule_dialog: ScheduleDialog | None = None

        # Set Windows AppUserModelID so our custom icon & taskbar progress bar bind properly
        if os.name == "nt":
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "RetroSoft.BackMeUpScotty.8BitBackup.1"
                )
            except Exception:
                pass

        self.taskbar_overlay = TaskbarProgressOverlay() if os.name == "nt" else None

        self.root.title("BackMeUpScotty // Retro Style Turbo Backup System")
        # The computer-icon theme selector needs more horizontal room than the
        # original text-only controls.
        self.root.geometry("1120x1030")
        self.root.minsize(1040, 900)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_window)

        # Build UI shell
        self._build_ui()
        self.apply_theme(self.config.theme)

        # Initialize System Tray Icon
        init_rgba = create_tray_icon_rgba(self.config.theme, progress=None)
        self.tray = SystemTrayIcon(
            initial_rgba=init_rgba,
            tooltip="BackMeUpScotty - Ready (Right-click for Backup & Schedule)",
            on_show_window=lambda: self.root.after(0, self.show_window),
            on_edit_schedule=lambda: self.root.after(0, self.open_schedule_dialog),
            on_run_full=lambda: self.root.after(0, lambda: self.start_backup("full")),
            on_run_incremental=lambda: self.root.after(0, lambda: self.start_backup("incremental")),
            on_change_theme=lambda t: self.root.after(0, lambda: self.apply_theme(t)),
            on_exit=lambda: self.root.after(0, self.exit_application),
        )

        # Initialize Scheduler
        self.scheduler = BackupScheduler(
            get_config=lambda: self.config,
            trigger_backup=lambda mode: self.root.after(0, lambda: self._run_scheduled_backup(mode)),
        )

        if start_minimized:
            self.root.withdraw()
        else:
            self.root.state("zoomed")

        # Start 60ms retro CRT / tape border animation & telemetry loop
        self._tick_animation()

    def _get_hwnd(self) -> int:
        try:
            frame_id = self.root.wm_frame()
            if frame_id and frame_id != "0x0":
                return int(frame_id, 16)
            return self.root.winfo_id()
        except Exception:
            return 0

    def _build_ui(self) -> None:
        # Outer Canvas for authentic ZX Spectrum / C64 animated loading border stripes!
        self.border_canvas = tk.Canvas(self.root, highlightthickness=0, bd=0)
        self.border_canvas.pack(fill=tk.BOTH, expand=True)

        # Main CRT Screen Container placed inside the border
        self.screen_frame = tk.Frame(self.border_canvas, bd=0, highlightthickness=2)
        self.screen_window_id = self.border_canvas.create_window(
            24, 24, anchor="nw", window=self.screen_frame
        )
        self.border_canvas.bind("<Configure>", self._on_border_resize)

        # Top Header Bar: System Boot Banner + Theme Switcher
        self.top_bar = tk.Frame(self.screen_frame)
        self.top_bar.pack(fill=tk.X, padx=14, pady=(10, 6))

        self.banner_label = tk.Label(self.top_bar, text="", justify=tk.LEFT, anchor="w")
        self.banner_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.theme_bar = tk.Frame(self.top_bar)
        self.theme_bar.pack(side=tk.RIGHT)

        self.theme_lbl = tk.Label(self.theme_bar, text="SYSTEM ROM:")
        self.theme_lbl.pack(side=tk.LEFT, padx=(0, 6))

        self.theme_buttons: dict[str, tk.Button] = {}
        # Keep PhotoImage references alive: each selector shows the computer's
        # pixel-art badge as well as its text label.
        self.theme_selector_icons: dict[str, ImageTk.PhotoImage] = {}
        selector_art = {
            "ZX Spectrum": "8bitZXSpectrum.png",
            "Commodore 64": "8bitC64.png",
        }
        for t_name in ("ZX Spectrum", "Commodore 64"):
            try:
                asset_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "assets",
                    selector_art[t_name],
                )
                with Image.open(asset_path) as image:
                    icon_image = image.convert("RGBA")
                    content_bounds = icon_image.getchannel("A").getbbox()
                    if content_bounds is not None:
                        icon_image = icon_image.crop(content_bounds)
                    icon_image.thumbnail((52, 38), Image.Resampling.NEAREST)
            except (OSError, ValueError):
                # Keep the selector usable if an optional art asset is absent.
                icon_rgba = create_tray_icon_rgba(t_name, progress=None, size=32)
                icon_image = Image.frombytes("RGBA", (32, 32), icon_rgba)
            self.theme_selector_icons[t_name] = ImageTk.PhotoImage(icon_image)
            btn = tk.Button(
                self.theme_bar,
                text=t_name.upper(),
                image=self.theme_selector_icons[t_name],
                compound=tk.LEFT,
                command=lambda n=t_name: self.apply_theme(n),
                relief=tk.FLAT,
                padx=5,
                pady=2,
                cursor="hand2",
            )
            btn.pack(side=tk.LEFT, padx=3)
            self.theme_buttons[t_name] = btn

        # Retro colour divider canvas
        self.divider_canvas = tk.Canvas(self.screen_frame, height=8, highlightthickness=0, bd=0)
        self.divider_canvas.pack(fill=tk.X, padx=14, pady=(0, 8))

        # Middle Section: Left (Source Folders & Target) + Right (Backup Options & Schedule)
        self.mid_frame = tk.Frame(self.screen_frame)
        self.mid_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)
        self.mid_frame.columnconfigure(0, weight=3)
        self.mid_frame.columnconfigure(1, weight=2)
        self.mid_frame.rowconfigure(0, weight=1)

        # --- LEFT PANEL: Source Folders & Destination ---
        self.left_panel = tk.Frame(self.mid_frame, padx=10, pady=8, highlightthickness=1)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.src_header = tk.Label(
            self.left_panel, text="10 PEEK SOURCE FOLDERS TO BACK UP", anchor="w"
        )
        self.src_header.pack(fill=tk.X, pady=(0, 4))

        # Keep the source list compact; the transfer monitor gets the extra room.
        list_container = tk.Frame(self.left_panel)
        list_container.pack(fill=tk.X)

        self.src_listbox = tk.Listbox(
            list_container,
            selectmode=tk.EXTENDED,
            relief=tk.FLAT,
            highlightthickness=1,
            activestyle="none",
            height=16, # height of the source folder listbox in lines
        )
        self.src_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.src_scroll = tk.Scrollbar(list_container, command=self.src_listbox.yview)
        self.src_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.src_listbox.config(yscrollcommand=self.src_scroll.set)

        for folder in self.config.source_folders:
            self.src_listbox.insert(tk.END, folder)

        src_btn_row = tk.Frame(self.left_panel)
        src_btn_row.pack(fill=tk.X, pady=(6, 10))

        self.btn_add_src = tk.Button(
            src_btn_row,
            text="+ ADD FOLDER",
            command=self._add_source_folder,
            relief=tk.FLAT,
            padx=10,
            pady=3,
            cursor="hand2",
        )
        self.btn_add_src.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_rem_src = tk.Button(
            src_btn_row,
            text="- REMOVE SELECTED",
            command=self._remove_selected_sources,
            relief=tk.FLAT,
            padx=10,
            pady=3,
            cursor="hand2",
        )
        self.btn_rem_src.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_clr_src = tk.Button(
            src_btn_row,
            text="CLEAR",
            command=self._clear_sources,
            relief=tk.FLAT,
            padx=10,
            pady=3,
            cursor="hand2",
        )
        self.btn_clr_src.pack(side=tk.LEFT)

        # Destination Folder
        self.dst_header = tk.Label(
            self.left_panel, text="20 PEEK DESTINATION ARCHIVE FOLDER", anchor="w"
        )
        self.dst_header.pack(fill=tk.X, pady=(2, 4))

        dst_row = tk.Frame(self.left_panel)
        dst_row.pack(fill=tk.X, pady=(0, 4))

        self.dst_var = tk.StringVar(value=self.config.destination_folder)
        self.dst_entry = tk.Entry(
            dst_row,
            textvariable=self.dst_var,
            relief=tk.FLAT,
            highlightthickness=1,
        )
        self.dst_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6), ipady=4)
        self.dst_var.trace_add("write", lambda *_: self._save_paths_from_ui())

        self.btn_browse_dst = tk.Button(
            dst_row,
            text="BROWSE...",
            command=self._browse_destination,
            relief=tk.FLAT,
            padx=10,
            pady=3,
            cursor="hand2",
        )
        self.btn_browse_dst.pack(side=tk.RIGHT)

        # --- RIGHT PANEL: Mode, Incremental Criteria, Schedule, Actions ---
        self.right_panel = tk.Frame(self.mid_frame, padx=10, pady=8, highlightthickness=1)
        self.right_panel.grid(row=0, column=1, sticky="nsew")

        self.mode_header = tk.Label(
            self.right_panel, text="30 POKE TRANSFER ENGINE & DELTA", anchor="w"
        )
        self.mode_header.pack(fill=tk.X, pady=(0, 4))

        self.backup_mode_var = tk.StringVar(value=self.config.backup_mode)
        self.rb_inc = tk.Radiobutton(
            self.right_panel,
            text="INCREMENTAL BACKUP (FAST DELTA)",
            variable=self.backup_mode_var,
            value="incremental",
            command=self._on_options_changed,
            anchor="w",
        )
        self.rb_inc.pack(fill=tk.X)

        self.rb_full = tk.Radiobutton(
            self.right_panel,
            text="FULL BACKUP (OVERWRITE ALL)",
            variable=self.backup_mode_var,
            value="full",
            command=self._on_options_changed,
            anchor="w",
        )
        self.rb_full.pack(fill=tk.X, pady=(0, 6))

        self.crit_header = tk.Label(
            self.right_panel, text="40 REM INCREMENTAL DETECT BY:", anchor="w"
        )
        self.crit_header.pack(fill=tk.X, pady=(2, 2))

        self.criteria_var = tk.StringVar(value=self.config.compare_criteria)
        self.rb_crit_both = tk.Radiobutton(
            self.right_panel,
            text="Size OR Timestamp Changed (Both)",
            variable=self.criteria_var,
            value="both",
            command=self._on_options_changed,
            anchor="w",
        )
        self.rb_crit_both.pack(fill=tk.X)

        self.rb_crit_size = tk.Radiobutton(
            self.right_panel,
            text="File Size Changed Only",
            variable=self.criteria_var,
            value="size",
            command=self._on_options_changed,
            anchor="w",
        )
        self.rb_crit_size.pack(fill=tk.X)

        self.rb_crit_time = tk.Radiobutton(
            self.right_panel,
            text="Timestamp (Modified Time) Only",
            variable=self.criteria_var,
            value="timestamp",
            command=self._on_options_changed,
            anchor="w",
        )
        self.rb_crit_time.pack(fill=tk.X, pady=(0, 8))

        # Schedule summary + Edit button
        self.sched_box = tk.Frame(self.right_panel, padx=8, pady=6, highlightthickness=1)
        self.sched_box.pack(fill=tk.X, pady=(2, 8))

        self.sched_status_lbl = tk.Label(
            self.sched_box, text="AUTO SCHEDULE: OFF", anchor="w"
        )
        self.sched_status_lbl.pack(fill=tk.X)

        self.btn_sched = tk.Button(
            self.sched_box,
            text="EDIT SCHEDULE...",
            command=self.open_schedule_dialog,
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
        )
        self.btn_sched.pack(anchor="e", pady=(4, 0))

        # Action Launch Buttons
        act_frame = tk.Frame(self.right_panel)
        act_frame.pack(fill=tk.X, pady=(4, 0))

        self.btn_run_inc = tk.Button(
            act_frame,
            text="▶ RUN INCREMENTAL",
            command=lambda: self.start_backup("incremental"),
            relief=tk.FLAT,
            pady=6,
            cursor="hand2",
        )
        self.btn_run_inc.pack(fill=tk.X, pady=(0, 5))

        sub_act = tk.Frame(act_frame)
        sub_act.pack(fill=tk.X)

        self.btn_run_full = tk.Button(
            sub_act,
            text="▶▶ RUN FULL",
            command=lambda: self.start_backup("full"),
            relief=tk.FLAT,
            pady=5,
            cursor="hand2",
        )
        self.btn_run_full.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self.btn_stop = tk.Button(
            sub_act,
            text="■ BREAK / STOP",
            command=self.stop_backup,
            relief=tk.FLAT,
            pady=5,
            cursor="hand2",
        )
        self.btn_stop.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        self.btn_hide_tray = tk.Button(
            act_frame,
            text="▼ MINIMIZE TO TASKBAR TRAY",
            command=self.hide_to_tray,
            relief=tk.FLAT,
            pady=4,
            cursor="hand2",
        )
        self.btn_hide_tray.pack(fill=tk.X, pady=(6, 0))

        # --- BOTTOM SECTION: Animated Retro Tape Deck / Progress Visualization & Telemetry ---
        self.deck_frame = tk.Frame(self.screen_frame, padx=10, pady=8, highlightthickness=1)
        self.deck_frame.pack(fill=tk.X, padx=14, pady=(6, 12))

        self.deck_header = tk.Label(
            self.deck_frame,
            text="50 RUN TURBO TAPE / DMA TRANSFER MONITOR",
            anchor="w",
        )
        self.deck_header.pack(fill=tk.X, pady=(0, 4))

        # Animated cassette-to-cassette transfer, progress bar, and telemetry.
        self.progress_canvas = tk.Canvas(
            self.deck_frame, height=270, highlightthickness=1, bd=0
        )
        self.progress_canvas.pack(fill=tk.X, pady=(0, 6))
        # The first draw can happen before Tk knows the final canvas width.
        # Redraw when geometry settles and on later monitor resizes.
        self.progress_canvas.bind("<Configure>", self._on_transfer_monitor_resize)

        # Status & Log Ticker
        self.status_row = tk.Frame(self.deck_frame)
        self.status_row.pack(fill=tk.X)

        self.prompt_lbl = tk.Label(self.status_row, text="0 OK, 0:1", anchor="w")
        self.prompt_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.tray_hint_lbl = tk.Label(
            self.status_row,
            text="[TRAY ICON ACTIVE: RIGHT-CLICK FOR QUICK MENU]",
            anchor="e",
        )
        self.tray_hint_lbl.pack(side=tk.RIGHT)

    def _on_border_resize(self, event) -> None:
        pad = 22
        w = max(200, event.width - pad * 2)
        h = max(200, event.height - pad * 2)
        self.border_canvas.coords(self.screen_window_id, pad, pad)
        self.border_canvas.itemconfigure(self.screen_window_id, width=w, height=h)
        self._draw_border_and_divider()

    def _on_transfer_monitor_resize(self, _event=None) -> None:
        """Keep cassette positions and data stream aligned to the actual canvas width."""
        self.root.after_idle(self._draw_progress_deck)

    def _apply_application_icon(self, window: tk.Tk | tk.Toplevel) -> None:
        """Apply the packaged Windows icon to the main window and every popup."""
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ico_file = os.path.join(root_dir, "assets", "app_icon.ico")
        master_png = os.path.join(root_dir, "assets", "app_icon_master.png")
        if os.name == "nt" and os.path.exists(ico_file):
            try:
                window.iconbitmap(default=ico_file)
            except tk.TclError:
                pass
        if not hasattr(self, "_tk_icon_256") and os.path.exists(master_png):
            try:
                with Image.open(master_png) as image:
                    pil_master = image.convert("RGBA")
                    self._tk_icon_256 = ImageTk.PhotoImage(
                        pil_master.resize((256, 256), Image.Resampling.LANCZOS)
                    )
                    self._tk_icon_64 = ImageTk.PhotoImage(
                        pil_master.resize((64, 64), Image.Resampling.LANCZOS)
                    )
                    self._tk_icon_32 = ImageTk.PhotoImage(
                        pil_master.resize((32, 32), Image.Resampling.LANCZOS)
                    )
            except (OSError, ValueError, tk.TclError):
                return
        if hasattr(self, "_tk_icon_256"):
            try:
                window.iconphoto(True, self._tk_icon_256, self._tk_icon_64, self._tk_icon_32)
            except tk.TclError:
                pass
        self._set_windows_taskbar_icon(window, ico_file)

    def _set_windows_taskbar_icon(self, window: tk.Tk | tk.Toplevel, ico_file: str) -> None:
        """Set both native title-bar icon sizes so Windows does not fall back to Python's icon."""
        if os.name != "nt" or not os.path.isfile(ico_file):
            return
        try:
            window.update_idletasks()
            frame = window.wm_frame()
            hwnd = int(frame, 16) if frame and frame != "0x0" else window.winfo_id()
            if hwnd in self._native_icon_window_ids:
                return
            user32 = ctypes.windll.user32
            load_image = user32.LoadImageW
            load_image.argtypes = [
                ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint,
                ctypes.c_int, ctypes.c_int, ctypes.c_uint,
            ]
            load_image.restype = ctypes.c_void_p
            send_message = user32.SendMessageW
            send_message.argtypes = [
                ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t,
            ]
            send_message.restype = ctypes.c_ssize_t
            image_icon, load_from_file = 1, 0x0010
            wm_seticon, icon_small, icon_big = 0x0080, 0, 1
            for icon_kind, width, height in ((icon_small, 16, 16), (icon_big, 32, 32)):
                hicon = load_image(None, ico_file, image_icon, width, height, load_from_file)
                if hicon:
                    self._window_icon_handles.append(int(hicon))
                    send_message(ctypes.c_void_p(hwnd), wm_seticon, icon_kind, int(hicon))
            self._native_icon_window_ids.add(hwnd)
        except (AttributeError, OSError, ValueError, tk.TclError):
            pass

    def apply_theme(self, theme_name: str) -> None:
        if theme_name not in THEMES:
            theme_name = "ZX Spectrum"
        self.config.theme = theme_name
        self.config.save()
        t = THEMES[theme_name]

        font_fam = t["font_family"]
        f_banner = (font_fam, 11, "bold")
        f_hdr = (font_fam, 10, "bold")
        f_norm = (font_fam, 9, "bold")
        f_small = (font_fam, 8, "bold")

        # Use the same packaged icon in the title bar and Windows taskbar.
        self._apply_application_icon(self.root)

        rgba = create_tray_icon_rgba(
            theme_name,
            progress=self.latest_stats.progress_fraction if self._backup_is_active() else None,
            pulse=self._anim_tick,
        )
        if hasattr(self, "tray") and self.tray:
            self.tray.update_icon_and_tip(
                rgba, f"BackMeUpScotty [{t['name']}]"
            )

        self.screen_frame.configure(
            bg=t["paper"], highlightbackground=t["accent"], highlightcolor=t["accent"]
        )
        self.top_bar.configure(bg=t["paper"])
        self.banner_label.configure(
            text=f"{t['boot_banner']}",
            font=f_banner,
            bg=t["paper"],
            fg=t["ink"],
        )
        self.theme_bar.configure(bg=t["paper"])
        self.theme_lbl.configure(font=f_small, bg=t["paper"], fg=t["ink"])

        for name, btn in self.theme_buttons.items():
            is_sel = name == theme_name
            btn.configure(
                font=f_small,
                bg=t["button_active_bg"] if is_sel else t["panel_bg"],
                fg=t["button_active_fg"] if is_sel else t["panel_fg"],
                activebackground=t["button_active_bg"],
                activeforeground=t["button_active_fg"],
            )

        self.mid_frame.configure(bg=t["paper"])
        for panel in (self.left_panel, self.right_panel, self.deck_frame):
            panel.configure(
                bg=t["paper"],
                highlightbackground=t["accent"],
                highlightcolor=t["accent"],
            )

        for hdr in (self.src_header, self.dst_header, self.mode_header, self.crit_header, self.deck_header):
            hdr.configure(font=f_hdr, bg=t["panel_bg"], fg=t["panel_fg"], padx=6, pady=3)

        self.src_listbox.configure(
            font=f_norm,
            bg=t["input_bg"],
            fg=t["input_fg"],
            selectbackground=t["accent"],
            selectforeground=t["accent_bright"],
            highlightbackground=t["accent"],
        )
        self.dst_entry.configure(
            font=f_norm,
            bg=t["input_bg"],
            fg=t["input_fg"],
            insertbackground=t["input_fg"],
            highlightbackground=t["accent"],
        )

        for frame_w in (
            self.left_panel.winfo_children()
            + self.right_panel.winfo_children()
            + [self.status_row]
        ):
            if isinstance(frame_w, tk.Frame) and frame_w is not self.sched_box:
                frame_w.configure(bg=t["paper"])

        for rb in (self.rb_inc, self.rb_full, self.rb_crit_both, self.rb_crit_size, self.rb_crit_time):
            rb.configure(
                font=f_norm,
                bg=t["paper"],
                fg=t["ink"],
                selectcolor=t["input_bg"],
                activebackground=t["paper"],
                activeforeground=t["accent"],
            )

        self.sched_box.configure(
            bg=t["panel_bg"], highlightbackground=t["accent"]
        )
        self.sched_status_lbl.configure(
            font=f_norm, bg=t["panel_bg"], fg=t["accent_bright"]
        )
        self.btn_sched.configure(
            font=f_small,
            bg=t["button_bg"],
            fg=t["button_fg"],
            activebackground=t["button_active_bg"],
            activeforeground=t["button_active_fg"],
        )

        for btn in (self.btn_add_src, self.btn_rem_src, self.btn_clr_src, self.btn_browse_dst):
            btn.configure(
                font=f_small,
                bg=t["button_bg"],
                fg=t["button_fg"],
                activebackground=t["button_active_bg"],
                activeforeground=t["button_active_fg"],
            )

        self.btn_run_inc.configure(
            font=f_hdr,
            bg=t["success"],
            fg="#000000",
            activebackground=t["button_active_bg"],
            activeforeground=t["button_active_fg"],
        )
        self.btn_run_full.configure(
            font=f_norm,
            bg=t["button_bg"],
            fg=t["button_fg"],
            activebackground=t["button_active_bg"],
            activeforeground=t["button_active_fg"],
        )
        self.btn_stop.configure(
            font=f_norm,
            bg=t["danger"],
            fg="#FFFFFF",
            activebackground="#FF5555",
            activeforeground="#FFFFFF",
        )
        self.btn_hide_tray.configure(
            font=f_small,
            bg=t["panel_bg"],
            fg=t["panel_fg"],
            activebackground=t["button_active_bg"],
            activeforeground=t["button_active_fg"],
        )

        self.progress_canvas.configure(
            # Match the main interface background behind the surrounding boxes.
            bg=t["paper"], highlightbackground=t["accent"]
        )
        self.prompt_lbl.configure(
            font=f_hdr, bg=t["paper"], fg=t["ink"], text=t["ready_prompt"]
        )
        self.tray_hint_lbl.configure(
            font=f_small, bg=t["paper"], fg=t["accent"]
        )

        self._draw_border_and_divider()
        self._draw_progress_deck()

    def _backup_is_active(self) -> bool:
        """Includes the short handoff between the UI and worker thread."""
        return self._backup_ui_active or self.engine.is_running

    def _get_cassette_tape_image(self) -> ImageTk.PhotoImage | None:
        """Return a cropped, pixel-crisp thumbnail from the supplied cassette art."""
        if self._cassette_tape_image is not None:
            return self._cassette_tape_image
        try:
            asset_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "assets",
                "8bitCassette.png",
            )
            with Image.open(asset_path) as image:
                cassette = image.convert("RGBA")
                # Trim transparent padding without assuming a fixed image size.
                content_bounds = cassette.getchannel("A").getbbox()
                if content_bounds is not None:
                    cassette = cassette.crop(content_bounds)
                cassette = cassette.resize((180, 138), Image.Resampling.NEAREST)
                self._cassette_tape_image = ImageTk.PhotoImage(cassette)
        except (OSError, ValueError):
            return None
        return self._cassette_tape_image

    def _get_success_popup_image(self) -> ImageTk.PhotoImage | None:
        """Load the user-supplied completion artwork at popup resolution."""
        if self._success_popup_image is not None:
            return self._success_popup_image
        try:
            asset_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "assets",
                "SuccessPic.jpg",
            )
            with Image.open(asset_path) as image:
                success_image = image.convert("RGBA").resize(
                    (800, 450), Image.Resampling.NEAREST
                )
                self._success_popup_image = ImageTk.PhotoImage(success_image)
        except (OSError, ValueError):
            return None
        return self._success_popup_image

    def _draw_border_and_divider(self) -> None:
        t = THEMES[self.config.theme]
        self.border_canvas.delete("border_stripes")
        w = self.border_canvas.winfo_width()
        h = self.border_canvas.winfo_height()

        if self._backup_is_active():
            # Draw authentic 8-bit tape/raster loading bars along the outer border!
            phase = self.latest_stats.phase
            palette = t["border_active_1"] if phase == "SCANNING" else t["border_active_2"]
            stripe_h = 8
            idx = self._anim_tick
            for y in range(0, max(h, 700), stripe_h):
                color = palette[(idx + (y // stripe_h)) % len(palette)]
                self.border_canvas.create_rectangle(
                    0, y, max(w, 950), y + stripe_h, fill=color, outline="", tags="border_stripes"
                )
            self.border_canvas.tag_lower("border_stripes")
        else:
            self.border_canvas.configure(bg=t["border_idle"])

        # Draw rainbow/teletext divider strip
        self.divider_canvas.delete("all")
        dw = max(self.divider_canvas.winfo_width(), 860)
        rainbow = t["rainbow"]
        seg_w = dw / len(rainbow)
        for i, col in enumerate(rainbow):
            self.divider_canvas.create_rectangle(
                i * seg_w, 0, (i + 1) * seg_w, 8, fill=col, outline=""
            )

    def _draw_progress_deck(self) -> None:
        t = THEMES[self.config.theme]
        c = self.progress_canvas
        c.delete("all")
        w = max(c.winfo_width(), 840)
        h = max(c.winfo_height(), 270)
        font_fam = t["font_family"]

        stats = self.latest_stats
        running = self._backup_is_active()
        pct = stats.progress_fraction if (running or stats.phase == "DONE") else 0.0
        pct_int = int(round(pct * 100))

        # The supplied 8-bit cassette artwork anchors both ends of the transfer.
        cassette_image = self._get_cassette_tape_image()
        cassette_w, cassette_h, cassette_y = 180, 138, 62
        source_x, target_x = 14, w - cassette_w - 14
        for x, label in ((source_x, "SOURCE TAPE"), (target_x, "BACKUP TAPE")):
            c.create_text(x + cassette_w / 2, 55, text=label,
                          font=(font_fam, 8, "bold"), fill=t["highlight"])
            if cassette_image is not None:
                c.create_image(x + cassette_w / 2, cassette_y + cassette_h / 2,
                               image=cassette_image)
            else:
                c.create_rectangle(x, cassette_y, x + cassette_w, cassette_y + cassette_h,
                                   fill="#080808", outline=t["accent_bright"], width=3)

        stream_x1, stream_x2, stream_y = 215, w - 215, 127
        c.create_line(stream_x1, stream_y, stream_x2, stream_y, fill=t["accent"], dash=(4, 5))
        c.create_text((stream_x1 + stream_x2) / 2, 69, text="TURBO DATA LINK >>>",
                      font=(font_fam, 8, "bold"), fill=t["highlight"])
        if running:
            stream_width = max(1, stream_x2 - stream_x1)
            for block in range(9):
                block_x = stream_x1 + ((self._anim_tick * 12 + block * 73) % stream_width)
                block_color = t["accent_bright"] if block % 2 else t["bar_fg"]
                c.create_rectangle(block_x, stream_y - 5, block_x + 12, stream_y + 5,
                                   fill=block_color, outline="")

        # Center Progress Track (between the two tape reels)
        bar_x1 = 215
        bar_x2 = w - 215
        bar_y1 = 12
        bar_y2 = 42
        bar_w = max(10, bar_x2 - bar_x1)

        c.create_rectangle(
            bar_x1, bar_y1, bar_x2, bar_y2,
            outline=t["accent_bright"], width=2, fill="#050505"
        )

        # Segmented 8-bit character blocks inside the progress bar
        num_blocks = 32
        block_gap = 3
        block_w = (bar_w - 8 - (num_blocks - 1) * block_gap) / num_blocks
        filled_blocks = int(round(pct * num_blocks))

        for b in range(num_blocks):
            bx1 = bar_x1 + 4 + b * (block_w + block_gap)
            bx2 = bx1 + block_w
            if b < filled_blocks:
                # Chasing highlight pulse when actively copying
                if running and (b == filled_blocks - 1 or (b + self._anim_tick) % 8 == 0):
                    b_col = t["accent_bright"]
                else:
                    b_col = t["bar_fg"] if (b % 2 == 0) else t["bar_alt"]
                c.create_rectangle(bx1, bar_y1 + 4, bx2, bar_y2 - 4, fill=b_col, outline="")
            else:
                c.create_rectangle(bx1, bar_y1 + 4, bx2, bar_y2 - 4, fill="#161622", outline="")

        # Percentage badge centered over progress bar
        status_tag = stats.phase if (running or stats.phase != "IDLE") else "READY"
        badge_text = f"{status_tag} {pct_int:3d}%"
        badge_text_id = c.create_text(
            (bar_x1 + bar_x2) / 2, (bar_y1 + bar_y2) / 2,
            text=badge_text,
            font=(font_fam, 11, "bold"),
            fill="#FFFFFF",
        )
        text_bounds = c.bbox(badge_text_id)
        if text_bounds is not None:
            badge_box = c.create_rectangle(
                max(bar_x1 + 2, text_bounds[0] - 8), bar_y1 + 5,
                min(bar_x2 - 2, text_bounds[2] + 8), bar_y2 - 5,
                fill="#000000", outline=t["accent"],
            )
            c.tag_lower(badge_box, badge_text_id)

        # Telemetry readout lines below the bar
        copied_str = f"COPIED: {stats.files_copied}/{stats.files_to_copy} ({format_bytes(stats.bytes_copied)} / {format_bytes(stats.bytes_to_copy)})"
        skipped_str = f"SKIPPED (UNCHANGED): {stats.files_skipped} ({format_bytes(stats.bytes_skipped)})"
        speed_str = f"SPEED: {stats.speed_mbps:.1f} MB/s | TIME: {stats.elapsed:.1f}s | ERR: {stats.errors}"

        c.create_text(
            bar_x1, 202,
            anchor="w",
            text=copied_str,
            font=(font_fam, 9, "bold"),
            fill=t["highlight"],
        )
        c.create_text(
            bar_x1, 218,
            anchor="w",
            text=skipped_str,
            font=(font_fam, 9, "bold"),
            fill=t["highlight"],
        )
        c.create_text(
            bar_x2, 218,
            anchor="e",
            text=speed_str,
            font=(font_fam, 9, "bold"),
            fill=t["highlight"],
        )

        # Current file / program byte stream ticker at bottom of deck
        cur_file = stats.current_file or "Waiting for command..."
        if len(cur_file) > 85:
            cur_file = "..." + cur_file[-82:]
        last_log = stats.recent_logs[-1] if stats.recent_logs else "Program: BACKMEUPSCOTTY  Bytes: TURBO-DMA"
        if len(last_log) > 90:
            last_log = last_log[:87] + "..."

        c.create_text(
            16, 239,
            anchor="w",
            text=f"FILE: {cur_file}",
            font=(font_fam, 9, "bold"),
            fill="#FFFFFF",
        )
        c.create_text(
            16, 258,
            anchor="w",
            text=f"LOG : {last_log}",
            font=(font_fam, 8, "bold"),
            fill=t["success"],
        )

    def _tick_animation(self) -> None:
        self._anim_tick = (self._anim_tick + 1) % 10000
        t = THEMES[self.config.theme]

        # Update schedule countdown display
        if hasattr(self, "scheduler"):
            self.sched_status_lbl.configure(
                text=f"AUTO SCHEDULE: {self.scheduler.next_run_display}"
            )

        running = self._backup_is_active()
        stats = self.latest_stats

        if running:
            self._draw_border_and_divider()
            self._draw_progress_deck()

            pct_int = int(round(stats.progress_fraction * 100))
            self.prompt_lbl.configure(
                text=f"LOADING... {pct_int}% ({stats.files_copied}/{stats.files_to_copy} files @ {stats.speed_mbps:.1f} MB/s)"
            )

            # Update Windows Taskbar button progress bar + System Tray progress icon
            hwnd = self._get_hwnd()
            if self.taskbar_overlay and hwnd:
                if stats.phase == "SCANNING":
                    self.taskbar_overlay.set_state(hwnd, TaskbarProgressOverlay.TBPF_INDETERMINATE)
                else:
                    self.taskbar_overlay.set_state(hwnd, TaskbarProgressOverlay.TBPF_NORMAL)
                    self.taskbar_overlay.set_value(hwnd, int(stats.progress_fraction * 1000), 1000)

            now = time.perf_counter()
            if now - self._last_tray_update >= 0.20:
                self._last_tray_update = now
                rgba = create_tray_icon_rgba(
                    self.config.theme, progress=stats.progress_fraction, pulse=self._anim_tick
                )
                tip = f"BackMeUpScotty: {stats.phase} {pct_int}% ({stats.speed_mbps:.1f} MB/s)"
                self.tray.update_icon_and_tip(rgba, tip)
        else:
            # Cursor blink in idle prompt
            cursor_char = "█" if (self._anim_tick // 6) % 2 == 0 else " "
            if stats.phase == "DONE":
                self.prompt_lbl.configure(
                    text=f"{t['ready_prompt']} — DONE: {stats.files_copied} copied, {stats.files_skipped} skipped in {stats.elapsed:.2f}s {cursor_char}"
                )
            elif stats.phase == "CANCELLED":
                self.prompt_lbl.configure(text=f"BREAK - CONT REPEATS {cursor_char}")
            elif stats.phase == "ERROR":
                self.prompt_lbl.configure(text=f"TAPE LOADING ERROR ({stats.errors} errors) {cursor_char}")
            else:
                self.prompt_lbl.configure(text=f"{t['ready_prompt']} {cursor_char}")

        self.root.after(70, self._tick_animation)

    # --- Folder & Option Handlers ---

    def _add_source_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select Source Folder to Back Up")
        if folder:
            norm = os.path.normpath(folder)
            existing = list(self.src_listbox.get(0, tk.END))
            if norm not in existing:
                self.src_listbox.insert(tk.END, norm)
                self._save_paths_from_ui()

    def _remove_selected_sources(self) -> None:
        sel = list(self.src_listbox.curselection())
        for idx in reversed(sel):
            self.src_listbox.delete(idx)
        self._save_paths_from_ui()

    def _clear_sources(self) -> None:
        self.src_listbox.delete(0, tk.END)
        self._save_paths_from_ui()

    def _browse_destination(self) -> None:
        folder = filedialog.askdirectory(title="Select Destination Backup Folder")
        if folder:
            self.dst_var.set(os.path.normpath(folder))
            self._save_paths_from_ui()

    def _save_paths_from_ui(self) -> None:
        self.config.source_folders = list(self.src_listbox.get(0, tk.END))
        self.config.destination_folder = self.dst_var.get().strip()
        self.config.save()

    def _on_options_changed(self) -> None:
        self.config.backup_mode = self.backup_mode_var.get()
        self.config.compare_criteria = self.criteria_var.get()
        self.config.save()

    def open_schedule_dialog(self) -> None:
        self.show_window()
        if self._schedule_dialog and self._schedule_dialog.winfo_exists():
            self._schedule_dialog.lift()
            return
        t = THEMES[self.config.theme]
        self._schedule_dialog = ScheduleDialog(
            self,
            self.config,
            t,
            on_save=lambda: self.scheduler.reset_timer(),
        )

    # --- Backup Execution ---

    def _run_scheduled_backup(self, mode: str) -> None:
        if self._backup_is_active():
            return
        if not self.config.source_folders or not self.config.destination_folder:
            return
        self.start_backup(mode, triggered_by_schedule=True)

    def start_backup(self, mode: str | None = None, triggered_by_schedule: bool = False) -> None:
        if self._backup_is_active():
            if not triggered_by_schedule:
                messagebox.showinfo("Backup Busy", "A backup is already running!")
            return

        self._save_paths_from_ui()
        sources = self.config.source_folders
        dest = self.config.destination_folder

        if not sources:
            if not triggered_by_schedule:
                self.show_window()
                messagebox.showwarning(
                    "No Source Folders",
                    "Please add at least one Source Folder to back up.",
                )
            return

        if not dest:
            if not triggered_by_schedule:
                self.show_window()
                messagebox.showwarning(
                    "No Destination Folder",
                    "Please choose a Destination Folder for the backup.",
                )
            return

        chosen_mode = mode or self.config.backup_mode
        self.backup_mode_var.set(chosen_mode)
        criteria = self.config.compare_criteria
        self._backup_ui_active = True
        self.latest_stats = BackupStats(
            mode=chosen_mode,
            compare_criteria=criteria,
            phase="SCANNING",
            start_time=time.perf_counter(),
        )
        self._draw_border_and_divider()
        self._draw_progress_deck()
        self.prompt_lbl.configure(text="LOADING... PREPARING TURBO TAPE")

        def _on_progress(st: BackupStats) -> None:
            with self._stats_lock:
                self.latest_stats = st

        def _worker() -> None:
            final_stats = self.engine.run_backup(
                source_folders=sources,
                destination_root=dest,
                mode=chosen_mode,
                compare_criteria=criteria,
                on_progress=_on_progress,
            )
            self.root.after(0, lambda: self._on_backup_finished(final_stats, triggered_by_schedule))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_backup_finished(self, stats: BackupStats, triggered_by_schedule: bool) -> None:
        self._backup_ui_active = False
        self.latest_stats = stats
        self._draw_border_and_divider()
        self._draw_progress_deck()

        # Reset taskbar progress bar & tray icon back to idle state
        hwnd = self._get_hwnd()
        if self.taskbar_overlay and hwnd:
            self.taskbar_overlay.set_state(hwnd, TaskbarProgressOverlay.TBPF_NOPROGRESS)

        rgba = create_tray_icon_rgba(self.config.theme, progress=None)
        summary = (
            f"BackMeUpScotty - Last {stats.mode.title()}: "
            f"{stats.files_copied} copied, {stats.files_skipped} skipped ({stats.elapsed:.1f}s)"
        )
        self.tray.update_icon_and_tip(rgba, summary)

        if stats.phase == "DONE":
            self._show_backup_complete_sprite(stats)

        if triggered_by_schedule or not self.root.winfo_viewable():
            self.tray.show_balloon(
                f"Backup Complete ({stats.mode.upper()})",
                f"Copied {stats.files_copied} files ({format_bytes(stats.bytes_copied)}), "
                f"skipped {stats.files_skipped} unchanged in {stats.elapsed:.2f}s.",
            )

    def stop_backup(self) -> None:
        if self._backup_is_active():
            self.engine.cancel()

    def _show_backup_complete_sprite(self, stats: BackupStats) -> None:
        """Show a small, celebratory pixel-art completion card over the app."""
        if self._completion_popup and self._completion_popup.winfo_exists():
            self._completion_popup.destroy()

        t = THEMES[self.config.theme]
        popup = tk.Toplevel(self.root)
        self._completion_popup = popup
        self._apply_application_icon(popup)
        popup.title("MISSION COMPLETE!")
        popup.transient(self.root)
        popup.resizable(False, False)
        popup.configure(bg=t["paper"])
        popup.attributes("-topmost", True)
        popup.protocol("WM_DELETE_WINDOW", popup.destroy)

        canvas = tk.Canvas(popup, width=860, height=540, bg="#090914", highlightthickness=3,
                           highlightbackground=t["accent_bright"], bd=0)
        canvas.pack(padx=10, pady=10)

        success_image = self._get_success_popup_image()
        if success_image is not None:
            canvas.create_image(430, 230, image=success_image)
        else:
            canvas.create_text(430, 230, text="*** BACKUP COMPLETE! ***", fill=t["accent_bright"],
                               font=(t["font_family"], 15, "bold"))
        canvas.create_text(430, 485,
                           text=f"{stats.files_copied} FILES SAVED  |  {stats.files_skipped} UNCHANGED  |  {stats.elapsed:.1f} SEC",
                           fill="#FFFFFF", font=(t["font_family"], 9, "bold"))
        canvas.create_text(430, 515, text="PRESS ANY KEY / CLICK TO CONTINUE", fill=t["warning"],
                           font=(t["font_family"], 9, "bold"))

        center_popup(popup)

        def dismiss(_event=None) -> None:
            if popup.winfo_exists():
                popup.destroy()

        popup.bind("<Key>", dismiss)
        canvas.bind("<Button-1>", dismiss)
        popup.grab_set()
        popup.focus_force()
        # Leave enough time to enjoy the graphic, but never make it permanent.
        popup.after(8000, dismiss)

    # --- Window / Tray Management ---

    def hide_to_tray(self) -> None:
        self.root.withdraw()
        self.tray.show_balloon(
            "BackMeUpScotty Running in Taskbar",
            "Right-click the retro tray icon to Edit Schedule, Run Full/Incremental Backup, or Exit.",
        )

    def show_window(self) -> None:
        self.root.deiconify()
        self.root.state("zoomed")
        self.root.lift()
        self.root.focus_force()

    def _on_close_window(self) -> None:
        if self.config.minimize_to_tray_on_close:
            self.hide_to_tray()
        else:
            self.exit_application()

    def exit_application(self) -> None:
        if self.engine.is_running:
            self.engine.cancel()
        if hasattr(self, "scheduler") and self.scheduler:
            self.scheduler.stop()
        if hasattr(self, "tray") and self.tray:
            self.tray.destroy()
        self.root.quit()
        self.root.destroy()
        sys.exit(0)
