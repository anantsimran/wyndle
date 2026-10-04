from wyndle.lib.state import _subtask_key


def test_primitives(state):
    assert state.get("missing", "d") == "d"
    state.set("k", "5")
    assert state.get_int("k") == 5
    state.set("k", "junk")
    assert state.get_int("k", 7) == 7
    state.clear("k")
    assert not state.exists("k")


def test_subtask_key_ignores_estimate_and_case():
    assert _subtask_key("Read docs ~30m") == _subtask_key("read DOCS ~45m")
    assert _subtask_key("Read docs ~30m ~optional") == _subtask_key("read DOCS ~45m ~p0")


def test_subtask_timer_accumulates_across_pauses(state, clock):
    state.start_subtask_timer("Read docs ~30m")
    clock.advance(minutes=10)
    assert state.get_subtask_elapsed_min("Read docs") == 10  # live time counted
    assert state.pause_active_subtask() == "Read docs ~30m"
    clock.advance(minutes=30)  # paused: not counted
    state.start_subtask_timer("Read docs ~30m")
    clock.advance(minutes=5)
    assert state.get_subtask_elapsed_min("Read docs ~30m") == 15
    assert state.get_last_subtask_text() == "Read docs ~30m"


def test_starting_another_subtask_pauses_the_first(state, clock):
    state.start_subtask_timer("A")
    clock.advance(minutes=3)
    state.start_subtask_timer("B")
    clock.advance(minutes=4)
    assert state.get_subtask_elapsed_min("A") == 3
    assert state.is_subtask_active("B") and not state.is_subtask_active("A")


def test_day_lifecycle(state, clock):
    state.set("today_date", "2026-04-06")
    state.set("tomorrow_first_task", "keep me")
    state.start_subtask_timer("A")
    assert state.is_new_day()
    state.clear_day()
    assert not state.exists("today_date")
    assert not list(state.state_dir.glob("st_*"))
    assert state.get("tomorrow_first_task") == "keep me"
