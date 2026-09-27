"""Non-interactive day workflow shared by graphical clients.

Markdown remains the source of truth; the UI never keeps a second task database.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from wyndle.commands import morning, wrap
from wyndle.lib import daily_notes, time_utils
from wyndle.lib.config import WyndleConfig
from wyndle.lib.dashboard_tasks import add_group, delete_group, delete_subtask
from wyndle.lib.markdown_dom import MarkdownDoc
from wyndle.lib.models import WorkSummary
from wyndle.lib.state import State, _subtask_key


def _text(data: dict, key: str, *, required: bool = True) -> str:
    value = data.get(key, "")
    if not isinstance(value, str) or len(value) > 2000 or "\n" in value or "\r" in value:
        raise ValueError(f"{key} must be a single line of text (up to 2000 characters).")
    value = value.strip()
    if required and not value:
        raise ValueError(f"Please enter {key}.")
    return value


def _minutes(data: dict, key: str, default: int, minimum: int = 1) -> int:
    value = data.get(key, default)
    if type(value) is not int or not minimum <= value <= 480:
        raise ValueError(f"{key} must be between {minimum} and 480 minutes.")
    return value


def _id(sub) -> str:
    return hashlib.sha256(f"{sub.parent}\0{sub.text}".encode()).hexdigest()[:20]


def snapshot(cfg: WyndleConfig, state: State) -> dict:
    """Read today's work without resetting or syncing another day's state."""
    current = not state.is_new_day()
    active = state.get_active_subtask_text() if current else None
    tasks = []
    notes = {}
    for sub in daily_notes.get_all_subtasks(cfg.daily_dir):
        if sub.parent not in notes:
            notes[sub.parent] = daily_notes.read_subtask_notes(cfg.daily_dir, sub.parent)
        tasks.append({
            "id": _id(sub), "title": sub.display_text, "parent": sub.parent,
            "done": sub.done, "estimate": sub.estimate_min,
            "elapsed": state.get_subtask_elapsed(sub.text) if current else 0,
            "active": current and state.is_subtask_active(sub.text),
            "notes": notes[sub.parent].get(sub.display_text, []),
        })
    seconds = sum(state.get_int(p.name) for p in state.state_dir.glob("st_*_elapsed"))
    if active:
        key = _subtask_key(active)
        seconds += state.get_subtask_elapsed(active) - state.get_int(f"st_{key}_elapsed")
    kind = state.get("today_ui_kind") if current else ""
    last = state.get_last_subtask_text() if current else None
    last_id = next((t["id"] for t in tasks
                    if not t["done"] and _subtask_key(t["title"]) == _subtask_key(last or "")), "")
    # A CLI switch invalidates the browser's old focus countdown.
    if kind == "focus" and active != state.get("today_ui_task"):
        kind = ""
    return {
        "date": time_utils.now_date_str(), "now": time_utils.epoch_now(),
        "name": cfg.user_name, "notesPath": str(cfg.notes_path),
        "dailyNote": str(daily_notes.daily_note_path(cfg.daily_dir)),
        "started": current and state.get("today_started") == "true",
        "wrapped": current and state.get("today_wrapped") == "true",
        "focusedSeconds": seconds if current else 0,
        "hardStop": cfg.hard_stop,
        "minutesLeft": time_utils.minutes_until(cfg.hard_stop),
        "tasks": tasks,
        "lastTaskId": last_id,
        "groups": [t.text for t in daily_notes.get_high_level_tasks(cfg.daily_dir)],
        "highLevelTasks": [{"title": t.text, "done": t.done}
                           for t in daily_notes.get_high_level_tasks(cfg.daily_dir)],
        "timer": {"kind": kind, "end": state.get_int("today_ui_deadline") if kind else 0,
                  "duration": state.get_int("today_ui_duration") if kind else 0,
                  "title": daily_notes.strip_estimate(active or "")},
        "tomorrow": state.get("tomorrow_first_task"),
        "carryover": daily_notes.get_yesterday_remaining(cfg.daily_dir),
    }


def _pause(cfg: WyndleConfig, state: State) -> None:
    if state.get("today_ui_kind") == "break":
        elapsed = max(0, time_utils.epoch_now() - state.get_int("today_ui_started")) // 60
        daily_notes.log_to_daily(cfg.daily_dir, f"Break ended: {elapsed}m actual")
    state.pause_active_subtask()
    state.set_block_active(False)
    for key in ("kind", "deadline", "duration", "started", "task"):
        state.clear(f"today_ui_{key}")
    wrap._flush_focused_time(state)


def _start_day(cfg: WyndleConfig, state: State, data: dict) -> None:
    if not state.is_new_day() and state.get("today_started") == "true":
        return  # Repeated clicks must not reset chores or elapsed time.
    wrap.auto_wrap_yesterday(cfg, state)
    morning._init_day(state)
    cfg.ensure_dirs()
    daily_notes.create_daily_note(cfg.daily_dir)
    morning._add_chores_task(cfg)
    if data.get("carryover", True):
        existing = {t.text for t in daily_notes.get_high_level_tasks(cfg.daily_dir)}
        carried = [t for t in daily_notes.get_yesterday_remaining(cfg.daily_dir)
                   if t != "Daily Chores" and t not in existing]
        morning._carry_over_tasks(cfg, carried)
    state.set("today_started", "true")
    state.set("today_start_time", time_utils.now_time_str())
    daily_notes.log_to_daily(cfg.daily_dir, "Day started from dashboard.")


def _add_task(cfg: WyndleConfig, data: dict) -> None:
    title = _text(data, "title")
    parent = _text(data, "parent", required=False) or "Today"
    estimate = _minutes(data, "estimate", 15, 0)
    if any(_subtask_key(s.text) == _subtask_key(title)
           for s in daily_notes.get_all_subtasks(cfg.daily_dir)):
        raise ValueError("That task name already exists today. Give this one a distinct name.")
    daily = cfg.daily_dir
    parent = add_group(cfg, parent)
    path = daily_notes.daily_note_path(daily)
    doc = MarkdownDoc(path.read_text())
    details = doc.find_section("Task Details", level=2)
    block = doc.find_subsection(details, parent) if details else None
    content = "\n".join(block.content) if block else ""
    line = f"- [ ] {title}" + (f" ~{estimate}m" if estimate else "")
    daily_notes.write_task_details(daily, parent, content.rstrip() + "\n" + line + "\n")
    _set_parent_done(daily, parent, False)


def _set_parent_done(daily: Path, parent: str, done: bool) -> None:
    path = daily_notes.daily_note_path(daily)
    doc = MarkdownDoc(path.read_text())
    high = doc.find_section("High Level Tasks", level=2)
    if high:
        for idx, checked, title in doc.get_checkboxes(high):
            if title.casefold() == parent.casefold() and checked != done:
                old, new = ("[ ]", "[x]") if done else ("[x]", "[ ]")
                high.content[idx] = high.content[idx].replace("[X]", "[x]").replace(old, new, 1)
        path.write_text(doc.serialize())


def dispatch(cfg: WyndleConfig, state: State, action: str, data: dict) -> dict:
    """Apply one validated action. The HTTP layer serializes calls."""
    if action == "morning":
        _start_day(cfg, state, data)
        return snapshot(cfg, state)
    if action not in {"add", "focus", "pause", "complete", "break", "wrap", "note",
                      "add_group", "delete", "delete_group", "complete_group"}:
        raise ValueError("Unknown action.")
    if state.is_new_day() or state.get("today_started") != "true":
        raise ValueError("Start your day first.")
    if state.get("today_wrapped") == "true":
        if action == "wrap":
            return snapshot(cfg, state)
        raise ValueError("Today is wrapped. Come back tomorrow for a fresh start.")
    if action == "add":
        _add_task(cfg, data)
    elif action == "add_group":
        add_group(cfg, _text(data, "title"))
    elif action in {"delete_group", "complete_group"}:
        parent = _text(data, "parent")
        current = snapshot(cfg, state)
        names = current["groups"] + [t["parent"] for t in current["tasks"]]
        if parent not in names:
            raise ValueError("That high-level task changed. Refresh and try again.")
        subs = [s for s in daily_notes.get_all_subtasks(cfg.daily_dir) if s.parent == parent]
        if any(state.is_subtask_active(s.text) for s in subs):
            _pause(cfg, state)
        if action == "delete_group":
            delete_group(cfg, parent)
            daily_notes.log_to_daily(cfg.daily_dir, f"Deleted high-level task: **{parent}**")
        else:
            for sub in subs:
                daily_notes.mark_subtask_done(cfg.daily_dir, sub.text, parent)
            _set_parent_done(cfg.daily_dir, parent, True)
    elif action in {"focus", "complete", "note", "delete"}:
        subs = daily_notes.get_all_subtasks(cfg.daily_dir)
        sub = next((s for s in subs if _id(s) == data.get("id")), None)
        if sub is None:
            raise ValueError("That task changed. Refresh and try again.")
        if action == "focus":
            duration = _minutes(data, "minutes", cfg.timer.short_block)
            if sub.done:
                raise ValueError("This task is already complete.")
            if sum(_subtask_key(s.text) == _subtask_key(sub.text) for s in subs) > 1:
                raise ValueError("Two tasks share this name. Rename one in your daily note first.")
            _pause(cfg, state)
            state.set("today_current_task", sub.parent)
            state.start_subtask_timer(sub.text)
            _begin_timer(state, "focus", duration)
            state.set("today_ui_task", sub.text)
            daily_notes.log_to_daily(cfg.daily_dir, f"Started: **{sub.display_text}**")
        elif action == "complete":
            if state.is_subtask_active(sub.text):
                _pause(cfg, state)
            if not sub.done:
                daily_notes.mark_subtask_done(cfg.daily_dir, sub.text, sub.parent)
                remaining = daily_notes.get_task_details(cfg.daily_dir, sub.parent)
                _set_parent_done(cfg.daily_dir, sub.parent, all(s.done for s in remaining))
                daily_notes.log_to_daily(cfg.daily_dir, f"Completed: **{sub.display_text}**")
        elif action == "delete":
            if state.is_subtask_active(sub.text):
                _pause(cfg, state)
            delete_subtask(cfg, sub)
            remaining = daily_notes.get_task_details(cfg.daily_dir, sub.parent)
            _set_parent_done(cfg.daily_dir, sub.parent,
                             bool(remaining) and all(s.done for s in remaining))
            daily_notes.log_to_daily(cfg.daily_dir, f"Deleted subtask: **{sub.display_text}**")
        else:
            note = _text(data, "note")
            path = daily_notes.daily_note_path(cfg.daily_dir)
            doc = MarkdownDoc(path.read_text())
            block = doc.find_subsection(doc.find_section("Task Details", level=2), sub.parent)
            block.content.insert(sub.line_num + 1, f"  - {note}")
            path.write_text(doc.serialize())
    elif action == "pause":
        _pause(cfg, state)
    elif action == "break":
        duration = _minutes(data, "minutes", 5)
        _pause(cfg, state)
        _begin_timer(state, "break", duration)
        daily_notes.log_to_daily(cfg.daily_dir, f"Break started: {duration}m")
    elif action == "wrap":
        tomorrow = _text(data, "tomorrow", required=False)
        reflection = _text(data, "reflection", required=False)
        _pause(cfg, state)
        tasks = snapshot(cfg, state)["tasks"]
        summary = WorkSummary(
            total=len(tasks), completed=sum(t["done"] for t in tasks),
            actual_min=sum(t["elapsed"] for t in tasks) // 60,
            estimated_min=sum(t["estimate"] for t in tasks),
        )
        lines = [f"{'✓' if t['done'] else '☐'} {t['title']}  "
                 f"est: {t['estimate']}m  actual: {t['elapsed'] // 60}m" for t in tasks]
        wrap._write_shutdown_notes(cfg, state.get("today_focused_min", "0"), summary,
                                   "Reviewed", tomorrow, reflection, lines)
        wrap.sync_task_notes(cfg, state, time_utils.now_date_str())
        state.set("tomorrow_first_task", tomorrow)
        state.set("today_wrapped", "true")
    return snapshot(cfg, state)


def _begin_timer(state: State, kind: str, minutes: int) -> None:
    now = time_utils.epoch_now()
    state.set("today_ui_kind", kind)
    state.set("today_ui_started", str(now))
    state.set("today_ui_deadline", str(now + minutes * 60))
    state.set("today_ui_duration", str(minutes * 60))
    state.set_block_active(True)
