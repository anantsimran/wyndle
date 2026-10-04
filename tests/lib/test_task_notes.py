from wyndle.lib import task_notes
from wyndle.lib.models import TaskNote, TaskNoteSubtask


def test_slug():
    assert task_notes.task_slug("Build auth flow!") == "build-auth-flow"


def test_write_read_roundtrip(cfg):
    note = TaskNote(
        name="Auth", created="2026-04-01", total_time_min=40, days_worked=["2026-04-01"],
        subtasks=[
            TaskNoteSubtask(
                name="Read docs", added="2026-04-01", estimate_min=30, started="2026-04-01",
                time_min=40, status="done", jira_link="PROJ-1",
                notes=[("good link", "open"), ("parked", "deferred")],
            ),
            TaskNoteSubtask(name="Later", estimate_min=15, status="future", optional=True),
        ],
    )
    task_notes.write_task_note(cfg, note)
    assert task_notes.read_task_note(cfg, "Auth") == note


def test_detail_lookup_is_exact(cfg):
    """A subtask whose name is a substring of another heading keeps its own details."""
    note = TaskNote(name="T", created="2026-04-01", subtasks=[
        TaskNoteSubtask(name="tasks", time_min=5),
        TaskNoteSubtask(name="Read", time_min=7),
        TaskNoteSubtask(name="Read docs", time_min=9),
    ])
    task_notes.write_task_note(cfg, note)
    read = task_notes.read_task_note(cfg, "T")
    assert [s.time_min for s in read.subtasks] == [5, 7, 9]


def test_read_legacy_format(cfg):
    task_notes.task_note_path(cfg, "Old").write_text(
        "---\ntask: Old\nstatus: open\n---\n# Old\n"
        "## Step one\n- added: 2026-03-01\n- time_min: 12\n- status: done\n"
        "- estimate_min: 10\n### Notes\n- a note\n"
    )
    [sub] = task_notes.read_task_note(cfg, "Old").subtasks
    assert (sub.name, sub.time_min, sub.status, sub.estimate_min) == ("Step one", 12, "done", 10)
    assert sub.notes == [("a note", "open")]


def test_sync_subtask_from_daily(clock):
    note = TaskNote(name="T", subtasks=[
        TaskNoteSubtask(name="Parked", status="deferred", notes=[("keep", "deferred")]),
    ])
    task_notes.sync_subtask_from_daily(note, "New", 20, True, ["n1", "n1", ""], "2026-04-07", 15)
    task_notes.sync_subtask_from_daily(note, "parked", 5, True, ["keep", "fresh"], "2026-04-07")
    new, parked = note.subtasks[1], note.subtasks[0]
    assert (new.time_min, new.status, new.estimate_min) == (20, "done", 15)
    assert new.started == "2026-04-07"
    assert new.notes == [("n1", "open")]
    assert parked.status == "deferred"  # done never overrides deferred
    assert parked.notes == [("keep", "deferred"), ("fresh", "open")]
    assert note.total_time_min == 25
    assert note.days_worked == ["2026-04-07"]
    assert note.status == "open"


def test_generate_daily_subtasks_only_open(cfg):
    task_notes.write_task_note(cfg, TaskNote(name="T", subtasks=[
        TaskNoteSubtask(name="A", estimate_min=30, notes=[("o", "open"), ("d", "deferred")]),
        TaskNoteSubtask(name="B", status="done"),
        TaskNoteSubtask(name="C", status="future"),
    ]))
    assert task_notes.generate_daily_subtasks(cfg, "T") == "- [ ] A ~30m\n  - o"


def test_optional_marker_carries_to_next_daily_note(cfg):
    task_notes.write_task_note(cfg, TaskNote(name="T", subtasks=[
        TaskNoteSubtask(name="Nice to have", estimate_min=20, optional=True),
    ]))
    assert task_notes.generate_daily_subtasks(cfg, "T") == "- [ ] Nice to have ~20m ~optional"


def test_remaining_counts_treat_untagged_as_open(cfg):
    task_notes.write_task_note(cfg, TaskNote(name="T", subtasks=[
        TaskNoteSubtask(name="A"), TaskNoteSubtask(name="B", status="future"),
    ]))
    path = task_notes.task_note_path(cfg, "T")
    path.write_text(path.read_text().replace("## Subtasks\n", "## Subtasks\n- Hand-added\n"))
    assert task_notes.get_all_remaining_counts(cfg) == (2, 1, 3)
