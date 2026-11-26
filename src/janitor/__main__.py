"""`python -m janitor` serves the app; `python -m janitor reset-password` clears the admin password."""
import logging
import os
import sys
from pathlib import Path

import uvicorn

from janitor.app import create_app
from janitor.cleaner import Cleaner
from janitor.disks import DiskProbe
from janitor.security import SecretBox
from janitor.service import Janitor
from janitor.store import Store


def main(arguments: list[str]) -> None:
    # Only for runs outside Docker; the container uses the defaults.
    data = Path(os.environ.get("JANITOR_DATA", "/data"))
    key = Path(os.environ.get("JANITOR_KEY", "/key"))
    port = int(os.environ.get("JANITOR_PORT", "26510"))
    store = Store(data / "janitor.db")
    if arguments == ["reset-password"]:
        store.delete_sync("admin")
        print("Admin password cleared. Restart the service to get a new setup code.")
        return
    if arguments:
        sys.exit("usage: python -m janitor [reset-password]")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    janitor = Janitor(store, SecretBox(key / "secret.key"), Cleaner(), DiskProbe())
    uvicorn.run(create_app(janitor), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main(sys.argv[1:])
