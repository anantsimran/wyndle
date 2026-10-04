import pytest

from wyndle.lib import daily_notes, dashboard, task_notes, time_utils


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
    assert daily_notes.get_high_level_tasks(cfg.daily_dir)[0].done
    result = dashboard.dispatch(cfg, state, "wrap", {"tomorrow": "Polish", "reflection": "Good"})
    assert result["wrapped"] and result["focusedSeconds"] == 180
    dashboard.dispatch(cfg, state, "wrap", {})
    note = task_notes.read_task_note(cfg, "Today")
    assert note.subtasks[0].time_min == 3
    assert note.subtasks[0].notes == [("Use storm blue", "open")]
    assert "Tomorrow: Polish" in daily_notes.daily_note_path(cfg.daily_dir).read_text()


def test_morning_idempotent_and_chores_visible(cfg, state, clock):
    first = start(cfg, state)
    assert first["tasks"][0]["parent"] == "Daily Chores"
    dashboard.dispatch(cfg, state, "complete", {"id": first["tasks"][0]["id"]})
    again = start(cfg, state)
    assert len(again["tasks"]) == 1
    assert again["tasks"][0]["done"]


def _write_previous_day(cfg):
    (cfg.daily_dir / "2026-04-06.md").write_text(
        "# Monday\n\n"
        "## High Level Tasks\n"
        "- [ ] Alpha\n- [ ] Beta\n- [x] Done\n- [ ] Gamma\n"
        "- [ ] Daily Chores\n\n"
        "## Task Details\n"
        "### Alpha\n- [ ] First step ~10m\n"
        "### Beta\n- [ ] Second step ~20m\n"
        "### Gamma\n- [ ] Third step ~30m\n"
        "### Daily Chores\n- [ ] Old chore ~15m\n"
    )


def test_morning_carries_only_selected_high_level_tasks(cfg, state, clock):
    _write_previous_day(cfg)
    assert dashboard.snapshot(cfg, state)["carryover"] == ["Alpha", "Beta", "Gamma"]

    result = dashboard.dispatch(cfg, state, "morning", {"carryover": ["Gamma", "Alpha"]})
    assert [task["title"] for task in result["highLevelTasks"]] == ["Alpha", "Gamma"]
    assert {(task["parent"], task["title"]) for task in result["tasks"]} == {
        ("Daily Chores", "Reply to Slack"),
        ("Alpha", "First step"),
        ("Gamma", "Third step"),
    }

    again = dashboard.dispatch(cfg, state, "morning", {"carryover": ["Beta"]})
    assert [task["title"] for task in again["highLevelTasks"]] == ["Alpha", "Gamma"]


def test_carryover_choices_ignore_duplicate_names_and_chores(cfg, state, clock):
    _write_previous_day(cfg)
    path = cfg.daily_dir / "2026-04-06.md"
    text = path.read_text().replace("- [ ] Beta\n", "- [ ] Beta\n- [ ] beta\n")
    text = text.replace("- [ ] Daily Chores\n", "- [ ] Daily Chores\n- [ ] daily chores\n")
    path.write_text(text)
    assert dashboard.snapshot(cfg, state)["carryover"] == ["Alpha", "Beta", "Gamma"]


@pytest.mark.parametrize("carryover,expected", [
    (True, ["Alpha", "Beta", "Gamma"]),
    (False, []),
    ([], []),
])
def test_morning_preserves_boolean_carryover(cfg, state, clock, carryover, expected):
    _write_previous_day(cfg)
    result = dashboard.dispatch(cfg, state, "morning", {"carryover": carryover})
    assert [task["title"] for task in result["highLevelTasks"]] == expected


@pytest.mark.parametrize("carryover", [
    None, "Alpha", 1, {}, ["Unknown"], ["Alpha", "Alpha"], [1], [""],
    ["Daily Chores"],
])
def test_morning_rejects_invalid_carryover_without_starting_day(
    cfg, state, clock, carryover,
):
    _write_previous_day(cfg)
    with pytest.raises(ValueError, match="carryover"):
        dashboard.dispatch(cfg, state, "morning", {"carryover": carryover})
    assert not daily_notes.daily_note_path(cfg.daily_dir).exists()
    assert state.get("today_started") == ""


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
    path = daily_notes.daily_note_path(cfg.daily_dir)
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


def test_add_group_is_visible_empty_and_case_insensitive(cfg, state, clock):
    start(cfg, state)
    result = dashboard.dispatch(cfg, state, "add_group", {"title": "Ship A2"})
    assert {"title": "Ship A2", "done": False} in result["highLevelTasks"]
    result = dashboard.dispatch(cfg, state, "add_group", {"title": "ship a2"})
    assert [g["title"] for g in result["highLevelTasks"]].count("Ship A2") == 1
    assert add(cfg, state, parent="SHIP A2")["parent"] == "Ship A2"


