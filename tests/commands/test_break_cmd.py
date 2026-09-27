from wyndle.commands import break_cmd


def test_break_is_not_tracked_as_subtask_time(cfg, state, clock, answers, monkeypatch):
    seen_block_active: list[bool] = []

    def fake_timer(seconds, label):
        seen_block_active.append(state.is_block_active())
        clock.advance(seconds=seconds)

    monkeypatch.setattr(break_cmd, "timer_display", fake_timer)
    monkeypatch.setattr(break_cmd, "notify", lambda *a, **k: None)
    state.start_subtask_timer("Read docs ~30m")
    clock.advance(minutes=20)

    answers.extend(["3", "n"])  # coffee break, don't resume
    break_cmd.run(cfg, state)

    assert seen_block_active == [True]  # daemon stays quiet during the break
    assert not state.is_block_active()
    assert state.get_subtask_elapsed_min("Read docs ~30m") == 20
    # `restart` resumes the work, not the break
    assert state.get_last_subtask_text() == "Read docs ~30m"
    assert len(list(state.state_dir.glob("st_*_elapsed"))) == 1
