from wyndle.commands import start
from wyndle.lib import obsidian


def test_close_active_subtask_marks_done_and_logs(cfg, state, clock, answers):
    daily = cfg.obsidian_daily_dir
    obsidian.create_daily_note(daily)
    obsidian.write_task_details(daily, "Auth", "- [ ] Read docs ~30m")
    state.start_subtask_timer("Read docs ~30m")
    clock.advance(minutes=12)

    answers.append("y")
    assert start.close_active_subtask(cfg, state)
    assert obsidian.get_task_details(daily, "Auth")[0].done
    assert "Completed: **Read docs** (12m)" in obsidian.daily_note_path(daily).read_text()
    assert not start.close_active_subtask(cfg, state)  # nothing active anymore
