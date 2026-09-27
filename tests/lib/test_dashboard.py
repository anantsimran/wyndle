import pytest

from wyndle.lib import dashboard, obsidian, task_notes, time_utils


def start(cfg, state):
    return dashboard.dispatch(cfg, state, "morning", {})


def add(cfg, state, title="Sketch the screen", **data):
    result = dashboard.dispatch(cfg, state, "add", {"title": title, **data})
    return next(t for t in result["tasks"] if t["title"] == title)


def test_full_day_with_break_and_wrap(cfg, state, clock):
    start(cfg, state)
    task = add(cfg, state)
    dashboard.dispatch(cfg, state, "focus", {"id": task["id"], "minutes": 5})
    clock.advance(minutes=2)
    assert dashboard.snapshot(cfg, state)["focusedSeconds"] == 120
    assert dashboard.snapshot(cfg, state)["lastTaskId"] == task["id"]
    dashboard.dispatch(cfg, state, "break", {"minutes": 5})
    clock.advance(minutes=5)
    assert not state.is_block_active()
    assert dashboard.snapshot(cfg, state)["focusedSeconds"] == 120
    dashboard.dispatch(cfg, state, "focus", {"id": task["id"]})
    clock.advance(minutes=1)
    dashboard.dispatch(cfg, state, "note", {"id": task["id"], "note": "Use storm blue"})
    result = dashboard.dispatch(cfg, state, "complete", {"id": task["id"]})
    assert not result["timer"]["kind"]
    assert obsidian.get_high_level_tasks(cfg.obsidian_daily_dir)[0].done
    result = dashboard.dispatch(cfg, state, "wrap", {"tomorrow": "Polish", "reflection": "Good"})
    assert result["wrapped"] and result["focusedSeconds"] == 180
    dashboard.dispatch(cfg, state, "wrap", {})
    note = task_notes.read_task_note(cfg, "Today")
    assert note.subtasks[0].time_min == 3
    assert note.subtasks[0].notes == [("Use storm blue", "open")]
    assert "Tomorrow: Polish" in obsidian.daily_note_path(cfg.obsidian_daily_dir).read_text()


def test_morning_idempotent_and_chores_visible(cfg, state, clock):
    first = start(cfg, state)
    assert first["tasks"][0]["parent"] == "Daily Chores"
    dashboard.dispatch(cfg, state, "complete", {"id": first["tasks"][0]["id"]})
    again = start(cfg, state)
    assert len(again["tasks"]) == 1
    assert again["tasks"][0]["done"]


def test_refresh_after_midnight_is_read_only(cfg, state, clock):
    start(cfg, state)
    add(cfg, state)
    clock.advance(days=1)
    result = dashboard.snapshot(cfg, state)
    assert not result["started"] and not result["wrapped"]
    assert state.get("today_date") == "2026-04-07"
    with pytest.raises(ValueError, match="Start your day"):
        dashboard.dispatch(cfg, state, "add", {"title": "New day"})
    result = start(cfg, state)
    assert any(t["title"] == "Sketch the screen" for t in result["tasks"])


@pytest.mark.parametrize("action,data", [
    ("focus", {"id": "missing"}), ("focus", {"minutes": -1}),
    ("add", {"title": "Injected\n## Heading"}), ("add", {"title": ""}),
    ("add", {"title": "Task", "estimate": True}), ("break", {"minutes": 0}),
    ("unknown", {}),
])
def test_invalid_action_does_not_change_notes(cfg, state, clock, action, data):
    start(cfg, state)
    path = obsidian.daily_note_path(cfg.obsidian_daily_dir)
    before = path.read_text()
    with pytest.raises(ValueError):
        dashboard.dispatch(cfg, state, action, data)
    assert path.read_text() == before


def test_cli_pause_clears_dashboard_timer(cfg, state, clock):
    start(cfg, state)
    task = add(cfg, state)
    dashboard.dispatch(cfg, state, "focus", {"id": task["id"]})
    state.pause_active_subtask()
    assert not dashboard.snapshot(cfg, state)["timer"]["kind"]
    assert not state.is_block_active()


def test_estimate_and_notes_survive_addition(cfg, state, clock):
    start(cfg, state)
    task = add(cfg, state, parent="Auth", estimate=25)
    dashboard.dispatch(cfg, state, "note", {"id": task["id"], "note": "Keep this"})
    add(cfg, state, title="Write tests", parent="Auth")
    tasks = dashboard.snapshot(cfg, state)["tasks"]
    assert next(t for t in tasks if t["id"] == task["id"])["notes"] == ["Keep this"]
    with pytest.raises(ValueError, match="already exists"):
        add(cfg, state, title="Sketch the screen", parent="Other")


def test_focus_expiry_does_not_discard_overflow(cfg, state, clock):
    start(cfg, state)
    task = add(cfg, state)
    dashboard.dispatch(cfg, state, "focus", {"id": task["id"], "minutes": 5})
    clock.advance(minutes=7)
    result = dashboard.snapshot(cfg, state)
    assert result["focusedSeconds"] == 420
    assert result["timer"]["end"] < time_utils.epoch_now()
    assert not state.is_block_active()
