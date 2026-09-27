from wyndle.commands import wrap
from wyndle.lib import obsidian, task_notes


def _day_with_work(cfg, state, clock):
    clock.set("2026-04-06T09:00:00")
    daily = cfg.obsidian_daily_dir
    obsidian.create_daily_note(daily)
    obsidian.write_high_level_tasks(daily, ["Auth"])
    obsidian.write_task_details(daily, "Auth", "- [x] Read docs ~30m\n  - a note\n- [ ] Build ~45m")
    state.set("today_date", "2026-04-06")
    state.set("today_started", "true")
    state.start_subtask_timer("Read docs ~30m")
    clock.advance(minutes=25)
    state.pause_active_subtask()


def test_auto_wrap_syncs_once(cfg, state, clock):
    _day_with_work(cfg, state, clock)
    clock.set("2026-04-07T09:00:00")
    for _ in range(3):  # every CLI command before `morning` calls this
        wrap.auto_wrap_yesterday(cfg, state)

    note = task_notes.read_task_note(cfg, "Auth")
    read_docs = note.subtasks[0]
    assert (read_docs.name, read_docs.time_min, read_docs.status) == ("Read docs", 25, "done")
    assert read_docs.notes == [("a note", "open")]
    assert note.days_worked == ["2026-04-06"]


def test_auto_wrap_skips_same_day_and_wrapped_day(cfg, state, clock):
    _day_with_work(cfg, state, clock)
    wrap.auto_wrap_yesterday(cfg, state)  # same day
    assert not task_notes.task_note_path(cfg, "Auth").exists()
    state.set("today_wrapped", "true")
    clock.set("2026-04-07T09:00:00")
    wrap.auto_wrap_yesterday(cfg, state)
    assert not task_notes.task_note_path(cfg, "Auth").exists()


def test_wrap_run_writes_shutdown_notes_and_syncs(cfg, state, clock, answers):
    _day_with_work(cfg, state, clock)
    answers.extend(["good", "Build middleware", "nothing"])
    wrap.run(cfg, state)

    assert state.get("today_wrapped") == "true"
    assert state.get("today_focused_min") == "25"
    daily = cfg.obsidian_daily_dir
    assert "Tomorrow: Build middleware" in obsidian.daily_note_path(daily).read_text()
    assert task_notes.read_task_note(cfg, "Auth").subtasks[0].time_min == 25


def test_focused_minutes_round_after_adding_seconds(state, clock):
    for name in ("First", "Second"):
        state.start_subtask_timer(name)
        clock.advance(seconds=40)
        state.pause_active_subtask()
    wrap._flush_focused_time(state)
    assert state.get_int("today_focused_min") == 1


def test_manual_wrap_is_idempotent(cfg, state, clock, answers):
    _day_with_work(cfg, state, clock)
    answers.extend(["good", "Tomorrow", ""])
    wrap.run(cfg, state)
    wrap.run(cfg, state)
    assert task_notes.read_task_note(cfg, "Auth").subtasks[0].time_min == 25
