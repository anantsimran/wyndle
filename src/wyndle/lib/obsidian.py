"""Obsidian vault integration -- daily notes, task reading, logging.

The daily note is the **editing surface** for today's tasks.
Persistent task history lives in ``vault/tasks/`` (see :mod:`task_notes`).

v1.3.0: All parsing uses :mod:`markdown_dom` instead of regex-based
line iteration.  This decouples from Obsidian -- any markdown editor works.

Estimate format
---------------
Append ``~Xm`` to any subtask checkbox line::

    - [ ] Read OAuth docs ~30m

Note format
-----------
Indented bullets under a subtask are notes::

    - [ ] Read OAuth docs ~30m
      - Found good resource at oauth.net
"""

from __future__ import annotations

import subprocess
import sys
from datetime import timedelta
from pathlib import Path

from wyndle.lib import time_utils
from wyndle.lib.markdown_dom import (
    HeadingBlock,
    MarkdownDoc,
    parse_estimate,
    strip_estimate,
)
from wyndle.lib.models import RemainingWork, SubTask, Task

# Re-export for backward compatibility
__all__ = ["parse_estimate", "strip_estimate"]


# ---------------------------------------------------------------------------
# Daily note template
# ---------------------------------------------------------------------------


def _daily_template(today: str, day_name: str) -> str:
    """Generate the markdown template for a new daily note.

    Args:
        today:    Date string ``YYYY-MM-DD``.
        day_name: Weekday name (e.g. ``Monday``).

    Returns:
        Complete markdown string.
    """
    return f"""---
date: {today}
day: {day_name}
type: daily
---

# {day_name} — {today}

## High Level Tasks (Priority Order)
- [ ] (add tasks via `wyndle morning` or edit here)

## Task Details
<!-- Add subtasks under ### headings here -->

## Log
_Auto-logged by Wyndle_

## Shutdown Notes
> _filled by wyndle wrap_

"""


# ---------------------------------------------------------------------------
# Note path helpers
# ---------------------------------------------------------------------------


def daily_note_path(daily_dir: Path, date_str: str | None = None) -> Path:
    """Return the path to a daily note file.

    Args:
        daily_dir: Directory containing daily notes.
        date_str:  ISO date (defaults to today).
    """
    return daily_dir / f"{date_str or time_utils.now_date_str()}.md"


def create_daily_note(daily_dir: Path, chores: list[str] | None = None) -> Path:
    """Create today's daily note if it doesn't exist yet.

    Args:
        daily_dir: Directory for daily notes.
        chores:    Unused in v1.3.0 (chores added by morning command).

    Returns:
        Path to the (possibly newly created) note.
    """
    daily_dir.mkdir(parents=True, exist_ok=True)
    note_path = daily_note_path(daily_dir)
    if not note_path.exists():
        note_path.write_text(
            _daily_template(time_utils.now_date_str(), time_utils.today_weekday())
        )
    return note_path


# ---------------------------------------------------------------------------
# DOM helpers
# ---------------------------------------------------------------------------


def _load_doc(daily_dir: Path, date_str: str | None = None) -> MarkdownDoc | None:
    """Load a daily note as a MarkdownDoc, or None if missing."""
    path = daily_note_path(daily_dir, date_str)
    if not path.exists():
        return None
    return MarkdownDoc(path.read_text())


def _save_doc(daily_dir: Path, doc: MarkdownDoc, date_str: str | None = None) -> None:
    """Write a MarkdownDoc back to its daily note file."""
    path = daily_note_path(daily_dir, date_str)
    path.write_text(doc.serialize())


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def log_to_daily(daily_dir: Path, msg: str) -> None:
    """Append a timestamped log entry to today's daily note.

    Args:
        daily_dir: Directory containing daily notes.
        msg:       Message to log (may contain markdown).
    """
    note_path = create_daily_note(daily_dir)
    with open(note_path, "a") as f:
        f.write(f"- **{time_utils.now_friendly()}** — {msg}\n")


def replace_placeholder(daily_dir: Path, placeholder: str, replacement: str) -> None:
    """Replace a placeholder string in today's note (used by ``wrap``).

    Args:
        daily_dir:   Directory containing daily notes.
        placeholder: Exact string to find.
        replacement: String to substitute.
    """
    note_path = daily_note_path(daily_dir)
    if not note_path.exists():
        return
    content = note_path.read_text()
    note_path.write_text(content.replace(placeholder, replacement))


