from unittest.mock import MagicMock

from janitor.cleaner import Cleaner


def fake_docker():
    client = MagicMock()
    client.images.prune.return_value = {"ImagesDeleted": [{"Deleted": "a"}], "SpaceReclaimed": 10}
    client.api.prune_builds.return_value = {"CachesDeleted": None, "SpaceReclaimed": 20}
    return client


async def test_only_the_two_prune_calls_with_their_filters():
    client = fake_docker()
    result = await Cleaner(lambda: client).run(True, True)
    assert result == {"images": {"count": 1, "bytes": 10}, "cache": {"count": 0, "bytes": 20}}
    assert [c[0] for c in client.method_calls] == ["images.prune", "api.prune_builds"]
    client.images.prune.assert_called_once_with(filters={"dangling": True})
    client.api.prune_builds.assert_called_once_with(filters={"until": "168h"}, all=True)


async def test_switched_off_steps_do_nothing():
    client = fake_docker()
    assert await Cleaner(lambda: client).run(False, False) == {}
    assert client.method_calls == []


async def test_one_failing_step_does_not_stop_the_other():
    client = fake_docker()
    client.images.prune.side_effect = RuntimeError("boom")
    result = await Cleaner(lambda: client).run(True, True)
    assert result["images"] == {"error": "boom"} and result["cache"]["bytes"] == 20


async def test_preview_counts_only_old_unused_cache():
    client = fake_docker()
    client.df.return_value = {"BuildCache": [
        {"Size": 5, "InUse": False, "LastUsedAt": "2020-01-01T00:00:00.123456789Z"},
        {"Size": 7, "InUse": True, "LastUsedAt": "2020-01-01T00:00:00Z"},
        {"Size": 9, "InUse": False, "CreatedAt": "2999-01-01T00:00:00Z"},
    ]}
    assert (await Cleaner(lambda: client).preview(False, True))["cache"] == {"count": 1, "bytes": 5}
