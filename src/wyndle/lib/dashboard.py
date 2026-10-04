"""Non-interactive day workflow shared by graphical clients.

Markdown remains the source of truth; the UI never keeps a second task database.
"""

from __future__ import annotations

import hashlib

from wyndle.commands import morning, wrap
from wyndle.lib import daily_alarm, daily_notes, time_utils
from wyndle.lib.config import WyndleConfig
from wyndle.lib.daily_note_ops import (
    add_group,
    add_subtask,
    append_subtask_note,
    delete_group,
    delete_subtask,
    reorder_subtasks,
    set_parent_done,
    update_subtask,
)
from wyndle.lib.models import WorkSummary
from wyndle.lib.note_archive import stats as note_stats
from wyndle.lib.state import State, _subtask_key


def _text(data: dict, key: str, *, required: bool = True) -> str:
    value = data.get(key, "")
    if not isinstance(value, str) or len(value) > 2000 or "\n" in value or "\r" in value:
        raise ValueError(f"{key} must be a single line of text (up to 2000 characters).")
    value = value.strip()
    if required and not value:
        raise ValueError(f"Please enter {key}.")
    return value


def _minutes(data: dict, key: str, default: int, minimum: int = 1,
             maximum: int = 480) -> int:
    value = data.get(key, default)
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{key} must be between {minimum} and {maximum} minutes.")
    return value


def _id(sub) -> str:
    return hashlib.sha256(f"{sub.parent}\0{sub.display_text.casefold()}".encode()).hexdigest()[:20]


def _carryover_names(cfg: WyndleConfig) -> list[str]:
    """Return eligible unfinished high-level tasks from the previous note."""
    names = []
    seen = {"daily chores"}
    for name in daily_notes.get_yesterday_remaining(cfg.daily_dir):
        if name.casefold() not in seen:
            names.append(name)
            seen.add(name.casefold())
    return names


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
            "priority": sub.priority,
            "optional": sub.optional,
            "elapsed": max(state.get_subtask_elapsed(sub.text), sub.saved_elapsed) if current
                       else sub.saved_elapsed,
            "startedAt": (state.get_subtask_started(sub.text) or sub.started_at) if current
                         else sub.started_at,
            "endedAt": sub.ended_at,
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
        "serverTime": time_utils.now_time_str(),
        "name": cfg.user_name, "notesPath": str(cfg.notes_path),
        "dailyNote": str(daily_notes.daily_note_path(cfg.daily_dir)),
        "started": current and state.get("today_started") == "true",
        "wrapped": current and state.get("today_wrapped") == "true",
        "focusedSeconds": seconds if current else 0,
        "hardStop": cfg.hard_stop,
        "minutesLeft": time_utils.minutes_until(cfg.hard_stop),
        "tasks": tasks,
        "dailyAlarm": daily_alarm.read_plan(state, tasks) if current else None,
        "lastTaskId": last_id,
        "groups": [t.text for t in daily_notes.get_high_level_tasks(cfg.daily_dir)],
        "highLevelTasks": [{"title": t.text, "done": t.done}
                           for t in daily_notes.get_high_level_tasks(cfg.daily_dir)],
        "recentGroups": daily_notes.get_recent_high_level_tasks(cfg.daily_dir),
        "timer": {"kind": kind, "end": state.get_int("today_ui_deadline") if kind else 0,
                  "duration": state.get_int("today_ui_duration") if kind else 0,
                  "title": daily_notes.strip_estimate(active or "")},
        "tomorrow": state.get("tomorrow_first_task"),
        "carryover": _carryover_names(cfg),
    }


def recent_stats(cfg: WyndleConfig, state: State, days: int = 7) -> dict:
    """Add today's live timer and task state to the Markdown history."""
    history = note_stats(cfg, days)
    if state.is_new_day() or state.get("today_started") != "true":
        return history
    current = snapshot(cfg, state)
    today = history["daily"][0]
    live = {"focusedMinutes": current["focusedSeconds"] // 60,
            "completedTasks": sum(task["done"] for task in current["tasks"]),
            "totalTasks": len(current["tasks"])}
    for key, value in live.items():
        history[key] += value - today[key]
        today[key] = value
    return history


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
    available = _carryover_names(cfg)
    requested = data.get("carryover", True)
    if type(requested) is bool:
        selected = set(available if requested else [])
    elif isinstance(requested, list):
        if any(type(name) is not str or name not in available for name in requested):
            raise ValueError("Choose carryover tasks from the unfinished high-level tasks.")
        if len({name.casefold() for name in requested}) != len(requested):
            raise ValueError("A carryover task can only be selected once.")
        selected = set(requested)
    else:
        raise ValueError("carryover must be true, false, or a list of high-level task names.")
    wrap.auto_wrap_yesterday(cfg, state)
    morning._init_day(state)
    cfg.ensure_dirs()
    daily_notes.create_daily_note(cfg.daily_dir)
    morning._add_chores_task(cfg)
    if selected:
        existing = {t.text.casefold() for t in daily_notes.get_high_level_tasks(cfg.daily_dir)}
        carried = [name for name in available
                   if name in selected and name.casefold() not in existing]
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
    priority = data.get("priority", False)
    optional = data.get("optional", False)
    if type(priority) is not bool:
        raise ValueError("priority must be true or false.")
    if type(optional) is not bool:
        raise ValueError("optional must be true or false.")
    if priority and optional:
        raise ValueError("A task cannot be both P0 and optional.")
    add_subtask(cfg, title, parent, estimate, priority, optional)


