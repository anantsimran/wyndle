import pytest

from wyndle.lib import time_utils


@pytest.mark.parametrize(
    ("mins", "expected"), [(0, "0m"), (12, "12m"), (95, "1h 35m"), (-1, "past")],
)
def test_hours_minutes(mins, expected):
    assert time_utils.hours_minutes(mins) == expected


def test_clock_driven_helpers(clock):
    clock.set("2026-04-07T14:30:00")
    assert time_utils.now_date_str() == "2026-04-07"
    assert time_utils.now_time_str() == "14:30"
    assert time_utils.today_weekday() == "Tuesday"
    assert time_utils.minutes_until("15:00") == 30
    assert time_utils.minutes_until("14:00") == -30
