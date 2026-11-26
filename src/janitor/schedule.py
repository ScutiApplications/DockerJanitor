"""Pure date rules for the monthly run."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from janitor.settings import Settings


def _slot(year: int, month: int, settings: Settings) -> datetime:
    return datetime(year, month, settings.day, settings.hour, tzinfo=ZoneInfo(settings.timezone))


def next_month_slot(after: datetime, settings: Settings) -> datetime:
    """The configured day and hour in the month that follows `after`."""
    local = after.astimezone(ZoneInfo(settings.timezone))
    return _slot(local.year + local.month // 12, local.month % 12 + 1, settings)


def first_slot(now: datetime, settings: Settings) -> datetime:
    """The next configured day and hour after `now`."""
    local = now.astimezone(ZoneInfo(settings.timezone))
    this_month = _slot(local.year, local.month, settings)
    return this_month if this_month > now else next_month_slot(now, settings)


def slot_with_notice(earliest: datetime, settings: Settings) -> datetime:
    """The first moment at the configured hour that is not before `earliest`."""
    local = earliest.astimezone(ZoneInfo(settings.timezone))
    slot = local.replace(hour=settings.hour, minute=0, second=0, microsecond=0)
    return slot if slot >= local else slot + timedelta(days=1)
