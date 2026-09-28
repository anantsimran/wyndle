"""wyndle start [task] — Begin a timed focus block on a sub-task.

Reads high-level tasks and subtasks from the daily note.
Tracks elapsed time per subtask.  Switching pauses the old subtask
and resumes the new one.

wyndle switch
    Pause the current subtask and show a flat list of *all* remaining
    subtasks across every high-level task.  Pick one to start.
"""

from __future__ import annotations

from wyndle.lib import display, time_utils
from wyndle.lib.config import WyndleConfig
from wyndle.lib.daily_notes import (
    get_all_subtasks,
    get_high_level_tasks,
    get_task_details,
    get_task_estimate,
    log_to_daily,
    mark_subtask_done,
    parse_estimate,
    strip_estimate,
)
from wyndle.lib.models import SubTask
from wyndle.lib.state import State
from wyndle.lib.timer import start_focus_block

_VALID_DURATIONS = {5, 15, 30}


def run(cfg: WyndleConfig, state: State, task: str = "") -> None:
    """Main entry: pick a high-level task, then a subtask, then focus.

    Args:
        cfg:   Current configuration.
        state: Current state store.
        task:  Optional pre-selected task name (from CLI argument).
    """
    if state.get("today_started", "false") != "true":
        display.warn("Day not started yet.")
        display.dim("Run 'wyndle morning' first.")
        return

    hl_task = task if task else _pick_high_level(cfg, state)
    if not hl_task:
        display.error("No task specified.")
        return

    state.set("today_current_task", hl_task)
    subtask = _pick_subtask(cfg, state, hl_task)

    if not subtask:
        display.dim("No sub-tasks found. Working on the task directly.")
        display.dim("Tip: add sub-tasks with estimates in your notes -> wyndle open")
        state.start_subtask_timer(hl_task)
        if cfg.features.notes:
            log_to_daily(cfg.daily_dir, f"Started: **{hl_task}**")
        start_focus_block(hl_task, 0, cfg, state)
        return

    state.start_subtask_timer(subtask.text)
    if cfg.features.notes:
        msg = f"Started: **{subtask.display_text}** (under {hl_task})"
        if subtask.estimate_min:
            msg += f" — est: {subtask.estimate_min}m"
        log_to_daily(cfg.daily_dir, msg)
    start_focus_block(subtask.text, subtask.estimate_min, cfg, state)


def _pick_high_level(cfg: WyndleConfig, state: State) -> str:
    """Interactively pick a high-level task from the daily note.

    Falls back to today's ``one_thing`` or a free-text prompt if no
    tasks are found.

    Args:
        cfg:   Current configuration.
        state: Current state store.

    Returns:
        Selected task name string.
    """
    tasks = get_high_level_tasks(cfg.daily_dir)
    remaining = [t for t in tasks if not t.done]

    if not remaining:
        one_thing = state.get("today_one_thing", "")
        if one_thing:
            display.info(f"Today's priority: [bold]{one_thing}[/bold]")
            if display.confirm("Work on this?"):
                return one_thing
        return display.prompt("What are you working on?")

    display.accent("Today's tasks:")
    for i, t in enumerate(remaining, 1):
        est = get_task_estimate(cfg.daily_dir, t.text)
        subs = get_task_details(cfg.daily_dir, t.text)
        sub_remaining = len([s for s in subs if not s.done])
        parts = [f"{sub_remaining} items" if sub_remaining else "no sub-tasks"]
        if est:
            parts.append(f"est: {time_utils.hours_minutes(est)}")
        display.info(f"  {i}) {t.text}  ({', '.join(parts)})")
    display.console.print()

    choice = display.prompt("Pick a task number (or type a new one):")
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(remaining):
            return remaining[idx].text
    except ValueError:
        pass
    return choice


def _pick_subtask(cfg: WyndleConfig, state: State, hl_task: str) -> SubTask | None:
    """Interactively pick a subtask within a high-level task.

    Args:
        cfg:     Current configuration.
        state:   Current state store.
        hl_task: Parent high-level task name.

    Returns:
        Selected :class:`SubTask`, or ``None`` if no subtasks exist.
    """
    subs = get_task_details(cfg.daily_dir, hl_task)
    remaining = [s for s in subs if not s.done]
    if not remaining:
        return None

    display.console.print()
    display.accent(f"Sub-tasks for '{hl_task}':")
    total_est = sum(s.estimate_min for s in remaining)

    for i, s in enumerate(remaining, 1):
        elapsed_min = state.get_subtask_elapsed_min(s.text)
        parts = []
        if s.estimate_min:
            parts.append(f"~{s.estimate_min}m")
        if elapsed_min:
            parts.append(f"{elapsed_min}m done")
        if state.is_subtask_active(s.text):
            parts.append("<- active")
        info = f"  ({', '.join(parts)})" if parts else ""
        display.info(f"  {i}) {s.display_text}{info}")

    if total_est:
        display.dim(f"  Total estimate: {time_utils.hours_minutes(total_est)}")
    display.console.print()

    choice = display.prompt("Pick sub-task number (or Enter for first):")
    if not choice.strip():
        return remaining[0]
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(remaining):
            return remaining[idx]
    except ValueError:
        pass
    return remaining[0]


