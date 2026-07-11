from __future__ import annotations

import json
import os
import subprocess
import hashlib
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

from desktop_app.config import (
    DESKTOP_ADMIN_EMAIL,
    DESKTOP_ADMIN_PASSWORD,
    DESKTOP_ADMIN_USERNAME,
    DESKTOP_SETTINGS_MODULE,
    desktop_data_dir,
    desktop_db_path,
)


class DjangoServer(QObject):
    started = Signal()
    stopped = Signal()
    output = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._handle_output)
        self._process.finished.connect(self._handle_finished)
        self._settings_module = DESKTOP_SETTINGS_MODULE
        self._desktop_db = ""

    @staticmethod
    def prepare_desktop_backend(python_exe: str, project_root: str) -> tuple[bool, str]:
        root = Path(project_root)
        data_dir = desktop_data_dir(root)
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = desktop_db_path(root)
        marker_path = data_dir / "migration_fingerprint.txt"
        env = {
            "DJANGO_SETTINGS_MODULE": DESKTOP_SETTINGS_MODULE,
            "DESKTOP_DB_PATH": str(db_path),
            "PYTHONUNBUFFERED": "1",
        }

        current_fingerprint = DjangoServer._migration_fingerprint(root)
        saved_fingerprint = ""
        if marker_path.exists():
            try:
                saved_fingerprint = marker_path.read_text(encoding="utf-8").strip()
            except Exception:
                saved_fingerprint = ""

        must_migrate = (not db_path.exists()) or (current_fingerprint != saved_fingerprint)
        if must_migrate:
            ok, msg = DjangoServer._run_manage(
                python_exe,
                root,
                ["manage.py", "migrate", "--noinput"],
                env=env,
                timeout=180,
            )
            if not ok:
                return False, msg
            try:
                marker_path.write_text(current_fingerprint, encoding="utf-8")
            except Exception:
                pass

        ok, msg = DjangoServer._ensure_default_superuser(
            python_exe,
            root,
            env=env,
            username=DESKTOP_ADMIN_USERNAME,
            password=DESKTOP_ADMIN_PASSWORD,
            email=DESKTOP_ADMIN_EMAIL,
        )
        if not ok:
            return False, msg

        mode = "migrated" if must_migrate else "schema-ok"
        return True, f"Desktop backend ready ({db_path}) [{mode}]"

    @staticmethod
    def _migration_fingerprint(project_root: Path) -> str:
        """Build a stable fingerprint of migration files to skip unnecessary migrate on startup."""
        parts: list[str] = []
        migrations_root = project_root / "apps"
        if migrations_root.exists():
            for path in sorted(migrations_root.rglob("migrations/*.py")):
                if path.name == "__init__.py":
                    continue
                rel = path.relative_to(project_root).as_posix()
                stat = path.stat()
                parts.append(f"{rel}:{stat.st_size}:{stat.st_mtime_ns}")
        digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
        return digest

    def _run_manage(
        python_exe: str,
        project_root: Path,
        args: list[str],
        env: dict[str, str],
        timeout: int = 120,
    ) -> tuple[bool, str]:
        merged_env = dict(os.environ)
        merged_env.update(env)
        try:
            result = subprocess.run(
                [python_exe, *args],
                cwd=str(project_root),
                env=merged_env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except Exception as exc:
            return False, str(exc)
        output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
        if result.returncode != 0:
            return False, output.strip() or f"Command failed: {' '.join(args)}"
        return True, output.strip()

    @staticmethod
    def _ensure_default_superuser(
        python_exe: str,
        project_root: Path,
        env: dict[str, str],
        username: str,
        password: str,
        email: str,
    ) -> tuple[bool, str]:
        payload_json = json.dumps(
            {
                "username": username,
                "password": password,
                "email": email,
            }
        )
        script = (
            "import json\n"
            "from django.contrib.auth import get_user_model\n"
            "User=get_user_model()\n"
            f"data=json.loads({json.dumps(payload_json)})\n"
            "if User.objects.filter(is_superuser=True).exists():\n"
            "    print('superuser_exists')\n"
            "else:\n"
            "    User.objects.create_superuser(username=data['username'], password=data['password'], email=data['email'])\n"
            "    print('superuser_created')\n"
        )
        ok, output = DjangoServer._run_manage(
            python_exe,
            project_root,
            ["manage.py", "shell", "-c", script],
            env=env,
            timeout=90,
        )
        return ok, output

    def start(self, python_exe: str, project_root: str, host: str, port: int) -> None:
        if self._process.state() != QProcess.NotRunning:
            return
        self._desktop_db = str(desktop_db_path(Path(project_root)))
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("DJANGO_SETTINGS_MODULE", self._settings_module)
        env.insert("DESKTOP_DB_PATH", self._desktop_db)
        self._process.setProcessEnvironment(env)
        self._process.setWorkingDirectory(project_root)
        args = ["manage.py", "runserver", f"{host}:{port}", "--noreload"]
        self._process.start(python_exe, args)
        self.started.emit()

    def stop(self, timeout_ms: int = 2000) -> None:
        if self._process.state() == QProcess.NotRunning:
            return
        self._process.terminate()
        if not self._process.waitForFinished(timeout_ms):
            self._process.kill()
            self._process.waitForFinished(timeout_ms)
        self.stopped.emit()

    def _handle_output(self) -> None:
        data = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if data:
            self.output.emit(data)

    def _handle_finished(self) -> None:
        self.stopped.emit()