def test_delete_subtask_pauses_and_keeps_siblings(cfg, state, clock):
    start(cfg, state)
    doomed = add(cfg, state, title="Doomed", parent="Auth")
    keep = add(cfg, state, title="Keep", parent="Auth")
    dashboard.dispatch(cfg, state, "note", {"id": doomed["id"], "note": "gone"})
    dashboard.dispatch(cfg, state, "note", {"id": keep["id"], "note": "stays"})
    dashboard.dispatch(cfg, state, "focus", {"id": doomed["id"]})
    result = dashboard.dispatch(cfg, state, "delete", {"id": doomed["id"]})
    assert not result["timer"]["kind"]
    assert [t["title"] for t in result["tasks"] if t["parent"] == "Auth"] == ["Keep"]
    assert daily_notes.read_subtask_notes(cfg.daily_dir, "Auth") == {"Keep": ["stays"]}


def test_delete_group_removes_heading_and_subtasks(cfg, state, clock):
    start(cfg, state)
    add(cfg, state, title="One", parent="Auth")
    result = dashboard.dispatch(cfg, state, "delete_group", {"parent": "Auth"})
    assert "Auth" not in result["groups"]
    assert not any(t["parent"] == "Auth" for t in result["tasks"])
    with pytest.raises(ValueError, match="changed"):
        dashboard.dispatch(cfg, state, "delete_group", {"parent": "Auth"})


def test_complete_group_marks_everything_done(cfg, state, clock):
    start(cfg, state)
    first = add(cfg, state, title="One", parent="Auth")
    add(cfg, state, title="Two", parent="Auth")
    dashboard.dispatch(cfg, state, "focus", {"id": first["id"]})
    result = dashboard.dispatch(cfg, state, "complete_group", {"parent": "Auth"})
    assert not result["timer"]["kind"]
    assert all(t["done"] for t in result["tasks"] if t["parent"] == "Auth")
    assert {"title": "Auth", "done": True} in result["highLevelTasks"]


def test_reopen_unchecks_subtask_and_its_group(cfg, state, clock):
    start(cfg, state)
    task = add(cfg, state, title="One", parent="Auth")
    dashboard.dispatch(cfg, state, "complete", {"id": task["id"]})
    result = dashboard.dispatch(cfg, state, "reopen", {"id": task["id"]})
    assert not next(t for t in result["tasks"] if t["id"] == task["id"])["done"]
    assert {"title": "Auth", "done": False} in result["highLevelTasks"]
    assert "- [ ] One ~15m" in daily_notes.daily_note_path(cfg.daily_dir).read_text()


def test_priority_and_time_edit_preserve_running_task_and_notes(cfg, state, clock):
    start(cfg, state)
    task = add(cfg, state, title="Important step", estimate=15, priority=True)
    assert task["priority"]
    dashboard.dispatch(cfg, state, "note", {"id": task["id"], "note": "Keep this"})
    dashboard.dispatch(cfg, state, "focus", {"id": task["id"], "minutes": 5})
    started = time_utils.epoch_now()
    clock.advance(minutes=2)
    edited = dashboard.dispatch(cfg, state, "edit_task", {
        "id": task["id"], "estimate": 3, "elapsedMinutes": 6, "priority": True,
    })
    current = next(t for t in edited["tasks"] if t["id"] == task["id"])
    assert (current["estimate"], current["elapsed"], current["startedAt"]) == (3, 360, started)
    assert current["active"] and edited["timer"]["kind"] == "focus"
    assert current["notes"] == ["Keep this"]
    note_text = daily_notes.daily_note_path(cfg.daily_dir).read_text()
    assert current["priority"] and "~3m ~p0" in note_text
    clock.advance(minutes=1)
    assert dashboard.snapshot(cfg, state)["tasks"][-1]["elapsed"] == 420
    toggled = dashboard.dispatch(cfg, state, "priority", {"id": task["id"], "priority": False})
    assert not next(t for t in toggled["tasks"] if t["id"] == task["id"])["priority"]
    assert toggled["timer"]["kind"] == "focus"
    edited_again = dashboard.dispatch(cfg, state, "edit_task", {
        "id": task["id"], "estimate": 8, "priority": False,
    })
    assert next(t for t in edited_again["tasks"] if t["id"] == task["id"])["elapsed"] == 420


def test_completed_stats_survive_state_clear_and_reopen(cfg, state, clock):
    start(cfg, state)
    task = add(cfg, state, title="Timed step", estimate=1)
    dashboard.dispatch(cfg, state, "focus", {"id": task["id"]})
    started = time_utils.epoch_now()
    clock.advance(minutes=3)
    ended = time_utils.epoch_now()
    completed = dashboard.dispatch(cfg, state, "complete", {"id": task["id"]})
    saved = next(t for t in completed["tasks"] if t["id"] == task["id"])
    assert (saved["elapsed"], saved["startedAt"], saved["endedAt"]) == (180, started, ended)
    assert saved["elapsed"] > saved["estimate"] * 60
    assert "<!-- wyndle:start=" in daily_notes.daily_note_path(cfg.daily_dir).read_text()
    assert daily_notes.get_task_details(cfg.daily_dir, "Today")[0].display_text == "Timed step"
    state.clear_day()
    persisted = next(t for t in dashboard.snapshot(cfg, state)["tasks"] if t["id"] == task["id"])
    assert (persisted["elapsed"], persisted["startedAt"], persisted["endedAt"]) == (
        180, started, ended,
    )
    state.set("today_date", time_utils.now_date_str())
    state.set("today_started", "true")
    reopened = dashboard.dispatch(cfg, state, "reopen", {"id": task["id"]})
    assert next(t for t in reopened["tasks"] if t["id"] == task["id"])["endedAt"] == 0


