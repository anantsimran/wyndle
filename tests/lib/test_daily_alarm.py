"""Daily schedules use the same tasks and day lifecycle as the dashboard."""

import pytest

from wyndle.lib import dashboard


def _add(cfg, state, title, estimate):
    status = dashboard.dispatch(cfg, state, "add", {"title": title, "estimate": estimate})
    return next(task for task in status["tasks"] if task["title"] == title)


def _plan(cfg, state, ids, **settings):
    return dashboard.dispatch(cfg, state, "alarm_plan", {
        "start": "10:00", "workMinutes": 25, "bufferMinutes": 5, "breakMinutes": 5,
        "taskIds": ids, **settings,
    })["dailyAlarm"]


def test_selected_tasks_become_ordered_work_buffer_break_cycles(cfg, state, clock):
    cfg.daily_chores.clear()
    dashboard.dispatch(cfg, state, "morning", {})
    long = _add(cfg, state, "Write draft", 50)
    short = _add(cfg, state, "Review it", 10)
    plan = _plan(cfg, state, [short["id"], long["id"]])

    blocks = plan["blocks"]
    assert [(b["kind"], b["title"], b["minutes"]) for b in blocks] == [
        ("work", "Review it", 10), ("buffer", "Buffer", 5), ("break", "Break", 5),
        ("work", "Write draft", 25), ("buffer", "Buffer", 5), ("break", "Break", 5),
        ("work", "Write draft", 25), ("buffer", "Buffer", 5), ("break", "Break", 5),
    ]
    assert blocks[0]["start"] == clock.current.timestamp()
    assert all(left["end"] == right["start"] for left, right in zip(blocks, blocks[1:]))
    assert blocks[-1]["end"] - blocks[0]["start"] == 90 * 60
    assert dashboard.snapshot(cfg, state)["dailyAlarm"]["id"] == plan["id"]


def test_estimate_uses_remaining_time_and_unestimated_task_gets_one_block(cfg, state, clock):
    cfg.daily_chores.clear()
    dashboard.dispatch(cfg, state, "morning", {})
    partial = _add(cfg, state, "Partial", 15)
    unknown = _add(cfg, state, "Unknown", 0)
    dashboard.dispatch(cfg, state, "focus", {"id": partial["id"], "minutes": 15})
    clock.advance(minutes=5)
    dashboard.dispatch(cfg, state, "pause", {})

    plan = _plan(cfg, state, [partial["id"], unknown["id"]])
    assert [block["minutes"] for block in plan["blocks"]] == [10, 5, 5, 25, 5, 5]
    assert [block["kind"] for block in plan["blocks"]] == [
        "work", "buffer", "break", "work", "buffer", "break",
    ]


def test_estimate_mode_uses_each_tasks_remaining_time_as_one_block(cfg, state, clock):
    cfg.daily_chores.clear()
    dashboard.dispatch(cfg, state, "morning", {})
    long = _add(cfg, state, "Long", 60)
    unknown = _add(cfg, state, "No estimate", 0)
    dashboard.dispatch(cfg, state, "focus", {"id": long["id"], "minutes": 15})
    clock.advance(minutes=10)
    dashboard.dispatch(cfg, state, "pause", {})

    plan = _plan(cfg, state, [long["id"], unknown["id"]], workMode="estimate")
    assert plan["workMode"] == "estimate"
    assert [(block["kind"], block["minutes"]) for block in plan["blocks"]] == [
        ("work", 50), ("buffer", 5), ("break", 5),
        ("work", 25), ("buffer", 5), ("break", 5),
    ]


def test_buffer_and_final_break_count_toward_hard_stop(cfg, state, clock):
    cfg.daily_chores.clear()
    dashboard.dispatch(cfg, state, "morning", {})
    task = _add(cfg, state, "One block", 25)
    cfg.hard_stop = "10:35"
    plan = _plan(cfg, state, [task["id"]])
    assert plan["blocks"][-1]["end"] - plan["blocks"][0]["start"] == 35 * 60
    cfg.hard_stop = "10:34"
    with pytest.raises(ValueError, match="hard stop"):
        _plan(cfg, state, [task["id"]])
    assert dashboard.snapshot(cfg, state)["dailyAlarm"]["id"] == plan["id"]


def test_older_page_gets_default_buffer(cfg, state, clock):
    cfg.daily_chores.clear()
    dashboard.dispatch(cfg, state, "morning", {})
    task = _add(cfg, state, "One block", 10)
    result = dashboard.dispatch(cfg, state, "alarm_plan", {
        "start": "10:00", "workMinutes": 25, "breakMinutes": 5,
        "taskIds": [task["id"]],
    })["dailyAlarm"]
    assert result["bufferMinutes"] == 5
    assert result["workMode"] == "fixed"
    assert [block["kind"] for block in result["blocks"]] == ["work", "buffer", "break"]


def test_plan_tracks_task_completion_and_clear_and_new_day(cfg, state, clock):
    cfg.daily_chores.clear()
    dashboard.dispatch(cfg, state, "morning", {})
    task = _add(cfg, state, "Finish", 15)
    first = _plan(cfg, state, [task["id"]])
    assert first["blocks"][0]["done"] is False

    status = dashboard.dispatch(cfg, state, "complete", {"id": task["id"]})
    assert status["dailyAlarm"]["blocks"][0]["done"] is True
    status = dashboard.dispatch(cfg, state, "delete", {"id": task["id"]})
    assert status["dailyAlarm"]["blocks"][0]["missing"] is True
    assert status["dailyAlarm"]["blocks"][0]["title"] == "Task changed"

    dashboard.dispatch(cfg, state, "alarm_clear", {})
    assert dashboard.snapshot(cfg, state)["dailyAlarm"] is None
    task = _add(cfg, state, "Tomorrow", 10)
    _plan(cfg, state, [task["id"]])
    clock.advance(days=1)
    assert dashboard.snapshot(cfg, state)["dailyAlarm"] is None
    dashboard.dispatch(cfg, state, "morning", {"carryover": False})
    assert dashboard.snapshot(cfg, state)["dailyAlarm"] is None


def test_invalid_plan_keeps_existing_schedule(cfg, state, clock):
    cfg.daily_chores.clear()
    dashboard.dispatch(cfg, state, "morning", {})
    task = _add(cfg, state, "One", 25)
    first = _plan(cfg, state, [task["id"]])
    bad = [
        {"start": "24:00"}, {"workMinutes": True}, {"workMode": "other"},
        {"bufferMinutes": 0},
        {"bufferMinutes": False}, {"breakMinutes": 0},
        {"taskIds": [task["id"], task["id"]]}, {"taskIds": ["missing"]},
        {"start": "19:50"},
    ]
    for change in bad:
        with pytest.raises(ValueError):
            _plan(cfg, state, [task["id"]], **change)
        assert dashboard.snapshot(cfg, state)["dailyAlarm"]["id"] == first["id"]

    dashboard.dispatch(cfg, state, "complete", {"id": task["id"]})
    with pytest.raises(ValueError, match="changed"):
        _plan(cfg, state, [task["id"]])