def close_active_subtask(cfg: WyndleConfig, state: State) -> bool:
    """Pause the active subtask and offer to check it off in the daily note.

    Returns:
        ``True`` if a subtask was active.
    """
    paused = state.pause_active_subtask()
    if not paused:
        return False
    name = strip_estimate(paused)
    elapsed = state.get_subtask_elapsed_min(paused)
    display.info(f"Paused: [bold]{name}[/bold] ({elapsed}m elapsed)")
    if display.confirm("Mark this sub-task as done?"):
        if mark_subtask_done(cfg.daily_dir, paused):
            display.success(f"Marked done: {name}")
            if cfg.features.notes:
                log_to_daily(cfg.daily_dir, f"Completed: **{name}** ({elapsed}m)")
    display.console.print()
    return True


def switch_task(cfg: WyndleConfig, state: State) -> None:
    """Pause the current subtask and switch to a different one.

    Prompts to mark the paused subtask as done (checks its checkbox
    in the daily note), then shows a flat list of all unchecked
    subtasks across every high-level task, grouped by parent.

    Args:
        cfg:   Current configuration.
        state: Current state store.
    """
    close_active_subtask(cfg, state)

    all_subs = get_all_subtasks(cfg.daily_dir)
    remaining = [s for s in all_subs if not s.done]

    if not remaining:
        display.warn("No sub-tasks found. Add them in your notes -> wyndle open")
        return

    display.accent("All sub-tasks:")
    current_parent = ""
    num = 0
    num_map: dict[int, SubTask] = {}

    for s in remaining:
        if s.parent != current_parent:
            current_parent = s.parent
            est = get_task_estimate(cfg.daily_dir, current_parent)
            est_str = f"  (est: {time_utils.hours_minutes(est)})" if est else ""
            display.info(f"  [bold]{current_parent}[/bold]{est_str}")
        num += 1
        num_map[num] = s
        parts = []
        if s.estimate_min:
            parts.append(f"~{s.estimate_min}m")
        elapsed_min = state.get_subtask_elapsed_min(s.text)
        if elapsed_min:
            parts.append(f"{elapsed_min}m done")
        info = f"  ({', '.join(parts)})" if parts else ""
        display.dim(f"    {num}) {s.display_text}{info}")

    display.console.print()
    choice = display.prompt("Pick sub-task number:")
    try:
        idx = int(choice)
        if idx in num_map:
            selected = num_map[idx]
            state.set("today_current_task", selected.parent)
            state.start_subtask_timer(selected.text)
            if cfg.features.notes:
                log_to_daily(
                    cfg.daily_dir,
                    f"Switched to: **{selected.display_text}** (under {selected.parent})",
                )
            start_focus_block(selected.text, selected.estimate_min, cfg, state)
            return
    except ValueError:
        pass
    display.dim("No valid selection. Run 'wyndle switch' again.")


def next_task(cfg: WyndleConfig, state: State) -> None:
    """Close the current subtask and start another through the normal picker."""
    if state.get("today_started", "false") != "true":
        display.warn("Day not started yet.")
        display.dim("Run 'wyndle morning' first.")
        return

    if not close_active_subtask(cfg, state):
        display.dim("No active sub-task to close.")
        display.console.print()

    remaining = [s for s in get_all_subtasks(cfg.daily_dir) if not s.done]
    if not remaining:
        display.success("All sub-tasks complete. Run 'wyndle wrap' to end the day.")
        return

    display.dim(f"{len(remaining)} sub-tasks remaining.")
    display.console.print()
    run(cfg, state)


def _resolve_subtask_text(state: State) -> str | None:
    """Use the active subtask, or the most recently active one."""
    return state.get_active_subtask_text() or state.get_last_subtask_text()


def _parse_duration(raw: str) -> int:
    """Return an allowed focus block length, or zero for the normal prompt."""
    try:
        mins = int(raw)
    except (ValueError, TypeError):
        return 0
    return mins if mins in _VALID_DURATIONS else 0


def restart_task(cfg: WyndleConfig, state: State, minutes: str = "") -> None:
    """Restart the last focus block with an optional fixed duration."""
    if state.get("today_started", "false") != "true":
        display.warn("Day not started yet.")
        display.dim("Run 'wyndle morning' first.")
        return

    subtask_text = _resolve_subtask_text(state)
    if not subtask_text:
        display.warn("No previous subtask found to restart.")
        display.dim("Run 'wyndle start' to pick a subtask first.")
        return

    display_name = strip_estimate(subtask_text)
    estimate_min = parse_estimate(subtask_text)
    block_min = _parse_duration(minutes)

    if block_min:
        display.info(f"Restarting [bold]{display_name}[/bold] with {block_min}m block.")
    else:
        display.info(f"Restarting [bold]{display_name}[/bold].")

    state.start_subtask_timer(subtask_text)

    if cfg.features.notes:
        log_to_daily(
            cfg.daily_dir,
            f"Restarted: **{display_name}** ({block_min}m)"
            if block_min
            else f"Restarted: **{display_name}**",
        )

    start_focus_block(
        subtask_text, estimate_min, cfg, state,
        block_min_override=block_min,
    )