# ---------------------------------------------------------------------------
# Task reading
# ---------------------------------------------------------------------------


def get_high_level_tasks(daily_dir: Path, date_str: str | None = None) -> list[Task]:
    """Read high-level tasks from ``## High Level Tasks``.

    Args:
        daily_dir: Directory containing daily notes.
        date_str:  ISO date (defaults to today).

    Returns:
        Ordered list of :class:`Task` objects.
    """
    doc = _load_doc(daily_dir, date_str)
    if doc is None:
        return []
    section = doc.find_section("High Level Tasks", level=2)
    if section is None:
        return []
    tasks: list[Task] = []
    for idx, done, text in doc.get_checkboxes(section):
        if text.startswith("(add "):
            continue
        tasks.append(Task(text=text, done=done, line_num=idx))
    return tasks


def get_task_details(
    daily_dir: Path, task_name: str, date_str: str | None = None,
) -> list[SubTask]:
    """Read subtasks for *task_name* from ``## Task Details``.

    Matches ``### <heading>`` case-insensitively against *task_name*.

    Args:
        daily_dir: Directory containing daily notes.
        task_name: High-level task name.
        date_str:  ISO date (defaults to today).

    Returns:
        Ordered list of :class:`SubTask` objects.
    """
    doc = _load_doc(daily_dir, date_str)
    if doc is None:
        return []
    details = doc.find_section("Task Details", level=2)
    if details is None:
        return []
    sub_block = doc.find_subsection(details, task_name)
    if sub_block is None:
        return []
    subtasks: list[SubTask] = []
    for idx, done, text in doc.get_checkboxes(sub_block):
        subtasks.append(SubTask(
            text=text,
            display_text=strip_estimate(text),
            done=done,
            line_num=idx,
            estimate_min=parse_estimate(text),
        ))
    return subtasks


def read_subtask_notes(
    daily_dir: Path, task_name: str, date_str: str | None = None,
) -> dict[str, list[str]]:
    """Read indented bullet notes under each subtask for *task_name*.

    Returns ``{display_text: [note_line, ...]}``.

    Args:
        daily_dir: Directory containing daily notes.
        task_name: High-level task name.
        date_str:  ISO date (defaults to today).
    """
    doc = _load_doc(daily_dir, date_str)
    if doc is None:
        return {}
    details = doc.find_section("Task Details", level=2)
    if details is None:
        return {}
    sub_block = doc.find_subsection(details, task_name)
    if sub_block is None:
        return {}
    return doc.get_checkbox_notes(sub_block)


# ---------------------------------------------------------------------------
# Task writing
# ---------------------------------------------------------------------------


def write_high_level_tasks(daily_dir: Path, tasks: list[str]) -> None:
    """Append new high-level tasks to today's note.

    Removes the default placeholder line if present.

    Args:
        daily_dir: Directory containing daily notes.
        tasks:     List of task labels to append.
    """
    doc = _load_doc(daily_dir)
    if doc is None:
        return
    section = doc.find_section("High Level Tasks", level=2)
    if section is None:
        return
    section.content = [
        line for line in section.content
        if "(add tasks via" not in line
    ]
    section.content.extend(f"- [ ] {t}" for t in tasks)
    _save_doc(daily_dir, doc)


def write_task_details(
    daily_dir: Path, task_name: str, content: str, *, prepend: bool = False,
) -> None:
    """Write or replace a ``### task_name`` block in Task Details.

    Args:
        daily_dir: Directory containing daily notes.
        task_name: Heading text for the ``###`` section.
        content:   Markdown content (checkbox lines + notes).
        prepend:   If True, insert as the first subsection.
    """
    doc = _load_doc(daily_dir)
    if doc is None:
        return
    details = doc.find_section("Task Details", level=2)
    if details is None:
        return
    existing = doc.find_subsection(details, task_name)
    new_block = HeadingBlock(
        level=3, title=task_name,
        heading_line=f"### {task_name}",
        content=content.splitlines() if content else [],
    )
    if existing is not None:
        doc.remove_subsection(details, existing)
    subs = doc.get_subsections(details)
    if prepend and subs:
        doc.insert_before(subs[0], new_block)
    elif subs:
        doc.insert_after(subs[-1], new_block)
    else:
        doc.insert_after(details, new_block)
    _save_doc(daily_dir, doc)


