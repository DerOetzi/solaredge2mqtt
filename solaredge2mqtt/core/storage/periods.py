from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from solaredge2mqtt.services.energy.models import HistoricPeriod

LIFETIME_UNIT = "99y"
LIFETIME_START = datetime(1970, 1, 1, tzinfo=timezone.utc)
LIFETIME_STOP = datetime(2100, 1, 1, tzinfo=timezone.utc)


def period_bounds(
    period: HistoricPeriod, now: datetime, tz: ZoneInfo
) -> tuple[datetime, datetime]:
    from solaredge2mqtt.services.energy.models import HistoricQuery

    is_actual = period.query == HistoricQuery.ACTUAL

    if period.unit == LIFETIME_UNIT:
        return LIFETIME_START, LIFETIME_STOP

    local = now.astimezone(tz)

    if period.unit == "1h":
        return _hour_bounds(local, is_actual)

    start, stop = _calendar_bounds(local.replace(tzinfo=None), period.unit, is_actual)
    return start.replace(tzinfo=tz), stop.replace(tzinfo=tz)


def _hour_bounds(local: datetime, is_actual: bool) -> tuple[datetime, datetime]:
    hour_start = local.replace(minute=0, second=0, microsecond=0)

    if is_actual:
        return hour_start, hour_start + timedelta(hours=1)

    return hour_start - timedelta(hours=1), hour_start


def _calendar_bounds(
    naive: datetime, unit: str, is_actual: bool
) -> tuple[datetime, datetime]:
    day = naive.replace(hour=0, minute=0, second=0, microsecond=0)

    if unit == "1d":
        current, following = day, _add_days(day, 1)
        previous = _add_days(day, -1)
    elif unit == "1w":
        current = _add_days(day, -day.weekday())
        following = _add_days(current, 7)
        previous = _add_days(current, -7)
    elif unit == "1mo":
        current = day.replace(day=1)
        following = add_months(current, 1)
        previous = add_months(current, -1)
    elif unit == "1y":
        current = day.replace(month=1, day=1)
        following = current.replace(year=current.year + 1)
        previous = current.replace(year=current.year - 1)
    else:
        raise ValueError(f"Unsupported period unit '{unit}'")

    if is_actual:
        return current, following

    return previous, current


def _add_days(moment: datetime, days: int) -> datetime:
    shifted = moment.date() + timedelta(days=days)
    return datetime.combine(shifted, moment.time())


def add_months(moment: datetime, months: int) -> datetime:
    total = moment.year * 12 + (moment.month - 1) + months
    return moment.replace(year=total // 12, month=total % 12 + 1, day=1)


def day_bounds(now: datetime, tz: ZoneInfo, days: int = 1) -> tuple[datetime, datetime]:
    local = now.astimezone(tz)
    start = local.replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)
    stop = _add_days(start, days)
    return start.replace(tzinfo=tz), stop.replace(tzinfo=tz)


def hour_start(now: datetime) -> datetime:
    return now.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def month_start(now: datetime) -> datetime:
    return now.astimezone(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )


def as_epoch(moment: datetime) -> int:
    return int(moment.timestamp())


def from_epoch(seconds: int) -> datetime:
    return datetime.fromtimestamp(seconds, tz=timezone.utc)


def local_zone(name: str) -> ZoneInfo:
    return ZoneInfo(name)


__all__ = [
    "add_months",
    "as_epoch",
    "day_bounds",
    "from_epoch",
    "hour_start",
    "local_zone",
    "month_start",
    "period_bounds",
]
