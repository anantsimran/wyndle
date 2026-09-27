from wyndle.commands import morning
from wyndle.lib import obsidian, task_notes
from wyndle.lib.markdown_dom import MarkdownDoc

FRIDAY_NOTE = """## High Level Tasks (Priority Order)
- [x] Finished thing
- [ ] Auth

## Task Details
### Auth
- [x] Read docs ~30m
- [ ] Build middleware ~45m
  - use the new session store

## Log

## Shutdown Notes
> _filled by wyndle wrap_
"""


def _friday(cfg, clock):
    clock.set("2026-04-03T18:00:00")
    (cfg.obsidian_daily_dir / "2026-04-03.md").write_text(FRIDAY_NOTE)


def test_carryover_after_weekend(cfg, state, clock, answers):
    _friday(cfg, clock)
    clock.set("2026-04-06T09:45:00")  # Monday: no note for "yesterday" (Sunday)
    answers.extend(["y", "New task", ""])
    morning.run(cfg, state)

    daily = cfg.obsidian_daily_dir
    assert [t.text for t in obsidian.get_high_level_tasks(daily)] == ["Auth", "New task"]
    subs = obsidian.get_task_details(daily, "Auth")
    assert [(s.display_text, s.estimate_min) for s in subs] == [("Build middleware", 45)]
    assert obsidian.read_subtask_notes(daily, "Auth") == {
        "Build middleware": ["use the new session store"],
    }
    assert task_notes.task_note_path(cfg, "New task").exists()
    assert state.get("today_started") == "true"


def test_carryover_prefers_task_note(cfg, state, clock, answers):
    _friday(cfg, clock)
    task_notes.write_task_note(cfg, task_notes.TaskNote(name="Auth", subtasks=[
        task_notes.TaskNoteSubtask(name="From task note", estimate_min=10),
    ]))
    clock.set("2026-04-06T09:45:00")
    answers.extend(["y", ""])
    morning.run(cfg, state)
    subs = obsidian.get_task_details(cfg.obsidian_daily_dir, "Auth")
    assert [s.display_text for s in subs] == ["From task note"]


def test_declining_carryover(cfg, state, clock, answers):
    _friday(cfg, clock)
    clock.set("2026-04-06T09:45:00")
    answers.extend(["n", ""])
    morning.run(cfg, state)
    assert obsidian.get_high_level_tasks(cfg.obsidian_daily_dir) == []


def test_chores_are_first_detail_section_and_log_is_in_log(cfg, state, clock, answers):
    answers.extend(["Auth", ""])
    morning.run(cfg, state)
    doc = MarkdownDoc(obsidian.daily_note_path(cfg.obsidian_daily_dir).read_text())
    details = doc.find_section("Task Details", level=2)
    assert [s.title for s in doc.get_subsections(details)][0] == "Daily Chores"
    log = "\n".join(doc.find_section("Log", level=2).content)
    assert "Day started. Tasks: Auth" in log


def test_running_morning_twice_does_not_duplicate(cfg, state, clock, answers):
    answers.extend(["Auth", "", "Auth", ""])
    morning.run(cfg, state)
    morning.run(cfg, state)
    assert [t.text for t in obsidian.get_high_level_tasks(cfg.obsidian_daily_dir)] == ["Auth"]
