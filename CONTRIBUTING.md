# Contributing to BackMeUpScotty

Thanks for helping improve BackMeUpScotty.

## Before you start

- Open an issue before beginning substantial work so the change can be discussed.
- Keep each pull request focused on one concern.
- Do not commit generated executables, ZIP archives, build output, or local backup settings.

## Development setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-build.txt
```

Run the non-GUI checks with:

```powershell
python -c "import sys; sys.path.insert(0, 'tests'); import test_app; test_app.test_backup_engine(); test_app.test_backup_engine_allows_different_drives()"
```

Run the complete suite from an interactive Windows desktop session because it creates a temporary Tkinter window:

```powershell
python tests\test_app.py
```

## Pull requests

- Describe the user-visible change and how you tested it.
- Update documentation and tests when behavior changes.
- Preserve the existing font-license notices in `assets/fonts/`.
