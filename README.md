# BackMeUpScotty — 8-Bit Turbo Folder Backup

A fast, low-memory folder backup application with switchable **ZX Spectrum 48K** and **Commodore 64 BASIC V2** retro user interfaces.

> **Windows only.** BackMeUpScotty is designed for Windows file-system and
> taskbar APIs.

## Key Features
- **2 Switchable 8-Bit Retro Themes**:
  - **ZX Spectrum 48K**: Iconic Sinclair boot banner, diagonal rainbow slash, and animated red/cyan & blue/yellow cassette loading border stripes during transfers.
  - **Commodore 64 BASIC V2**: Classic light-blue on dark-blue screen (`**** COMMODORE 64 BASIC V2 ****`) with animated raster loading bars.
- **High-Speed Kernel Transfer Engine**:
  - Uses iterative `os.scandir` directory delta scanning (`O(depth)` memory usage) and pre-caches destination directory entries per folder to avoid per-file `stat` overhead.
  - Multi-threaded worker pool (`ThreadPoolExecutor`) invoking native Win32 `CopyFileW` kernel-level DMA transfers with full long-path (`\\?\`) support.
- **Full & Incremental Backups**:
  - Choose between **Full Backup** or **Incremental Backup** detecting changes via:
    - **Size OR Timestamp (Both)**
    - **File Size Only**
    - **Timestamp (Modification Time) Only**
- **Taskbar & System Tray Integration**:
  - Runs quietly in the Windows Notification Area (System Tray) with minimal memory usage.
  - **Right-click the tray icon** at any time to:
    - **Open BackMeUpScotty**
    - **Edit Schedule...** (Interval in minutes or Daily `HH:MM`, Full or Incremental)
    - **Run Full Backup**
    - **Run Incremental Backup**
    - **Switch Retro Theme**
    - **Exit Application**
  - **Dual Live Progress Indicators**:
    - **Tiny Taskbar/Tray Progress**: The 32×32 System Tray icon dynamically animates a mini progress bar and pulsing activity light during backups, and the Windows Taskbar button displays a native `ITaskbarList3` progress overlay.
    - **Full Interface Progress**: When the main window is open, the outer border flashes authentic 8-bit tape loading stripes while the bottom Turbo Tape Deck animates spinning cassette reels, a 32-block progress bar, live MB/s speed, and file logs.

## Requirements

- Windows 10 or later
- Python 3.10 or later (only when running from source or building the executable)
- Tkinter (included with standard Windows Python installers)

## Run from Source

```powershell
uv sync
uv run python main.py
```

On first launch, the app creates `backmeupscotty_config.json` in the project
folder. This file stores local source, destination, and schedule choices and is
intentionally not tracked by Git. Use
`backmeupscotty_config.example.json` as a reference if you need to create one
manually.

## Run the Packaged App

- **Double-click the compiled executable**:
  - `dist\BackMeUpScotty.exe` is a self-contained Windows application. Copy that one file to another Windows PC; Python and `main.py` are not required there. Pass `--minimized` to start directly in the taskbar tray.

## Build a Release Executable

Use PyInstaller through UV's isolated build dependency group:

```powershell
uv run --group build pyinstaller --noconfirm --clean --onefile --windowed --name BackMeUpScotty --icon assets\app_icon.ico --add-data "assets;assets" --add-data "VERSION;." --distpath dist --workpath build main.py
```

The distributable is `dist\BackMeUpScotty.exe`. The build requires Windows.
Application settings on a recipient's PC are saved under
`%APPDATA%\BackMeUpScotty`.

## Test

```powershell
uv run python tests\test_app.py
```

The test suite opens a temporary Tkinter window, so run it from an interactive
Windows desktop session.

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) for
development, test, and pull-request guidance. Report potential security issues
privately as described in [SECURITY.md](SECURITY.md).

Project participants are expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
For general help and issue-reporting guidance, see [SUPPORT.md](SUPPORT.md).

## License

The source code and original project material are licensed under the
[MIT License](LICENSE). Bundled retro fonts are subject to their own license;
see [NOTICE.md](NOTICE.md) and `assets/fonts/LICENSE-Kreative-FreeUse-1.2f.txt`.
