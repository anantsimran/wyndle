"""Persistent per-task note files -- CRUD and sync with daily notes.

Each high-level task gets a markdown file in ``vault/tasks/<slug>.md``
with a YAML frontmatter, a ``## Subtasks`` summary section, and
per-subtask detail sections.

v1.3.0 format
--------------
Summary section (one-liner per subtask)::

    ## Subtasks
    - Create action plan ~15m ~done (added: 2026-04-01)
    - Read docs ~45m ~open (added: 2026-04-01)
    - Future work ~30m ~future (added: 2026-04-02)

Detail sections::

    ## Create action plan
    - started: 2026-04-01
    - time_min: 15
    - jira_link: PROJ-123
    ### Notes
    - Found good resource ~open
    - Parked this idea ~deferred

Subtask statuses::

    open      included in daily note during carryover
    done      excluded from daily note
    deferred  excluded from daily note, stays in task note
    future    excluded from daily note, counted in status remaining

Note status tags::

    ~open      carried over to daily note
    ~deferred  kept in task note only
    ~future    kept in task note only

Sync directions::

    morning:  task note  -->  daily note   (open subtasks + open notes)
    wrap:     daily note -->  task note    (strict-match merge of notes)
"""

from __future__ import annotations

import re
from pathlib import Path

from wyndle.lib import time_utils
from wyndle.lib.config import WyndleConfig
from wyndle.lib.markdown_dom import (
    HeadingBlock,
    MarkdownDoc,
    parse_added_date,
    parse_estimate,
    parse_status_tag,
    strip_all_metadata,
)
from wyndle.lib.models import TaskNote, TaskNoteSubtask

_SLUG_RE = re.compile(r"[^a-z0-9]+")


# ---------------------------------------------------------------------------
# Slug / path helpers
# ---------------------------------------------------------------------------


def task_slug(name: str) -> str:
    """Convert a task name to a filename-safe slug.

    ``"Build auth flow"`` -> ``"build-auth-flow"``.
    """
    return _SLUG_RE.sub("-", name.lower()).strip("-")


def task_note_path(cfg: WyndleConfig, name: str) -> Path:
    """Return the filesystem path for a task note."""
    return cfg.obsidian_tasks_dir / f"{task_slug(name)}.md"


# ---------------------------------------------------------------------------
# Read / parse
# ---------------------------------------------------------------------------


def read_task_note(cfg: WyndleConfig, name: str) -> TaskNote:
    """Parse a task note file into a :class:`TaskNote`.

    Handles both v1.3.0 format (with ``## Subtasks`` summary) and
    legacy v1.2.x format (inline metadata fields).  Returns a default
    empty note if the file doesn't exist.
    """
    path = task_note_path(cfg, name)
    if not path.exists():
        return TaskNote(name=name, created=time_utils.now_date_str())
    doc = MarkdownDoc(path.read_text())
    fm = doc.frontmatter.data if doc.frontmatter else {}
    note = TaskNote(
        name=str(fm.get("task", name)),
        created=str(fm.get("created", "")),
        status=str(fm.get("status", "open")),
        total_time_min=int(fm.get("total_time_min", 0)),
        days_worked=list(fm.get("days_worked", [])),
    )
    summary = doc.find_section("Subtasks", level=2)
    if summary is not None:
        note.subtasks = _parse_new_format(doc, summary)
    else:
        note.subtasks = _parse_legacy_format(doc)
    return note


def _parse_new_format(doc: MarkdownDoc, summary: HeadingBlock) -> list[TaskNoteSubtask]:
    """Parse v1.3.0 format: summary lines + detail sections."""
    subtasks: list[TaskNoteSubtask] = []
    for line in summary.content:
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        raw = stripped[2:]
        name_clean, added = parse_added_date(raw)
        name_clean, status = parse_status_tag(name_clean)
        est = parse_estimate(name_clean)
        name = strip_all_metadata(name_clean)
        sub = TaskNoteSubtask(
            name=name, added=added, estimate_min=est,
            status=status or "open",
        )
        # Exact match: a substring search would let a subtask named e.g.
        # "tasks" resolve to the "## Subtasks" summary block itself.
        detail = next(
            (b for b in doc.blocks if b.level == 2 and b.title == name), None,
        )
        if detail is not None:
            _fill_detail_fields(detail, doc, sub)
        subtasks.append(sub)
    return subtasks


