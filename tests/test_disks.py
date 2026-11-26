from janitor.disks import DiskProbe


async def test_only_an_unmounted_optional_disk_is_left_out(tmp_path):
    probes = {"system": tmp_path / "missing-system", "backup": tmp_path / "missing-backup", "ok": tmp_path}
    found = await DiskProbe(probes, optional=frozenset({"backup"})).read()
    assert [d["name"] for d in found] == ["system", "ok"]
    assert found[0]["error"] and not found[1]["error"]


async def test_a_mounted_optional_disk_that_fails_is_reported(tmp_path, monkeypatch):
    def broken(_):
        raise OSError(5, "Input/output error")

    monkeypatch.setattr("janitor.disks.shutil.disk_usage", broken)
    found = await DiskProbe({"backup": tmp_path}, optional=frozenset({"backup"})).read()
    assert "Input/output error" in found[0]["error"]
