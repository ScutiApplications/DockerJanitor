"""What DockerJanitor does: remind, clean, report, and warn about full disks."""
import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from janitor.cleaner import Cleaner
from janitor.disks import DiskProbe
from janitor.mailer import build_message, smtp_send
from janitor.schedule import first_slot, next_month_slot, slot_with_notice
from janitor.security import SecretBox
from janitor.settings import Settings
from janitor.store import Store

log = logging.getLogger("janitor")

TOLERANCE = timedelta(hours=1)  # how late a reminder or run may be before it counts as missed
RETRY = timedelta(hours=1)
DISK_CHECK = timedelta(hours=1)
DISK_REPEAT = timedelta(days=7)
PREVIEW_WAIT = 120  # seconds; `docker df` can be very slow and the reminder holds the schedule lock
SCHEDULE_FIELDS = ("day", "hour", "reminder_days", "timezone")
LABELS = {"images": "Untagged images", "cache": "Build cache"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def size(count: int | None) -> str:
    if count is None:
        return "unknown"
    value = float(count)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1000:
            return f"{value:.1f} {unit}"
        value /= 1000
    return f"{value:.1f} TB"


def describe(result: dict, verb: str) -> list[str]:
    if not result:
        return ["Both cleanup types are switched off."]
    return [f"{LABELS[k]}: failed: {v['error']}" if "error" in v else f"{LABELS[k]}: {v['count']} {verb}, {size(v['bytes'])}"
            for k, v in result.items()]


def describe_disks(disks: list[dict]) -> list[str]:
    return [f"{d['name']}: cannot read ({d['error']})" if d["error"] else f"{d['name']}: {d['percent']}% used, {size(d['free'])} free"
            for d in disks]


class Busy(Exception):
    """A cleanup is already running."""


class Janitor:
    """Schedule state lives in the store under "state"; `_state_lock` guards every change to it."""

    def __init__(self, store: Store, box: SecretBox, cleaner: Cleaner, disks: DiskProbe,
                 sender: Callable = smtp_send, clock: Callable[[], datetime] = utcnow):
        self.store, self.box, self.cleaner, self.disks = store, box, cleaner, disks
        self._sender, self._clock = sender, clock
        self._state_lock = asyncio.Lock()
        self._run_lock = asyncio.Lock()
        self._tasks: set[asyncio.Task] = set()

    # ---- settings and state ----
    async def settings(self) -> Settings:
        return Settings(**await self.store.get("settings", {}))

    async def state(self) -> dict:
        return await self.store.get("state", {})

    @property
    def running(self) -> bool:
        return self._run_lock.locked()

    async def save_settings(self, new: Settings, smtp_password: str) -> None:
        async with self._state_lock:
            old, state = await self.settings(), await self.state()
            await self.store.set("settings", new.model_dump())
            if smtp_password:
                await self.store.set("smtp_password", self.box.seal(smtp_password))
            if any(getattr(old, f) != getattr(new, f) for f in SCHEDULE_FIELDS):
                self._plan(state, first_slot(self._clock(), new))
            state.pop("last_try", None)  # a fixed mail setting is tried at the next tick
            await self.store.set("state", state)

    @staticmethod
    def _plan(state: dict, when: datetime) -> None:
        """Set the next run date. Any earlier reminder no longer counts."""
        state["next_run"] = when.isoformat()
        for key in ("reminded_at", "last_try", "error"):
            state.pop(key, None)

    async def skip(self) -> None:
        await self._reschedule(lambda planned, settings: next_month_slot(planned, settings))

    async def postpone(self, days: int) -> None:
        await self._reschedule(lambda planned, settings: planned + timedelta(days=days))

    async def _reschedule(self, move: Callable[[datetime, Settings], datetime]) -> None:
        async with self._state_lock:
            settings, state = await self.settings(), await self.state()
            planned = datetime.fromisoformat(state["next_run"]) if "next_run" in state else first_slot(self._clock(), settings)
            self._plan(state, move(planned, settings))
            await self.store.set("state", state)

    # ---- email ----
    async def send(self, subject: str, lines: list[str]) -> None:
        settings = await self.settings()
        sealed = await self.store.get("smtp_password", "")
        message = build_message(settings, subject, "\n".join(lines))
        await asyncio.to_thread(self._sender, settings, self.box.open(sealed) if sealed else "", message)

    # ---- the monthly run ----
    async def tick(self) -> None:
        """One scheduler step: send a due reminder, start a due run, check the disks."""
        async with self._state_lock:
            state = await self.state()
            due = await self._advance(state, await self.settings())
            await self.store.set("state", state)
        if due:
            await self._run("scheduled")
        await self._check_disks()

    async def _advance(self, state: dict, settings: Settings) -> bool:
        """Update `state` for the current time. True means: run the cleanup now."""
        now, notice = self._clock(), timedelta(days=settings.reminder_days)
        if "next_run" not in state:
            self._plan(state, first_slot(now, settings))
        planned = datetime.fromisoformat(state["next_run"])
        if notice and "reminded_at" in state and now > planned + TOLERANCE:
            state.pop("reminded_at")  # the run time was missed: warn again first
        if "reminded_at" not in state:
            if now < planned - notice and "error" not in state:  # a failed reminder keeps being retried
                return False
            if "last_try" in state and now - datetime.fromisoformat(state["last_try"]) < RETRY:
                return False
            if notice and planned < now + notice - TOLERANCE:
                planned = slot_with_notice(now + notice, settings)
                state["next_run"] = planned.isoformat()
            state["last_try"] = now.isoformat()
            if not await self._remind(state, settings, planned):
                return False
            state["reminded_at"] = now.isoformat()
        warned = now - datetime.fromisoformat(state["reminded_at"]) >= notice - TOLERANCE
        if now < planned or not warned or self.running:
            return False
        # Move on before running, so a crash during the run cannot start it again.
        self._plan(state, next_month_slot(planned, settings))
        return True

    async def _remind(self, state: dict, settings: Settings, planned: datetime) -> bool:
        try:
            found = await asyncio.wait_for(self.cleaner.preview(settings.prune_images, settings.prune_cache), PREVIEW_WAIT)
            preview = describe(found, "found")
        except Exception as error:  # noqa: BLE001 - the reminder matters more than the preview
            preview = [f"Preview not available: {str(error)[:300] or type(error).__name__}"]
        lines = [f"Cleanup runs on {planned:%Y-%m-%d %H:%M} ({settings.timezone}).",
                 "To skip or postpone it, open the DockerJanitor page.", "", "Would be removed (upper estimate):", *preview,
                 "", *describe_disks(await self.disks.read())]
        try:
            await self.send(f"Cleanup on {planned:%Y-%m-%d}", lines)
        except Exception as error:  # noqa: BLE001
            state["error"] = f"Reminder email failed, so the run is on hold: {str(error)[:300]}"
            log.warning(state["error"])
            return False
        state.pop("error", None)
        return True

    # ---- running ----
    def start_run(self) -> None:
        """Run now, in the background. Raises Busy when a run is active."""
        if self.running or self._tasks:
            raise Busy()
        task = asyncio.create_task(self._run("manual"))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def idle(self) -> None:
        if self._tasks:
            await asyncio.gather(*self._tasks)

    async def _run(self, trigger: str) -> None:
        async with self._run_lock:
            settings = await self.settings()
            try:
                result = await self.cleaner.run(settings.prune_images, settings.prune_cache)
            except Exception as error:  # noqa: BLE001
                log.exception("cleanup failed")
                result = {"images": {"error": str(error)[:300]}}
            entry = {"at": self._clock().isoformat(), "trigger": trigger, "result": result, "email_error": ""}
            failed = any("error" in v for v in result.values())
            try:
                await self.send("Cleanup failed" if failed else "Cleanup done",
                                [f"{trigger.capitalize()} run.", *describe(result, "removed"), "",
                                 *describe_disks(await self.disks.read())])
            except Exception as error:  # noqa: BLE001
                entry["email_error"] = str(error)[:300]
            await self.store.add_history(entry)

    # ---- disk alerts ----
    async def _check_disks(self) -> None:
        now = self._clock()
        last = await self.store.get("disk_checked")
        if last and now - datetime.fromisoformat(last) < DISK_CHECK:
            return
        await self.store.set("disk_checked", now.isoformat())
        threshold = (await self.settings()).threshold
        alerted: dict = await self.store.get("disk_alerts", {})
        disks = await self.disks.read()
        bad = [d for d in disks if d["error"] or d["percent"] >= threshold]
        alerted = {d["name"]: alerted[d["name"]] for d in bad if d["name"] in alerted}  # recovered disks are forgotten
        due = [d for d in bad if d["name"] not in alerted or now - datetime.fromisoformat(alerted[d["name"]]) >= DISK_REPEAT]
        if due:
            try:
                await self.send("Disk warning", [f"Alert level: {threshold}% used.", "", *describe_disks(due)])
                alerted.update({d["name"]: now.isoformat() for d in due})
            except Exception as error:  # noqa: BLE001 - tried again at the next check
                log.warning("disk warning email failed: %s", error)
        await self.store.set("disk_alerts", alerted)
