"""Time utilities for schedule calculations and display formatting.

All schedule-related time operations go through this module so that
clock access is centralized (makes testing easier) and formatting is
consistent throughout the CLI.
"""

from __future__ import annotations

from datetime import date, datetime, time


def now() -> datetime:
    """Return the current local datetime."""
    return datetime.now()


def now_time_str() -> str:
    """Current time as ``HH:MM`` (24-hour)."""
    return now().strftime("%H:%M")


def now_date_str() -> str:
    """Current date as ``YYYY-MM-DD`` ISO format."""
    return date.today().isoformat()


def now_friendly() -> str:
    """Current time in 12-hour format, e.g. ``02:30 PM``."""
    return now().strftime("%I:%M %p")


def today_weekday() -> str:
    """Full weekday name, e.g. ``Monday``."""
    return now().strftime("%A")


def parse_time(time_str: str) -> time:
    """Parse an ``HH:MM`` string into a :class:`datetime.time`.

    Args:
        time_str: Time in 24-hour ``HH:MM`` format.

    Returns:
        Corresponding :class:`datetime.time` object.
    """
    h, m = time_str.split(":")
    return time(int(h), int(m))


def time_to_datetime(time_str: str) -> datetime:
    """Convert an ``HH:MM`` string to today's datetime at that time.

    Args:
        time_str: Time in 24-hour ``HH:MM`` format.

    Returns:
        :class:`datetime.datetime` for today at the given time.
    """
    return datetime.combine(date.today(), parse_time(time_str))


def minutes_until(time_str: str) -> int:
    """Minutes remaining from now until *time_str* today.

    Returns a negative value if the time has already passed.

    Args:
        time_str: Target time in ``HH:MM`` format.
    """
    delta = time_to_datetime(time_str) - now()
    return int(delta.total_seconds() / 60)


def hours_minutes(mins: int) -> str:
    """Format a minute count as a human-readable ``Xh Ym`` string.

    Args:
        mins: Total minutes.  Negative values return ``"past"``.

    Examples:
        >>> hours_minutes(95)
        '1h 35m'
        >>> hours_minutes(12)
        '12m'
    """
    if mins < 0:
        return "past"
    h, m = divmod(mins, 60)
    return f"{h}h {m}m" if h > 0 else f"{m}m"


def epoch_now() -> int:
    """Current Unix timestamp as an integer (seconds since epoch)."""
    return int(now().timestamp())
