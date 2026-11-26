from datetime import datetime


async def planned(janitor):
    return datetime.fromisoformat((await janitor.state())["next_run"])


async def test_reminds_then_runs_then_moves_to_next_month(janitor, clock, mail):
    await janitor.tick()
    assert mail.sent == [] and (await planned(janitor)).date().isoformat() == "2026-12-01"
    clock.to(11, 28, 0, 1)
    await janitor.tick()
    assert mail.subjects == ["Cleanup on 2026-12-01"] and janitor.cleaner.runs == []
    clock.to(12, 1, 0, 1)
    await janitor.tick()
    assert janitor.cleaner.runs == [(True, True)]
    assert mail.subjects[-1] == "Cleanup done"
    assert (await planned(janitor)).date().isoformat() == "2027-01-01"
    await janitor.tick()
    assert len(janitor.cleaner.runs) == 1


async def test_failed_reminder_holds_the_run_and_retries_hourly(janitor, clock, mail):
    await janitor.tick()
    mail.broken = True
    clock.to(11, 28, 0, 1)
    await janitor.tick()
    assert "on hold" in (await janitor.state())["error"]
    clock.to(12, 1, 0, 1)
    await janitor.tick()
    assert janitor.cleaner.runs == []
    mail.broken = False
    clock.forward(minutes=30)
    await janitor.tick()
    assert mail.sent == []  # still inside the retry hour
    clock.forward(minutes=31)
    await janitor.tick()
    assert len(mail.sent) == 1 and janitor.cleaner.runs == []
    assert "error" not in await janitor.state()
    assert (await planned(janitor)).date().isoformat() == "2026-12-05"  # full notice again


async def test_downtime_past_the_run_time_warns_first(janitor, clock, mail):
    await janitor.tick()
    clock.to(11, 28, 0, 1)
    await janitor.tick()
    clock.to(12, 2, 12)
    await janitor.tick()
    assert janitor.cleaner.runs == [] and mail.subjects[-1] == "Cleanup on 2026-12-06"
    clock.to(12, 6, 0, 1)
    await janitor.tick()
    assert len(janitor.cleaner.runs) == 1


async def test_skip_and_postpone_need_a_new_reminder(janitor, clock, mail):
    await janitor.tick()
    clock.to(11, 28, 0, 1)
    await janitor.tick()
    await janitor.skip()
    assert "reminded_at" not in await janitor.state()
    clock.to(12, 1, 0, 1)
    await janitor.tick()
    assert janitor.cleaner.runs == [] and (await planned(janitor)).date().isoformat() == "2027-01-01"
    await janitor.postpone(5)
    assert (await planned(janitor)).date().isoformat() == "2027-01-06"


async def test_no_notice_reminds_and_runs_together(janitor, clock, mail):
    await janitor.save_settings((await janitor.settings()).model_copy(update={"reminder_days": 0}), "")
    clock.to(12, 1, 0, 1)
    await janitor.tick()
    assert mail.subjects == ["Cleanup on 2026-12-01", "Cleanup done"]


async def test_manual_run_keeps_the_schedule(janitor, mail):
    await janitor.tick()
    before = await planned(janitor)
    janitor.start_run()
    await janitor.idle()
    assert await planned(janitor) == before and mail.subjects == ["Cleanup done"]
    assert (await janitor.store.history())[0]["trigger"] == "manual"


async def test_disk_alert_repeats_weekly_and_resets(janitor, clock, mail):
    janitor.disks.percent = 90
    await janitor.tick()
    clock.forward(hours=2)
    await janitor.tick()
    assert mail.subjects == ["Disk warning"]
    janitor.disks.percent = 10
    clock.forward(hours=2)
    await janitor.tick()
    janitor.disks.percent = 90
    clock.forward(hours=2)
    await janitor.tick()
    assert mail.subjects == ["Disk warning", "Disk warning"]