def test_priority_survives_task_note_roundtrip_and_carryover(cfg, state, clock):
    start(cfg, state)
    add(cfg, state, title="Must do", parent="Project", priority=True)
    dashboard.dispatch(cfg, state, "wrap", {})
    note = task_notes.read_task_note(cfg, "Project")
    assert note.subtasks[0].priority
    assert "~p0" in task_notes.generate_daily_subtasks(cfg, "Project")


def test_optional_and_p0_are_exclusive_and_persist(cfg, state, clock):
    start(cfg, state)
    task = add(cfg, state, title="Nice to have", parent="Project", optional=True)
    assert task["optional"] and not task["priority"]
    assert "~optional" in daily_notes.daily_note_path(cfg.daily_dir).read_text()
    promoted = dashboard.dispatch(cfg, state, "priority", {"id": task["id"], "priority": True})
    current = next(t for t in promoted["tasks"] if t["id"] == task["id"])
    assert current["priority"] and not current["optional"]
    demoted = dashboard.dispatch(cfg, state, "optional", {"id": task["id"], "optional": True})
    current = next(t for t in demoted["tasks"] if t["id"] == task["id"])
    assert current["optional"] and not current["priority"]
    dashboard.dispatch(cfg, state, "wrap", {})
    sub = task_notes.read_task_note(cfg, "Project").subtasks[0]
    assert sub.optional and not sub.priority
    assert "~optional" in task_notes.generate_daily_subtasks(cfg, "Project")


def test_optional_validation_keeps_daily_note_unchanged(cfg, state, clock):
    start(cfg, state)
    task = add(cfg, state)
    path = daily_notes.daily_note_path(cfg.daily_dir)
    before = path.read_text()
    for action, data in (
        ("add", {"title": "Invalid", "priority": True, "optional": True}),
        ("edit_task", {"id": task["id"], "priority": True, "optional": True}),
        ("optional", {"id": task["id"], "optional": "yes"}),
        ("move_task", {"id": task["id"], "direction": "sideways"}),
    ):
        with pytest.raises(ValueError):
            dashboard.dispatch(cfg, state, action, data)
        assert path.read_text() == before


def test_reorder_within_group_moves_notes_and_keeps_other_groups(cfg, state, clock):
    start(cfg, state)
    first = add(cfg, state, title="First", parent="Project", priority=True)
    middle = add(cfg, state, title="Middle", parent="Project")
    last = add(cfg, state, title="Last", parent="Project", optional=True)
    add(cfg, state, title="Other", parent="Elsewhere")
    dashboard.dispatch(cfg, state, "note", {"id": first["id"], "note": "First note"})
    dashboard.dispatch(cfg, state, "note", {"id": last["id"], "note": "Last note"})
    dashboard.dispatch(cfg, state, "complete", {"id": middle["id"]})
    result = dashboard.dispatch(cfg, state, "move_task", {"id": last["id"], "direction": "up"})
    project = [t for t in result["tasks"] if t["parent"] == "Project"]
    assert [t["title"] for t in project] == ["Last", "Middle", "First"]
    assert project[0]["notes"] == ["Last note"]
    assert project[2]["notes"] == ["First note"]
    assert [t["title"] for t in result["tasks"] if t["parent"] == "Elsewhere"] == ["Other"]
    text = daily_notes.daily_note_path(cfg.daily_dir).read_text()
    assert (text.index("Last ~15m ~optional") < text.index("Middle ~15m")
            < text.index("First ~15m ~p0"))
    unchanged = dashboard.dispatch(cfg, state, "move_task", {"id": last["id"], "direction": "up"})
    assert [t["title"] for t in unchanged["tasks"] if t["parent"] == "Project"] == [
        "Last", "Middle", "First",
    ]


def test_reordered_existing_tasks_keep_order_on_next_carryover(cfg, state, clock):
    start(cfg, state)
    add(cfg, state, title="First", parent="Project")
    add(cfg, state, title="Second", parent="Project", optional=True)
    dashboard.dispatch(cfg, state, "wrap", {})

    clock.advance(days=1)
    carried = dashboard.dispatch(cfg, state, "morning", {"carryover": True})
    project = [t for t in carried["tasks"] if t["parent"] == "Project"]
    assert [t["title"] for t in project] == ["First", "Second"]
    dashboard.dispatch(cfg, state, "move_task", {"id": project[1]["id"], "direction": "up"})
    dashboard.dispatch(cfg, state, "wrap", {})
    assert task_notes.generate_daily_subtasks(cfg, "Project").splitlines() == [
        "- [ ] Second ~15m ~optional", "- [ ] First ~15m",
    ]
