"""Run on a PC for development: data under .local/, testing port 29900."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("JANITOR_DATA", str(ROOT / ".local" / "data"))
os.environ.setdefault("JANITOR_KEY", str(ROOT / ".local" / "key"))
os.environ.setdefault("JANITOR_PORT", "29900")

from janitor.__main__ import main  # noqa: E402

main([])
