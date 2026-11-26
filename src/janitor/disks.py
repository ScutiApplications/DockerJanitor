"""Reads how full a disk is, through an empty probe folder mounted from that disk."""
import asyncio
import shutil
from pathlib import Path

BACKUP = "Backup disk"
DEFAULT_PROBES = {"System disk (/DATA)": Path("/disks/system"), BACKUP: Path("/disks/backup")}


class DiskProbe:
    """An optional disk whose probe folder is not mounted is left out; any other failure is reported."""

    def __init__(self, probes: dict[str, Path] = DEFAULT_PROBES, optional: frozenset[str] = frozenset({BACKUP})):
        self._probes, self._optional = probes, optional

    async def read(self) -> list[dict]:
        return await asyncio.to_thread(self._read)

    def _read(self) -> list[dict]:
        out = []
        for name, path in self._probes.items():
            try:
                usage = shutil.disk_usage(path)
                percent = round(100 * usage.used / ((usage.used + usage.free) or 1))  # same rule as `df`
                out.append({"name": name, "percent": percent, "free": usage.free, "total": usage.total, "error": ""})
            except OSError as error:
                if name in self._optional and isinstance(error, FileNotFoundError):
                    continue  # not mounted in docker-compose.yml: the admin does not want it watched
                out.append({"name": name, "percent": None, "free": None, "total": None, "error": str(error)[:200]})
        return out