def _complete_subtask(cfg: WyndleConfig, state: State, sub) -> None:
    """Check a subtask and save its final timing in the daily Markdown."""
    if sub.done:
        return
    if state.is_subtask_active(sub.text):
        _pause(cfg, state)
    elapsed = state.get_subtask_elapsed(sub.text)
    started = state.get_subtask_started(sub.text) or sub.started_at
    daily_notes.mark_subtask_done(cfg.daily_dir, sub.text, sub.parent)
    update_subtask(cfg.daily_dir, sub, started=started,
                   ended=time_utils.epoch_now(), elapsed=elapsed)


def _refresh_active_text(cfg: WyndleConfig, state: State, sub) -> None:
    """Keep active timer references aligned after checkbox metadata changes."""
    if not state.is_subtask_active(sub.text):
        return
    fresh = next(s for s in daily_notes.get_task_details(cfg.daily_dir, sub.parent)
                 if s.display_text == sub.display_text)
    state.set("today_active_subtask_text", fresh.text)
    state.set("today_ui_task", fresh.text)
    state.set("today_last_subtask_text", fresh.text)


def dispatch(cfg: WyndleConfig, state: State, action: str, data: dict) -> dict:
    """Apply one validated action. The HTTP layer serializes calls."""
    if action == "morning":
        _start_day(cfg, state, data)
        return snapshot(cfg, state)
    if action not in {"add", "focus", "pause", "complete", "reopen", "break", "wrap", "note",
                      "add_group", "delete", "delete_group", "complete_group",
                      "alarm_plan", "alarm_clear", "edit_task", "priority", "optional",
                      "move_task"}:
        raise ValueError("Unknown action.")
    if state.is_new_day() or state.get("today_started") != "true":
        raise ValueError("Start your day first.")
    if state.get("today_wrapped") == "true":
        if action == "wrap":
            return snapshot(cfg, state)
        raise ValueError("Today is wrapped. Come back tomorrow for a fresh start.")
    if action == "alarm_plan":
        daily_alarm.save_plan(cfg, state, snapshot(cfg, state)["tasks"], data)
    elif action == "alarm_clear":
        daily_alarm.clear_plan(state)
    elif action == "add":
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
                _complete_subtask(cfg, state, sub)
            set_parent_done(cfg.daily_dir, parent, True)
    elif action in {"focus", "complete", "reopen", "note", "delete", "edit_task",
                    "priority", "optional", "move_task"}:
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
            if not sub.done:
                _complete_subtask(cfg, state, sub)
                remaining = daily_notes.get_task_details(cfg.daily_dir, sub.parent)
                set_parent_done(cfg.daily_dir, sub.parent, all(s.done for s in remaining))
                daily_notes.log_to_daily(cfg.daily_dir, f"Completed: **{sub.display_text}**")
        elif action == "reopen":
            if sub.done:
                daily_notes.mark_subtask_done(cfg.daily_dir, sub.text, sub.parent, done=False)
                update_subtask(cfg.daily_dir, sub, ended=0)
                if state.get_subtask_elapsed(sub.text) < sub.saved_elapsed:
                    state.set_subtask_elapsed(sub.text, sub.saved_elapsed)
                set_parent_done(cfg.daily_dir, sub.parent, False)
                daily_notes.log_to_daily(cfg.daily_dir, f"Reopened: **{sub.display_text}**")
        elif action == "priority":
            priority = data.get("priority")
            if type(priority) is not bool:
                raise ValueError("priority must be true or false.")
            update_subtask(cfg.daily_dir, sub, priority=priority,
                           optional=False if priority else sub.optional)
            _refresh_active_text(cfg, state, sub)
        elif action == "optional":
            optional = data.get("optional")
            if type(optional) is not bool:
                raise ValueError("optional must be true or false.")
            update_subtask(cfg.daily_dir, sub, optional=optional,
                           priority=False if optional else sub.priority)
            _refresh_active_text(cfg, state, sub)
        elif action == "edit_task":
            estimate = _minutes(data, "estimate", sub.estimate_min, 0)
            elapsed_min = (_minutes(data, "elapsedMinutes", 0, 0, 10080)
                           if "elapsedMinutes" in data else None)
            priority = data.get("priority", sub.priority)
            optional = data.get("optional", sub.optional)
            if type(priority) is not bool:
                raise ValueError("priority must be true or false.")
            if type(optional) is not bool:
                raise ValueError("optional must be true or false.")
            if priority and optional:
                raise ValueError("A task cannot be both P0 and optional.")
            if elapsed_min is not None:
                state.set_subtask_elapsed(sub.text, elapsed_min * 60)
            update_subtask(cfg.daily_dir, sub, estimate=estimate, priority=priority,
                           optional=optional,
                           elapsed=elapsed_min * 60 if elapsed_min is not None else None)
            _refresh_active_text(cfg, state, sub)
        elif action == "move_task":
            direction = data.get("direction")
            if direction not in ("up", "down"):
                raise ValueError("direction must be up or down.")
            if sub.done:
                raise ValueError("Only unfinished tasks can be reordered here.")
            siblings = [s for s in subs if s.parent == sub.parent and not s.done]
            position = next(i for i, item in enumerate(siblings) if _id(item) == _id(sub))
            target = position + (-1 if direction == "up" else 1)
            if 0 <= target < len(siblings):
                reorder_subtasks(cfg.daily_dir, sub, siblings[target])
        elif action == "delete":
            if state.is_subtask_active(sub.text):
                _pause(cfg, state)
            delete_subtask(cfg, sub)
            remaining = daily_notes.get_task_details(cfg.daily_dir, sub.parent)
            set_parent_done(cfg.daily_dir, sub.parent,
                            bool(remaining) and all(s.done for s in remaining))
            daily_notes.log_to_daily(cfg.daily_dir, f"Deleted subtask: **{sub.display_text}**")
        else:
            note = _text(data, "note")
            append_subtask_note(cfg.daily_dir, sub, note)
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
