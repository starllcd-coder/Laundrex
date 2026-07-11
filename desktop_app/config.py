from __future__ import annotations

import os
from pathlib import Path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
SYNC_INTERVAL_SECONDS = int(os.getenv("SYNC_INTERVAL_SECONDS", "120"))
SYNC_ENABLED = os.getenv("SYNC_ENABLED", "0") == "1"
DESKTOP_SETTINGS_MODULE = "laundrex.settings_desktop"
DESKTOP_DB_FILENAME = os.getenv("DESKTOP_DB_FILENAME", "desktop.sqlite3")
DESKTOP_ADMIN_USERNAME = os.getenv("DESKTOP_ADMIN_USERNAME", "laundrex")
DESKTOP_ADMIN_PASSWORD = os.getenv("DESKTOP_ADMIN_PASSWORD", "Kashmir@566")
DESKTOP_ADMIN_EMAIL = os.getenv("DESKTOP_ADMIN_EMAIL", "admin@laundrex.local")


def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__)).resolve()
    for parent in [current, *current.parents]:
        if (parent / "manage.py").exists():
            return parent
    raise FileNotFoundError("manage.py not found. Run from inside the project.")


def desktop_data_dir(project_root: Path) -> Path:
    return project_root / "desktop_app" / "data"


def desktop_db_path(project_root: Path) -> Path:
    return desktop_data_dir(project_root) / DESKTOP_DB_FILENAME
