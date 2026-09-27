from wyndle.lib import obsidian
from wyndle.lib.markdown_dom import MarkdownDoc


def _daily(cfg, date_str, body):
    path = cfg.obsidian_daily_dir / f"{date_str}.md"
    path.write_text(body)
    return path


def test_create_daily_note_uses_template(cfg, clock):
    path = obsidian.create_daily_note(cfg.obsidian_daily_dir)
    assert path.name == "2026-04-07.md"
    doc = MarkdownDoc(path.read_text())
    assert doc.frontmatter.data["day"] == "Tuesday"
    assert obsidian.get_high_level_tasks(cfg.obsidian_daily_dir) == []  # placeholder skipped


def test_log_goes_to_log_section_not_shutdown_notes(cfg, clock):
    daily = cfg.obsidian_daily_dir
    obsidian.log_to_daily(daily, "first")
    obsidian.log_to_daily(daily, "second")
    doc = MarkdownDoc(obsidian.daily_note_path(daily).read_text())
    log = [line for line in doc.find_section("Log", level=2).content if line.startswith("- ")]
    assert [line.split("— ")[1] for line in log] == ["first", "second"]
    shutdown = doc.find_section("Shutdown Notes", level=2).content
    assert not any("first" in line for line in shutdown)


def test_write_high_level_tasks_replaces_placeholder_and_dedupes(cfg, clock):
    daily = cfg.obsidian_daily_dir
    obsidian.create_daily_note(daily)
    obsidian.write_high_level_tasks(daily, ["Auth", "Docs"])
    obsidian.write_high_level_tasks(daily, ["auth", "Tests"])
    assert [t.text for t in obsidian.get_high_level_tasks(daily)] == ["Auth", "Docs", "Tests"]


def test_task_details_write_read_and_prefix_names(cfg, clock):
    daily = cfg.obsidian_daily_dir
    obsidian.create_daily_note(daily)
    obsidian.write_task_details(daily, "Auth", "- [ ] Read docs ~30m\n  - a note")
    obsidian.write_task_details(daily, "Auth refactor", "- [ ] Split ~45m")
    obsidian.write_task_details(daily, "Chores", "- [ ] Slack ~15m", prepend=True)
    # Rewriting "Auth refactor" must not clobber "Auth".
    obsidian.write_task_details(daily, "Auth refactor", "- [ ] Split ~60m")

    doc = MarkdownDoc(obsidian.daily_note_path(daily).read_text())
    details = doc.find_section("Task Details", level=2)
    assert [s.title for s in doc.get_subsections(details)] == ["Chores", "Auth", "Auth refactor"]
    auth = obsidian.get_task_details(daily, "Auth")
    assert [(s.display_text, s.estimate_min) for s in auth] == [("Read docs", 30)]
    assert obsidian.get_task_details(daily, "Auth refactor")[0].estimate_min == 60
    assert obsidian.read_subtask_notes(daily, "Auth") == {"Read docs": ["a note"]}


def test_mark_subtask_done(cfg, clock):
    daily = cfg.obsidian_daily_dir
    obsidian.create_daily_note(daily)
    obsidian.write_task_details(daily, "Auth", "- [ ] Read docs ~30m")
    assert obsidian.mark_subtask_done(daily, "Read docs ~30m")
    assert obsidian.get_task_details(daily, "Auth")[0].done
    assert not obsidian.mark_subtask_done(daily, "Read docs ~30m")


def test_previous_note_skips_gaps(cfg, clock):
    daily = cfg.obsidian_daily_dir
    clock.set("2026-04-06T09:00:00")  # Monday
    _daily(cfg, "2026-04-02", "")
    _daily(cfg, "2026-04-03", "")  # Friday
    (daily / "notes.md").write_text("")  # non-date files are ignored
    obsidian.create_daily_note(daily)  # today is never "previous"
    assert obsidian.previous_note_date(daily) == "2026-04-03"


def test_yesterday_remaining_and_wrap_after_weekend(cfg, clock):
    _daily(cfg, "2026-04-03", (
        "## High Level Tasks\n- [x] Done thing\n- [ ] Open thing\n"
        "## Shutdown Notes\n> Day: good\nTomorrow: X\n"
    ))
    clock.set("2026-04-06T09:00:00")
    daily = cfg.obsidian_daily_dir
    assert obsidian.get_yesterday_remaining(daily) == ["Open thing"]
    assert obsidian.get_yesterday_wrap(daily) == "Day: good\nTomorrow: X"


def test_remaining_estimate(cfg, clock):
    daily = cfg.obsidian_daily_dir
    obsidian.create_daily_note(daily)
    obsidian.write_high_level_tasks(daily, ["Auth"])
    obsidian.write_task_details(daily, "Auth", "- [ ] A ~30m\n- [x] B ~20m\n- [ ] C ~15m")
    assert obsidian.get_remaining_estimate_min(daily) == 45
