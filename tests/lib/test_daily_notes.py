from wyndle.lib import daily_notes
from wyndle.lib.markdown_dom import MarkdownDoc


def _daily(cfg, date_str, body):
    path = cfg.daily_dir / f"{date_str}.md"
    path.write_text(body)
    return path


def test_create_daily_note_uses_template(cfg, clock):
    path = daily_notes.create_daily_note(cfg.daily_dir)
    assert path.name == "2026-04-07.md"
    doc = MarkdownDoc(path.read_text())
    assert doc.frontmatter.data["day"] == "Tuesday"
    assert daily_notes.get_high_level_tasks(cfg.daily_dir) == []  # placeholder skipped


def test_completion_targets_the_right_subtask_not_a_high_level_checkbox(cfg, clock):
    daily = cfg.daily_dir
    daily_notes.create_daily_note(daily)
    daily_notes.write_high_level_tasks(daily, ["Read docs", "Auth", "API"])
    daily_notes.write_task_details(daily, "Auth", "- [ ] Read docs")
    daily_notes.write_task_details(daily, "API", "- [ ] Read docs")
    assert daily_notes.mark_subtask_done(daily, "Read docs", parent="API")
    assert not daily_notes.get_high_level_tasks(daily)[0].done
    assert not daily_notes.get_task_details(daily, "Auth")[0].done
    assert daily_notes.get_task_details(daily, "API")[0].done


def test_log_goes_to_log_section_not_shutdown_notes(cfg, clock):
    daily = cfg.daily_dir
    daily_notes.log_to_daily(daily, "first")
    daily_notes.log_to_daily(daily, "second")
    doc = MarkdownDoc(daily_notes.daily_note_path(daily).read_text())
    log = [line for line in doc.find_section("Log", level=2).content if line.startswith("- ")]
    assert [line.split("— ")[1] for line in log] == ["first", "second"]
    shutdown = doc.find_section("Shutdown Notes", level=2).content
    assert not any("first" in line for line in shutdown)


def test_write_high_level_tasks_replaces_placeholder_and_dedupes(cfg, clock):
    daily = cfg.daily_dir
    daily_notes.create_daily_note(daily)
    daily_notes.write_high_level_tasks(daily, ["Auth", "Docs"])
    daily_notes.write_high_level_tasks(daily, ["auth", "Tests"])
    assert [t.text for t in daily_notes.get_high_level_tasks(daily)] == ["Auth", "Docs", "Tests"]


def test_task_details_write_read_and_prefix_names(cfg, clock):
    daily = cfg.daily_dir
    daily_notes.create_daily_note(daily)
    daily_notes.write_task_details(daily, "Auth", "- [ ] Read docs ~30m\n  - a note")
    daily_notes.write_task_details(daily, "Auth refactor", "- [ ] Split ~45m")
    daily_notes.write_task_details(daily, "Chores", "- [ ] Slack ~15m", prepend=True)
    # Rewriting "Auth refactor" must not clobber "Auth".
    daily_notes.write_task_details(daily, "Auth refactor", "- [ ] Split ~60m")

    doc = MarkdownDoc(daily_notes.daily_note_path(daily).read_text())
    details = doc.find_section("Task Details", level=2)
    assert [s.title for s in doc.get_subsections(details)] == ["Chores", "Auth", "Auth refactor"]
    auth = daily_notes.get_task_details(daily, "Auth")
    assert [(s.display_text, s.estimate_min) for s in auth] == [("Read docs", 30)]
    assert daily_notes.get_task_details(daily, "Auth refactor")[0].estimate_min == 60
    assert daily_notes.read_subtask_notes(daily, "Auth") == {"Read docs": ["a note"]}


def test_mark_subtask_done(cfg, clock):
    daily = cfg.daily_dir
    daily_notes.create_daily_note(daily)
    daily_notes.write_task_details(daily, "Auth", "- [ ] Read docs ~30m")
    assert daily_notes.mark_subtask_done(daily, "Read docs ~30m")
    assert daily_notes.get_task_details(daily, "Auth")[0].done
    assert not daily_notes.mark_subtask_done(daily, "Read docs ~30m")


def test_previous_note_skips_gaps(cfg, clock):
    daily = cfg.daily_dir
    clock.set("2026-04-06T09:00:00")  # Monday
    _daily(cfg, "2026-04-02", "")
    _daily(cfg, "2026-04-03", "")  # Friday
    (daily / "notes.md").write_text("")  # non-date files are ignored
    daily_notes.create_daily_note(daily)  # today is never "previous"
    assert daily_notes.previous_note_date(daily) == "2026-04-03"


def test_recent_high_level_tasks_span_30_days_newest_first(cfg, clock):
    _daily(cfg, "2026-03-08", "## High Level Tasks\n- [ ] Too old\n")
    _daily(cfg, "2026-03-09", "## High Level Tasks\n- [x] Auth\n- [ ] Billing\n")
    _daily(cfg, "2026-04-06", "## High Level Tasks\n- [ ] AUTH\n")
    _daily(cfg, "2026-04-08", "## High Level Tasks\n- [ ] Future\n")
    daily_notes.create_daily_note(cfg.daily_dir)
    daily_notes.write_high_level_tasks(cfg.daily_dir, ["Today task"])
    assert daily_notes.get_recent_high_level_tasks(cfg.daily_dir) == [
        "Today task", "AUTH", "Billing",
    ]


def test_yesterday_remaining_and_wrap_after_weekend(cfg, clock):
    _daily(cfg, "2026-04-03", (
        "## High Level Tasks\n- [x] Done thing\n- [ ] Open thing\n"
        "## Shutdown Notes\n> Day: good\nTomorrow: X\n"
    ))
    clock.set("2026-04-06T09:00:00")
    daily = cfg.daily_dir
    assert daily_notes.get_yesterday_remaining(daily) == ["Open thing"]
    assert daily_notes.get_yesterday_wrap(daily) == "Day: good\nTomorrow: X"


def test_remaining_estimate(cfg, clock):
    daily = cfg.daily_dir
    daily_notes.create_daily_note(daily)
    daily_notes.write_high_level_tasks(daily, ["Auth"])
    daily_notes.write_task_details(daily, "Auth", "- [ ] A ~30m\n- [x] B ~20m\n- [ ] C ~15m")
    assert daily_notes.get_remaining_estimate_min(daily) == 45
