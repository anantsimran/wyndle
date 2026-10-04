"""Task edits in Markdown notes, independent of the browser and HTTP server."""

from pathlib import Path

from wyndle.lib import daily_notes, task_notes
from wyndle.lib.config import WyndleConfig
from wyndle.lib.markdown_dom import MarkdownDoc, format_task_text
from wyndle.lib.models import SubTask


def add_group(cfg: WyndleConfig, name: str) -> str:
    """Create an empty high-level task, or return its existing canonical name."""
    daily = cfg.daily_dir
    path = daily_notes.daily_note_path(daily)
    doc = MarkdownDoc(path.read_text())
    details = doc.find_section("Task Details", level=2)
    if details is None or doc.find_section("High Level Tasks", level=2) is None:
        raise ValueError("The daily note needs High Level Tasks and Task Details sections.")
    existing = next((t.text for t in daily_notes.get_high_level_tasks(daily)
                     if t.text.casefold() == name.casefold()), None)
    block = doc.find_subsection(details, name)
    name = existing or (block.title if block else name)
    if not existing and name != "Daily Chores":
        daily_notes.write_high_level_tasks(daily, [name])
    if block is None:
        daily_notes.write_task_details(daily, name, "")
    return name


def add_subtask(cfg: WyndleConfig, title: str, parent: str, estimate: int,
                priority: bool = False, optional: bool = False) -> None:
    """Add a subtask checkbox to today's daily note."""
    daily = cfg.daily_dir
    parent = add_group(cfg, parent)
    path = daily_notes.daily_note_path(daily)
    doc = MarkdownDoc(path.read_text())
    details = doc.find_section("Task Details", level=2)
    block = doc.find_subsection(details, parent) if details else None
    content = "\n".join(block.content) if block else ""
    line = f"- [ ] {format_task_text(title, estimate, priority, optional)}"
    daily_notes.write_task_details(daily, parent, content.rstrip() + "\n" + line + "\n")
    set_parent_done(daily, parent, False)


def update_subtask(daily: Path, sub: SubTask, *, estimate: int | None = None,
                   priority: bool | None = None, optional: bool | None = None,
                   started: int | None = None,
                   ended: int | None = None, elapsed: int | None = None) -> None:
    """Edit one checkbox's metadata without disturbing its notes or neighbors."""
    path = daily_notes.daily_note_path(daily)
    doc = MarkdownDoc(path.read_text())
    details = doc.find_section("Task Details", level=2)
    block = doc.find_subsection(details, sub.parent) if details else None
    if block is None:
        raise ValueError("That task changed. Refresh and try again.")
    for idx, _, text in doc.get_checkboxes(block):
        if text != sub.text:
            continue
        line = block.content[idx]
        prefix = line[:line.index("] ") + 2]
        block.content[idx] = prefix + format_task_text(
            text, sub.estimate_min if estimate is None else estimate,
            sub.priority if priority is None else priority,
            sub.optional if optional is None else optional,
            started=sub.started_at if started is None else started,
            ended=sub.ended_at if ended is None else ended,
            elapsed=sub.saved_elapsed if elapsed is None else elapsed,
        )
        path.write_text(doc.serialize())
        return
    raise ValueError("That task changed. Refresh and try again.")


def reorder_subtasks(daily: Path, first: SubTask, second: SubTask) -> None:
    """Swap two checkboxes in one group, including each task's indented notes."""
    if first.parent != second.parent:
        raise ValueError("Tasks must belong to the same high-level task.")
    path = daily_notes.daily_note_path(daily)
    doc = MarkdownDoc(path.read_text())
    details = doc.find_section("Task Details", level=2)
    block = doc.find_subsection(details, first.parent) if details else None
    if block is None:
        raise ValueError("That task changed. Refresh and try again.")
    checkboxes = doc.get_checkboxes(block)
    starts = [idx for idx, _, _ in checkboxes]
    texts = [text for _, _, text in checkboxes]
    if (first.line_num not in starts or second.line_num not in starts
            or texts[starts.index(first.line_num)] != first.text
            or texts[starts.index(second.line_num)] != second.text):
        raise ValueError("That task changed. Refresh and try again.")
    chunks = [block.content[start:starts[i + 1] if i + 1 < len(starts)
                            else len(block.content)] for i, start in enumerate(starts)]
    a, b = starts.index(first.line_num), starts.index(second.line_num)
    chunks[a], chunks[b] = chunks[b], chunks[a]
    block.content = block.content[:starts[0]] + [line for chunk in chunks for line in chunk]
    path.write_text(doc.serialize())


def set_parent_done(daily: Path, parent: str, done: bool) -> None:
    """Update a high-level checkbox without changing sibling content."""
    path = daily_notes.daily_note_path(daily)
    doc = MarkdownDoc(path.read_text())
    high = doc.find_section("High Level Tasks", level=2)
    if high:
        for idx, checked, title in doc.get_checkboxes(high):
            if title.casefold() == parent.casefold() and checked != done:
                old, new = ("[ ]", "[x]") if done else ("[x]", "[ ]")
                high.content[idx] = high.content[idx].replace("[X]", "[x]").replace(old, new, 1)
        path.write_text(doc.serialize())


def append_subtask_note(daily: Path, sub: SubTask, note: str) -> None:
    """Write an indented note beneath a subtask checkbox."""
    path = daily_notes.daily_note_path(daily)
    doc = MarkdownDoc(path.read_text())
    block = doc.find_subsection(doc.find_section("Task Details", level=2), sub.parent)
    block.content.insert(sub.line_num + 1, f"  - {note}")
    path.write_text(doc.serialize())


def _archive_subtasks(cfg: WyndleConfig, parent: str, names: set[str]) -> None:
    """Preserve saved history but keep removed subtasks out of future carryover."""
    if not task_notes.task_note_path(cfg, parent).exists():
        return
    note = task_notes.read_task_note(cfg, parent)
    changed = False
    for sub in note.subtasks:
        if sub.name in names and sub.status != "done":
            sub.status = "deferred"
            changed = True
    if changed:
        task_notes.write_task_note(cfg, note)


def delete_subtask(cfg: WyndleConfig, sub: SubTask) -> None:
    """Remove a checkbox and its indented notes, retaining sibling content."""
    path = daily_notes.daily_note_path(cfg.daily_dir)
    doc = MarkdownDoc(path.read_text())
    details = doc.find_section("Task Details", level=2)
    block = doc.find_subsection(details, sub.parent)
    start = sub.line_num
    indent = len(block.content[start].expandtabs()) - len(block.content[start].lstrip())
    end = start + 1
    while end < len(block.content):
        line = block.content[end]
        if line.strip() and len(line.expandtabs()) - len(line.lstrip()) <= indent:
            break
        end += 1
    _archive_subtasks(cfg, sub.parent, {sub.display_text})
    del block.content[start:end]
    path.write_text(doc.serialize())


def delete_group(cfg: WyndleConfig, parent: str) -> None:
    """Remove the high-level checkbox and its entire Task Details subtree."""
    daily = cfg.daily_dir
    path = daily_notes.daily_note_path(daily)
    doc = MarkdownDoc(path.read_text())
    high = doc.find_section("High Level Tasks", level=2)
    if high:
        for idx, _, text in reversed(doc.get_checkboxes(high)):
            if text.casefold() == parent.casefold():
                del high.content[idx]
    details = doc.find_section("Task Details", level=2)
    block = doc.find_subsection(details, parent) if details else None
    if block:
        doc.remove_subsection(block)
    # Persistent history is intentionally kept; this group is no longer in carryover.
    path.write_text(doc.serialize())
