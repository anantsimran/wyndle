from wyndle.commands import start
from wyndle.lib import daily_notes


def test_close_active_subtask_marks_done_and_logs(cfg, state, clock, answers):
    daily = cfg.daily_dir
    daily_notes.create_daily_note(daily)
    daily_notes.write_task_details(daily, "Auth", "- [ ] Read docs ~30m")
    state.start_subtask_timer("Read docs ~30m")
    clock.advance(minutes=12)

    answers.append("y")
    assert start.close_active_subtask(cfg, state)
    assert daily_notes.get_task_details(daily, "Auth")[0].done
    assert "Completed: **Read docs** (12m)" in daily_notes.daily_note_path(daily).read_text()
    assert not start.close_active_subtask(cfg, state)  # nothing active anymore
