"""Reads how full a disk is, through an empty probe folder mounted from that disk."""
import asyncio
import shutil
from pathlib import Path

DEFAULT_PROBES = {"System disk (/DATA)": Path("/disks/system"), "Backup disk (HDD320-1)": Path("/disks/backup")}


class DiskProbe:
    def __init__(self, probes: dict[str, Path] = DEFAULT_PROBES):
        self._probes = probes

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
                out.append({"name": name, "percent": None, "free": None, "total": None, "error": str(error)[:200]})
        return out
