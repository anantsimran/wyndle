"""wyndle status -- Show remaining work with estimated vs actual time.

Reads high-level tasks and subtasks from the daily note and
cross-references with elapsed time from the state store.

v1.3.0:
- Shows total estimated time remaining today.
- Marks the currently active task in the task list.
- Shows remaining subtask counts through ``~future`` from task notes.
"""

from __future__ import annotations

from wyndle.lib import display, time_utils
from wyndle.lib.config import WyndleConfig
from wyndle.lib.obsidian import (
    get_high_level_tasks,
    get_task_details,
    get_task_estimate,
    strip_estimate,
)
from wyndle.lib.state import State
from wyndle.lib.task_notes import get_all_remaining_counts


def run(cfg: WyndleConfig, state: State) -> None:
    """Print the full status dashboard for the current day."""
    display.header("Wyndle Status")

    if state.get("today_started", "false") != "true":
        display.warn("Day not started yet.")
        display.dim("Run 'wyndle morning' to begin.")
        return

    start_time = state.get("today_start_time", "??:??")
    total_focused = state.get("today_focused_min", "0")
    wrapped = state.get("today_wrapped", "false")
    mins_to_stop = time_utils.minutes_until(cfg.hard_stop)
    current_task = state.get("today_current_task", "")

    display.accent(f"{time_utils.now_date_str()} \u2014 {time_utils.now_friendly()}")
    display.console.print()
    display.dim(f"Started at:    {start_time}")
    display.dim(f"Focused today: {total_focused} minutes")

    active_sub = state.get_active_subtask_text()
    if active_sub:
        elapsed = state.get_subtask_elapsed_min(active_sub)
        display.info(f"Active:        [bold]{strip_estimate(active_sub)}[/bold] ({elapsed}m)")

    if wrapped == "true":
        display.success("Day wrapped up.")
        return

    if mins_to_stop > 0:
        display.info(
            f"Time to stop:  [bold]{time_utils.hours_minutes(mins_to_stop)}[/bold]",
            style=display.ACCENT,
        )
    else:
        display.warn(f"Past hard stop by {time_utils.hours_minutes(-mins_to_stop)}")

    # -- Tasks --
    display.console.print()
    tasks = get_high_level_tasks(cfg.obsidian_daily_dir)
    remaining_hl = [t for t in tasks if not t.done]
    done_hl = [t for t in tasks if t.done]

    # -- Remaining work time --
    total_remaining_est = 0
    total_remaining_actual = 0

    if remaining_hl:
        display.accent(f"Tasks remaining: {len(remaining_hl)}")
        for t in remaining_hl:
            est_rem, actual_rem = _print_task_detail(cfg, state, t.text, current_task)
            total_remaining_est += est_rem
            total_remaining_actual += actual_rem

    if done_hl:
        display.console.print()
        display.success(f"Completed: {len(done_hl)}")
        for t in done_hl:
            display.dim(f"  \u2713 {t.text}")

    # -- Time remaining summary --
    if total_remaining_est > 0:
        net_remaining = max(0, total_remaining_est - total_remaining_actual)
        display.console.print()
        display.accent("Time remaining:")
        display.info(
            f"  Estimated work left: [bold]{time_utils.hours_minutes(net_remaining)}[/bold]"
        )
        if mins_to_stop > 0:
            slack = mins_to_stop - net_remaining
            if slack >= 0:
                display.dim(f"  Slack: {time_utils.hours_minutes(slack)} buffer")
            else:
                display.warn(f"  Over capacity by {time_utils.hours_minutes(-slack)}")

    # -- Future subtask count from task notes --
    if cfg.features.obsidian:
        _print_future_counts(cfg)


def _print_task_detail(
    cfg: WyndleConfig, state: State, task_text: str, current_task: str,
) -> tuple[int, int]:
    """Print a single high-level task with its subtask breakdown.

    Returns:
        Tuple of (remaining_estimate_min, elapsed_on_remaining_min)
        for uncompleted subtasks only.
    """
    est = get_task_estimate(cfg.obsidian_daily_dir, task_text)
    subs = get_task_details(cfg.obsidian_daily_dir, task_text)
    total_elapsed = sum(state.get_subtask_elapsed_min(s.text) for s in subs)
    is_active = task_text == current_task

    parts = []
    if est:
        parts.append(f"est: {time_utils.hours_minutes(est)}")
    if total_elapsed:
        parts.append(f"actual: {time_utils.hours_minutes(total_elapsed)}")
    info = f"  ({', '.join(parts)})" if parts else ""
    active_marker = " [bold cyan]<- active[/bold cyan]" if is_active else ""
    display.info(f"  [bold]{task_text}[/bold]{info}{active_marker}")

    remaining_est = 0
    remaining_actual = 0
    for s in subs:
        marker = "\u2713" if s.done else "\u2610"
        elapsed_min = state.get_subtask_elapsed_min(s.text)
        sub_parts = []
        if s.estimate_min:
            sub_parts.append(f"~{s.estimate_min}m")
        if elapsed_min:
            sub_parts.append(f"{elapsed_min}m" if s.done else f"{elapsed_min}m done")
        if state.is_subtask_active(s.text):
            sub_parts.append("<- active")
        sub_info = f"  {' -> '.join(sub_parts)}" if sub_parts else ""
        display.dim(f"    {marker} {s.display_text}{sub_info}")
        if not s.done:
            remaining_est += s.estimate_min
            remaining_actual += elapsed_min

    return remaining_est, remaining_actual


def _print_future_counts(cfg: WyndleConfig) -> None:
    """Print remaining subtask counts including ~future from task notes."""
    open_count, future_count, total = get_all_remaining_counts(cfg)
    if total == 0:
        return
    display.console.print()
    display.accent("Backlog (from task notes):")
    display.dim(f"  ~open: {open_count} subtasks")
    if future_count > 0:
        display.dim(f"  ~future: {future_count} subtasks")
    display.dim(f"  Total remaining: {total} subtasks")