def _fill_detail_fields(
    block: HeadingBlock, doc: MarkdownDoc, sub: TaskNoteSubtask,
) -> None:
    """Populate started, time_min, jira_link, and notes from a detail block."""
    for line in block.content:
        stripped = line.strip()
        if stripped.startswith("- started:"):
            sub.started = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("- time_min:"):
            sub.time_min = int(stripped.split(":", 1)[1].strip() or "0")
        elif stripped.startswith("- jira_link:"):
            sub.jira_link = stripped.split(":", 1)[1].strip()
    notes_block = doc.find_subsection(block, "Notes")
    if notes_block is not None:
        for line in notes_block.content:
            stripped = line.strip()
            if stripped.startswith("- "):
                text = stripped[2:].strip()
                clean, tag = parse_status_tag(text)
                sub.notes.append((clean, tag or "open"))
            elif stripped:
                clean, tag = parse_status_tag(stripped)
                sub.notes.append((clean, tag or "open"))


def _parse_legacy_format(doc: MarkdownDoc) -> list[TaskNoteSubtask]:
    """Parse v1.2.x format: ``## SubtaskName`` with inline metadata fields.

    Shares the v1.3.0 detail fields; ``added``, ``status`` and
    ``estimate_min`` lived in the detail section before they moved to
    the summary line.
    """
    subtasks: list[TaskNoteSubtask] = []
    for block in doc.blocks:
        if block.level != 2 or block.title.lower() == "subtasks":
            continue
        sub = TaskNoteSubtask(name=block.title)
        _fill_detail_fields(block, doc, sub)
        for line in block.content:
            key, _, value = line.strip().removeprefix("- ").partition(":")
            value = value.strip()
            if key == "added":
                sub.added = value
            elif key == "status":
                sub.status = value or "open"
            elif key == "estimate_min":
                sub.estimate_min = int(value or "0")
        subtasks.append(sub)
    return subtasks


# ---------------------------------------------------------------------------
# Write / serialize
# ---------------------------------------------------------------------------


def write_task_note(cfg: WyndleConfig, note: TaskNote) -> None:
    """Serialize a :class:`TaskNote` to its markdown file in v1.3.0 format."""
    cfg.obsidian_tasks_dir.mkdir(parents=True, exist_ok=True)
    days = ", ".join(note.days_worked) if note.days_worked else ""
    lines: list[str] = [
        "---",
        f"task: {note.name}",
        f"created: {note.created}",
        f"status: {note.status}",
        f"total_time_min: {note.total_time_min}",
        f"days_worked: [{days}]",
        "---",
        "",
        f"# {note.name}",
        "",
    ]
    lines.extend(_serialize_summary(note.subtasks))
    lines.append("")
    for sub in note.subtasks:
        lines.extend(_serialize_detail(sub))
        lines.append("")
    task_note_path(cfg, note.name).write_text("\n".join(lines) + "\n")


def _serialize_summary(subtasks: list[TaskNoteSubtask]) -> list[str]:
    """Serialize the ``## Subtasks`` summary section."""
    lines = ["## Subtasks"]
    for sub in subtasks:
        est = f" ~{sub.estimate_min}m" if sub.estimate_min else ""
        added = f" (added: {sub.added})" if sub.added else ""
        lines.append(f"- {sub.name}{est} ~{sub.status}{added}")
    return lines


def _serialize_detail(sub: TaskNoteSubtask) -> list[str]:
    """Serialize a single subtask detail section."""
    lines = [f"## {sub.name}"]
    lines.append(f"- started: {sub.started}")
    lines.append(f"- time_min: {sub.time_min}")
    lines.append(f"- jira_link: {sub.jira_link}")
    lines.append("### Notes")
    for text, tag in sub.notes:
        lines.append(f"- {text} ~{tag}")
    if not sub.notes:
        lines.append("")
    return lines


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def create_task_note(cfg: WyndleConfig, name: str) -> Path:
    """Create a task note file if it doesn't exist.  Returns the path."""
    path = task_note_path(cfg, name)
    if not path.exists():
        write_task_note(cfg, TaskNote(name=name, created=time_utils.now_date_str()))
    return path


# ---------------------------------------------------------------------------
# Sync from daily note (called by wrap)
# ---------------------------------------------------------------------------


