"""Read saved Markdown notes and summarize daily notes without UI state."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from wyndle.lib import time_utils
from wyndle.lib.config import WyndleConfig
from wyndle.lib.daily_notes import extract_day_times, extract_focused_minutes
from wyndle.lib.markdown_dom import MarkdownDoc


def _note_dir(cfg: WyndleConfig, kind: str) -> Path:
    directories = {"daily": cfg.daily_dir, "tasks": cfg.tasks_dir, "weekly": cfg.weekly_dir}
    try:
        return directories[kind]
    except KeyError as exc:
        raise ValueError("Unknown note kind.") from exc


def _note_path(cfg: WyndleConfig, kind: str, name: str) -> Path:
    directory = _note_dir(cfg, kind)
    if (not name or name == ".md" or not name.endswith(".md")
            or Path(name).name != name or "\\" in name
            or any(ord(char) < 32 for char in name)):
        raise ValueError("Expected a Markdown note filename.")
    path = directory / name
    # A note may only reveal a file directly inside its configured folder.
    if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
        raise ValueError("Invalid note path.")
    return path


def _title(markdown: str, name: str) -> str:
    doc = MarkdownDoc(markdown)
    return next((block.title for block in doc.blocks if block.level == 1), Path(name).stem)


def read_note(cfg: WyndleConfig, kind: str, name: str) -> dict:
    """Return one note by kind and basename without exposing its full path."""
    path = _note_path(cfg, kind, name)
    if not path.is_file():
        raise FileNotFoundError(name)
    markdown = path.read_text()
    return {"kind": kind, "name": name, "title": _title(markdown, name),
            "markdown": markdown}


def list_notes(cfg: WyndleConfig) -> dict:
    """List Markdown notes in each configured notes folder."""
    result: dict[str, list[dict[str, str]]] = {}
    for kind in ("daily", "tasks", "weekly"):
        directory = _note_dir(cfg, kind)
        entries = []
        if directory.is_dir():
            for path in sorted(directory.glob("*.md"), reverse=kind != "tasks"):
                # Do not expose files reached through an in-folder symlink.
                if path.is_symlink() or not path.is_file():
                    continue
                markdown = path.read_text()
                entries.append({"name": path.name, "title": _title(markdown, path.name)})
        result[kind] = entries
    return result


def _subtask_counts(doc: MarkdownDoc) -> tuple[int, int]:
    """Count the completed and total checkboxes under Task Details."""
    details = doc.find_section("Task Details", level=2)
    if details is None:
        return 0, 0
    checkboxes = [checkbox for block in doc.get_subsections(details)
                  for checkbox in doc.get_checkboxes(block)]
    return sum(done for _, done, _ in checkboxes), len(checkboxes)


def stats(cfg: WyndleConfig, days: int = 7) -> dict:
    """Summarize recent daily notes without reading live timer state."""
    if days not in (7, 30):
        raise ValueError("days must be 7 or 30.")
    today = time_utils.now().date()
    daily = []
    for offset in range(days):
        day = (today - timedelta(days=offset)).isoformat()
        path = cfg.daily_dir / f"{day}.md"
        row = {"date": day, "exists": path.is_file() and not path.is_symlink(),
               "focusedMinutes": 0,
               "completedTasks": 0, "totalTasks": 0, "startTime": "", "endTime": ""}
        if row["exists"]:
            doc = MarkdownDoc(path.read_text())
            row["startTime"], row["endTime"] = extract_day_times(doc)
            row["focusedMinutes"] = extract_focused_minutes(doc)
            row["completedTasks"], row["totalTasks"] = _subtask_counts(doc)
        daily.append(row)

    return {"days": days,
            "trackedDays": sum(row["exists"] for row in daily),
            "focusedMinutes": sum(row["focusedMinutes"] for row in daily),
            "completedTasks": sum(row["completedTasks"] for row in daily),
            "totalTasks": sum(row["totalTasks"] for row in daily),
            "daily": daily}
