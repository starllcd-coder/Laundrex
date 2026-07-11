import os
import shutil
from datetime import datetime
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a database backup (SQLite only)."

    def add_arguments(self, parser):
        parser.add_argument("--dir", default="backups", help="Backup directory (relative to BASE_DIR).")

    def handle(self, *args, **options):
        db = settings.DATABASES.get("default", {})
        if db.get("ENGINE") != "django.db.backends.sqlite3":
            self.stdout.write(self.style.WARNING("Backup supported only for SQLite in this command."))
            return

        db_path = db.get("NAME")
        if not db_path or not os.path.exists(db_path):
            self.stdout.write(self.style.ERROR("SQLite database file not found."))
            return

        backup_dir = os.path.join(settings.BASE_DIR, options["dir"])
        os.makedirs(backup_dir, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"db_backup_{ts}.sqlite3"
        backup_path = os.path.join(backup_dir, backup_name)

        shutil.copy2(db_path, backup_path)
        self.stdout.write(self.style.SUCCESS(f"Backup created: {backup_path}"))
