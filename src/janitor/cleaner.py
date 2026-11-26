"""The only code that talks to Docker. It can delete untagged images and old build cache, nothing else."""
import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import docker

CACHE_AGE = timedelta(days=7)
CACHE_FILTER = {"until": "168h"}  # same age as CACHE_AGE
DOCKER_TIMEOUT = 900  # pruning tens of gigabytes takes minutes; the SDK default is 60 s


def default_client() -> docker.DockerClient:
    return docker.from_env(timeout=DOCKER_TIMEOUT)


class Cleaner:
    """The Docker SDK blocks, so every public method runs in a worker thread."""

    def __init__(self, client_factory: Callable[[], object] = default_client):
        self._factory = client_factory

    async def preview(self, images: bool, cache: bool) -> dict:
        return await asyncio.to_thread(self._preview, images, cache)

    async def run(self, images: bool, cache: bool) -> dict:
        return await asyncio.to_thread(self._run, images, cache)

    def _preview(self, images: bool, cache: bool) -> dict:
        client = self._factory()
        result: dict = {}
        if images:
            found = client.images.list(filters={"dangling": True})
            # Upper bound: images share layers, and an image used by a container is skipped by the prune.
            result["images"] = {"count": len(found), "bytes": sum(i.attrs.get("Size", 0) for i in found)}
        if cache:
            old = [c for c in client.df().get("BuildCache") or [] if self._is_old(c)]
            result["cache"] = {"count": len(old), "bytes": sum(c.get("Size", 0) for c in old)}
        return result

    @staticmethod
    def _is_old(entry: dict) -> bool:
        stamp = entry.get("LastUsedAt") or entry.get("CreatedAt")
        if entry.get("InUse") or not stamp:
            return False
        return datetime.now(timezone.utc) - datetime.fromisoformat(stamp) >= CACHE_AGE

    def _run(self, images: bool, cache: bool) -> dict:
        """One failing step is reported and does not stop the other."""
        steps = []
        if images:
            steps.append(("images", "ImagesDeleted",
                          lambda c: c.images.prune(filters={"dangling": True})))
        if cache:
            steps.append(("cache", "CachesDeleted",
                          lambda c: c.api.prune_builds(filters=CACHE_FILTER, all=True)))
        result: dict = {}
        for name, deleted_key, prune in steps:
            try:
                answer = prune(self._factory())
                result[name] = {"count": len(answer.get(deleted_key) or []),
                                "bytes": answer.get("SpaceReclaimed") or 0}
            except Exception as error:  # noqa: BLE001 - shown to the admin and mailed
                result[name] = {"error": str(error)[:300]}
        return result
