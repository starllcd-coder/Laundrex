from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from desktop_app.config import find_project_root


def main() -> int:
    root = find_project_root()
    print(f"OK: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