def sync_subtask_from_daily(
    note: TaskNote,
    subtask_name: str,
    elapsed_min: int,
    done: bool,
    daily_notes: list[str],
    today: str,
    estimate_min: int = 0,
) -> None:
    """Update a subtask in *note* with today's data from the daily note.

    Uses **strict match** for notes: each daily note line is compared
    exactly against existing note text.  If no exact match is found,
    the line is appended as a new ``~open`` note.  Existing notes with
    ``~deferred``/``~future`` tags are never modified.

    Does not overwrite ``deferred`` or ``future`` subtask status.
    """
    sub = _find_or_create_subtask(note, subtask_name, estimate_min)
    sub.time_min += elapsed_min
    if done and sub.status not in ("deferred", "future"):
        sub.status = "done"
    if daily_notes:
        _strict_merge_notes(sub, daily_notes)
    if not sub.started and (elapsed_min > 0 or daily_notes):
        sub.started = today
    note.total_time_min = sum(s.time_min for s in note.subtasks)
    if today not in note.days_worked and elapsed_min > 0:
        note.days_worked.append(today)
    if note.subtasks and all(s.status == "done" for s in note.subtasks):
        note.status = "done"


def _strict_merge_notes(sub: TaskNoteSubtask, daily_notes: list[str]) -> None:
    """Merge daily note lines into subtask notes using strict exact match.

    For each daily note line:
    - If an exact text match exists in existing notes, keep the existing
      entry (preserving its status tag).
    - If no exact match, append as new with ``~open`` tag.

    Existing notes not present in daily_notes are kept unchanged.
    """
    existing_texts = {text for text, _ in sub.notes}
    for note_line in daily_notes:
        clean = note_line.strip()
        if not clean:
            continue
        if clean not in existing_texts:
            sub.notes.append((clean, "open"))
            existing_texts.add(clean)


def _find_or_create_subtask(
    note: TaskNote, name: str, estimate_min: int = 0,
) -> TaskNoteSubtask:
    """Find a subtask by name or create it with today's date as ``added``."""
    name_lower = name.lower()
    for sub in note.subtasks:
        if sub.name.lower() == name_lower:
            return sub
    sub = TaskNoteSubtask(
        name=name, estimate_min=estimate_min,
        added=time_utils.now_date_str(),
    )
    note.subtasks.append(sub)
    return sub


# ---------------------------------------------------------------------------
# Generate daily note content (called by morning carryover)
# ---------------------------------------------------------------------------


def generate_daily_subtasks(cfg: WyndleConfig, task_name: str) -> str:
    """Generate markdown subtask lines with carried-over notes.

    Reads the task note and returns checkbox lines for all ``open``
    subtasks.  Only notes tagged ``~open`` are included.  Status tags
    are **not** written to the daily note.
    """
    note = read_task_note(cfg, task_name)
    lines: list[str] = []
    for sub in note.subtasks:
        if sub.status not in ("open",):
            continue
        est = f" ~{sub.estimate_min}m" if sub.estimate_min else ""
        lines.append(f"- [ ] {sub.name}{est}")
        for text, tag in sub.notes:
            if tag == "open":
                lines.append(f"  - {text}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Aggregate queries (for status command)
# ---------------------------------------------------------------------------


def get_all_remaining_counts(cfg: WyndleConfig) -> tuple[int, int, int]:
    """Count remaining subtasks across all task note files.

    Returns:
        Tuple of ``(open_count, future_count, total_open_and_future)``.
    """
    open_count = 0
    future_count = 0
    if not cfg.obsidian_tasks_dir.exists():
        return 0, 0, 0
    for path in cfg.obsidian_tasks_dir.glob("*.md"):
        doc = MarkdownDoc(path.read_text())
        fm = doc.frontmatter.data if doc.frontmatter else {}
        if str(fm.get("status", "open")) == "done":
            continue
        summary = doc.find_section("Subtasks", level=2)
        if summary is None:
            continue
        for line in summary.content:
            stripped = line.strip()
            if not stripped.startswith("- "):
                continue
            _, status = parse_status_tag(stripped[2:])
            # Untagged lines are "open", matching _parse_new_format.
            if status in ("open", ""):
                open_count += 1
            elif status == "future":
                future_count += 1
    return open_count, future_count, open_count + future_count
