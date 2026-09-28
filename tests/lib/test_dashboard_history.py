"""History shown in the dashboard comes from Markdown, including today's live state."""

from wyndle.lib.dashboard import recent_stats
from wyndle.lib.note_archive import stats as note_stats


def _daily(cfg, date, tasks, focused):
    path = cfg.daily_dir / f"{date}.md"
    path.write_text(
        "# Daily note\n\n"
        "## High Level Tasks\n- [x] Project\n\n"
        "## Task Details\n### Project\n"
        + "\n".join(tasks)
        + f"\n\n## Shutdown Notes\n> Total focused: {focused}m\n"
    )
    return path


def test_stats_count_subtasks_across_days_and_overlay_live_today(cfg, state, clock):
    # High-level checkboxes must not be counted as completed subtasks.
    _daily(cfg, "2026-04-05", ["- [x] Finished ~15m", "- [ ] Pending ~20m"], 15)
    _daily(cfg, "2026-04-06", ["- [ ] Continue ~30m"], 25)
    _daily(cfg, "2026-03-15", ["- [x] Older ~15m"], 60)
    today = _daily(cfg, "2026-04-07", ["- [x] Done ~10m", "- [ ] Current ~20m"], 0)
    state.set("today_date", "2026-04-07")
    state.set("today_started", "true")
    state.start_subtask_timer("Current ~20m")
    clock.advance(minutes=8)

    before = today.read_text()
    from_notes = note_stats(cfg, 7)
    assert from_notes["focusedMinutes"] == 40
    assert from_notes["daily"][0]["focusedMinutes"] == 0

    week = recent_stats(cfg, state, 7)
    assert week["days"] == 7
    assert (week["trackedDays"], week["focusedMinutes"]) == (3, 48)
    assert (week["completedTasks"], week["totalTasks"]) == (2, 5)
    rows = {row["date"]: row for row in week["daily"]}
    assert (rows["2026-04-05"]["focusedMinutes"], rows["2026-04-05"]["completedTasks"],
            rows["2026-04-05"]["totalTasks"]) == (15, 1, 2)
    assert (rows["2026-04-06"]["focusedMinutes"], rows["2026-04-06"]["completedTasks"],
            rows["2026-04-06"]["totalTasks"]) == (25, 0, 1)
    assert (rows["2026-04-07"]["focusedMinutes"], rows["2026-04-07"]["completedTasks"],
            rows["2026-04-07"]["totalTasks"]) == (8, 1, 2)
    assert rows["2026-04-04"]["exists"] is False
    assert today.read_text() == before

    month = recent_stats(cfg, state, 30)
    assert (month["trackedDays"], month["focusedMinutes"]) == (4, 108)
    assert (month["completedTasks"], month["totalTasks"]) == (3, 6)
