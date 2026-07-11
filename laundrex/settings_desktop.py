from pathlib import Path
import os

from .settings import *  # noqa: F403,F401


DESKTOP_DB_PATH = os.getenv("DESKTOP_DB_PATH")
if not DESKTOP_DB_PATH:
    DESKTOP_DB_PATH = str((BASE_DIR / "desktop_app" / "data" / "desktop.sqlite3").resolve())  # type: ignore[name-defined]

Path(DESKTOP_DB_PATH).parent.mkdir(parents=True, exist_ok=True)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DESKTOP_DB_PATH,
    }
}

# Desktop wrapper should always be locally reachable.
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
DEBUG = True

# Keep desktop local-first by default.
SYNC_ENABLED = os.getenv("SYNC_ENABLED", "0") == "1"
SYNC_ENDPOINTS_ENABLED = os.getenv("SYNC_ENDPOINTS_ENABLED", "0") == "1"