def mark_subtask_done(daily_dir: Path, subtask_text: str) -> bool:
    """Check off a subtask in today's daily note (``[ ]`` -> ``[x]``).

    Args:
        daily_dir:    Directory containing daily notes.
        subtask_text: Raw subtask text to match.

    Returns:
        ``True`` if the checkbox was found and updated.
    """
    note_path = daily_note_path(daily_dir)
    if not note_path.exists():
        return False
    lines = note_path.read_text().splitlines()
    target = subtask_text.strip()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("- [ ] ") and stripped[6:].strip() == target:
            lines[i] = line.replace("- [ ] ", "- [x] ", 1)
            note_path.write_text("\n".join(lines) + "\n")
            return True
    return False


# ---------------------------------------------------------------------------
# Aggregate queries
# ---------------------------------------------------------------------------


def get_task_estimate(daily_dir: Path, task_name: str) -> int:
    """Sum of ``~Xm`` estimates for *task_name*'s subtasks."""
    return sum(s.estimate_min for s in get_task_details(daily_dir, task_name))


def get_all_subtasks(daily_dir: Path) -> list[SubTask]:
    """Get every subtask across all tasks, with ``parent`` set.

    Used by ``wyndle switch`` for a flat list.
    """
    all_subs: list[SubTask] = []
    for task in get_high_level_tasks(daily_dir):
        for s in get_task_details(daily_dir, task.text):
            s.parent = task.text
            all_subs.append(s)
    return all_subs


def get_remaining_tasks(daily_dir: Path) -> RemainingWork:
    """Snapshot of all uncompleted work for today."""
    high = [t for t in get_high_level_tasks(daily_dir) if not t.done]
    details: dict[str, list[SubTask]] = {}
    for task in high:
        remaining = [s for s in get_task_details(daily_dir, task.text) if not s.done]
        if remaining:
            details[task.text] = remaining
    return RemainingWork(high_level=high, details=details)


def get_remaining_estimate_min(daily_dir: Path) -> int:
    """Sum of estimates for all uncompleted subtasks."""
    remaining = get_remaining_tasks(daily_dir)
    return sum(s.estimate_min for subs in remaining.details.values() for s in subs)


# ---------------------------------------------------------------------------
# Yesterday helpers
# ---------------------------------------------------------------------------


def _yesterday_date_str(daily_dir: Path) -> str | None:
    """Return yesterday's ISO date if the note file exists, else None."""
    yesterday = (time_utils.now().date() - timedelta(days=1)).isoformat()
    path = daily_dir / f"{yesterday}.md"
    return yesterday if path.exists() else None


def get_yesterday_wrap(daily_dir: Path) -> str | None:
    """Read shutdown notes from yesterday's daily note."""
    date_str = _yesterday_date_str(daily_dir)
    if date_str is None:
        return None
    doc = _load_doc(daily_dir, date_str)
    if doc is None:
        return None
    section = doc.find_section("Shutdown Notes", level=2)
    if section is None:
        return None
    lines = [
        l.strip().lstrip("> ").strip()
        for l in section.content
        if l.strip() and l.strip() != "> _filled by wyndle wrap_"
    ]
    return "\n".join(lines) if lines else None


def get_yesterday_remaining(daily_dir: Path) -> list[str]:
    """Get uncompleted high-level task texts from yesterday."""
    date_str = _yesterday_date_str(daily_dir)
    if date_str is None:
        return []
    tasks = get_high_level_tasks(daily_dir, date_str)
    return [t.text for t in tasks if not t.done]


# ---------------------------------------------------------------------------
# Open in editor
# ---------------------------------------------------------------------------


def open_daily_note(vault_path: Path, daily_dir: Path) -> None:
    """Open today's daily note in the Obsidian app (macOS).

    Falls back to printing the path on non-macOS systems.
    """
    note = create_daily_note(daily_dir)
    if sys.platform != "darwin":
        print(f"  Open manually: {note}")
        return
    vault_name = vault_path.name
    file_path = str(note.relative_to(vault_path)).replace(".md", "")
    uri = f"obsidian://open?vault={vault_name}&file={file_path}"
    try:
        subprocess.run(["open", uri], check=False, capture_output=True)
    except OSError:
        subprocess.run(["open", str(note)], check=False, capture_output=True)
