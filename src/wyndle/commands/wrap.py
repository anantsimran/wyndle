"""wyndle wrap -- Shutdown ritual with time-tracking summary.

Pauses any active subtask, computes a work-done summary (completed
vs total, actual vs estimated, on-time stats), prints per-task
breakdown, asks for reflection, and logs to the daily note.

v1.3.0: adds a ``Work Done`` section showing completion ratio,
actual vs estimated time, and on-time percentage.  Fixes
``today_focused_min`` to include unflushed active subtask time.
"""

from __future__ import annotations

from wyndle.lib import display, time_utils
from wyndle.lib.config import WyndleConfig
from wyndle.lib.models import WorkSummary
from wyndle.lib.obsidian import (
    get_high_level_tasks,
    get_remaining_tasks,
    get_task_details,
    get_task_estimate,
    log_to_daily,
    read_subtask_notes,
    replace_placeholder,
    strip_estimate,
)
from wyndle.lib.state import State
from wyndle.lib.task_notes import (
    read_task_note,
    sync_subtask_from_daily,
    write_task_note,
)


def run(cfg: WyndleConfig, state: State) -> None:
    """Execute the full shutdown ritual."""
    display.header("Shutdown Ritual")

    paused = state.pause_active_subtask()
    if paused:
        display.dim(f"Paused active sub-task: {strip_estimate(paused)}")
        display.console.print()

    # Flush focused time including any live subtask time
    _flush_focused_time(state)
    total_focused = state.get("today_focused_min", "0")
    start_time = state.get("today_start_time", "??:??")

    _print_day_stats(start_time, total_focused)
    tasks = get_high_level_tasks(cfg.obsidian_daily_dir)
    summary_lines, ws = _print_time_summary(cfg, state, tasks)
    _print_work_done(ws)
    _print_totals(ws, summary_lines)
    _print_remaining(cfg)

    progress, tomorrow_task, reflection = _collect_reflections(state)

    if cfg.features.obsidian:
        _write_shutdown_notes(
            cfg, total_focused, ws, progress,
            tomorrow_task, reflection, summary_lines,
        )
        _sync_all_task_notes(cfg, state, tasks)

    state.set("today_wrapped", "true")
    display.console.print()
    display.header("Day Complete")
    display.success(f"Tomorrow: [bold]{tomorrow_task}[/bold]")
    display.console.print()
    display.dim("Screen-free wind-down starts now. Rest.")


def _flush_focused_time(state: State) -> None:
    """Ensure today_focused_min includes all tracked subtask time.

    Sums elapsed minutes across all subtask timers and updates
    the focused counter if it's lower (catches mid-block Ctrl+C).
    """
    total = 0
    for path in state.state_dir.glob("st_*_elapsed"):
        try:
            total += int(path.read_text().strip()) // 60
        except (ValueError, OSError):
            continue
    current = state.get_int("today_focused_min", 0)
    if total > current:
        state.set("today_focused_min", str(total))


def _print_day_stats(start_time: str, total_focused: str) -> None:
    """Print start time and focused minutes."""
    display.accent("Today's stats:")
    display.dim(f"Started at: {start_time}")
    display.dim(f"Focused time: {total_focused} minutes")
    display.console.print()


def _print_time_summary(
    cfg: WyndleConfig, state: State, tasks: list,
) -> tuple[list[str], WorkSummary]:
    """Print per-task time tracking and return summary data."""
    display.accent("Time Tracking Summary:")
    display.console.print()

    summary_lines: list[str] = []
    ws = WorkSummary()

    for t in tasks:
        lines, task_ws = _task_summary(cfg, state, t)
        summary_lines.extend(lines)
        ws.completed += task_ws.completed
        ws.total += task_ws.total
        ws.actual_min += task_ws.actual_min
        ws.estimated_min += task_ws.estimated_min
        ws.on_time += task_ws.on_time
        ws.estimated_done += task_ws.estimated_done

    return summary_lines, ws


def _task_summary(
    cfg: WyndleConfig, state: State, task,
) -> tuple[list[str], WorkSummary]:
    """Print and return summary for one high-level task."""
    subs = get_task_details(cfg.obsidian_daily_dir, task.text)
    est_total = get_task_estimate(cfg.obsidian_daily_dir, task.text)
    actual_total = sum(state.get_subtask_elapsed_min(s.text) for s in subs)
    ws = WorkSummary(
        total=len(subs),
        completed=sum(1 for s in subs if s.done),
        actual_min=actual_total,
        estimated_min=est_total,
    )

    done_marker = "\u2713" if task.done else "\u2610"
    est_str = time_utils.hours_minutes(est_total) if est_total else "\u2014"
    actual_str = time_utils.hours_minutes(actual_total) if actual_total else "0m"
    display.info(f"  {done_marker} [bold]{task.text}[/bold]    est: {est_str}  actual: {actual_str}")
    lines = [f"{done_marker} {task.text}  est: {est_str}  actual: {actual_str}"]

    for s in subs:
        sub_done = "\u2713" if s.done else "\u2610"
        est_part = f"~{s.estimate_min}m" if s.estimate_min else "\u2014"
        elapsed_m = state.get_subtask_elapsed_min(s.text)
        actual_part = f"{elapsed_m}m" if elapsed_m else "0m"
        display.dim(f"    {sub_done} {s.display_text}    {est_part} -> {actual_part}")
        lines.append(f"  {sub_done} {s.display_text}  {est_part} -> {actual_part}")
        if s.done and s.estimate_min > 0:
            ws.estimated_done += 1
            if elapsed_m <= s.estimate_min:
                ws.on_time += 1

    return lines, ws


def _print_work_done(ws: WorkSummary) -> None:
    """Print the Work Done section with completion ratio."""
    display.console.print()
    display.accent("Work Done:")
    pct = int(ws.completed / ws.total * 100) if ws.total else 0
    display.info(f"  Completed: [bold]{ws.completed}/{ws.total} subtasks ({pct}%)[/bold]")
    est_str = time_utils.hours_minutes(ws.estimated_min) if ws.estimated_min else "\u2014"
    actual_str = time_utils.hours_minutes(ws.actual_min) if ws.actual_min else "0m"
    display.info(f"  Time tracked: [bold]{actual_str}[/bold] (actual) vs [bold]{est_str}[/bold] (estimated)")
    if ws.estimated_done > 0:
        display.info(
            f"  On-time: [bold]{ws.on_time}/{ws.estimated_done} sub-tasks within estimate[/bold]"
        )


def _print_totals(ws: WorkSummary, summary_lines: list[str]) -> None:
    """Print planned vs actual totals."""
    display.console.print()
    planned_str = time_utils.hours_minutes(ws.estimated_min) if ws.estimated_min else "\u2014"
    actual_str = time_utils.hours_minutes(ws.actual_min) if ws.actual_min else "0m"

    if ws.estimated_min > 0:
        delta = ws.actual_min - ws.estimated_min
        sign = "+" if delta >= 0 else "-"
        delta_str = f"{sign}{time_utils.hours_minutes(abs(delta))}"
        display.info(
            f"  [bold]Planned: {planned_str}  |  Actual: {actual_str}  |  Delta: {delta_str}[/bold]"
        )
    else:
        display.info(f"  [bold]Actual: {actual_str}[/bold]  (no estimates set)")

    summary_lines.append("")
    summary_lines.append(f"Planned: {planned_str}  Actual: {actual_str}")
    display.console.print()


def _print_remaining(cfg: WyndleConfig) -> None:
    """Show unfinished tasks if any."""
    remaining = get_remaining_tasks(cfg.obsidian_daily_dir)
    if remaining.high_level:
        display.warn(f"Unfinished tasks: {len(remaining.high_level)}")
        for t in remaining.high_level:
            display.dim(f"  \u2610 {t.text}")
        display.console.print()


def _collect_reflections(state: State) -> tuple[str, str, str]:
    """Prompt for end-of-day reflections.  Returns (progress, tomorrow, notes)."""
    progress = display.prompt("How did today go? (good/ok/rough)")
    display.console.print()
    display.accent("Tomorrow's gift to yourself:")
    tomorrow_task = display.prompt("What's the FIRST thing you'll work on tomorrow?")
    state.set("tomorrow_first_task", tomorrow_task)
    display.console.print()
    reflection = display.prompt("Anything to note? (Enter to skip)")
    return progress, tomorrow_task, reflection


def _write_shutdown_notes(
    cfg: WyndleConfig, total_focused: str, ws: WorkSummary,
    progress: str, tomorrow_task: str, reflection: str,
    summary_lines: list[str],
) -> None:
    """Write shutdown notes and log entry to the daily note."""
    pct = int(ws.completed / ws.total * 100) if ws.total else 0
    planned_str = time_utils.hours_minutes(ws.estimated_min) if ws.estimated_min else "\u2014"
    actual_str = time_utils.hours_minutes(ws.actual_min) if ws.actual_min else "0m"

    shutdown_text = f"Day: {progress}\n"
    shutdown_text += f"Total focused: {total_focused}m\n"
    shutdown_text += f"Planned: {planned_str}  Actual: {actual_str}\n"
    shutdown_text += f"Work done: {ws.completed}/{ws.total} subtasks ({pct}%)\n"
    if ws.estimated_done > 0:
        shutdown_text += f"On-time: {ws.on_time}/{ws.estimated_done} sub-tasks within estimate\n"
    shutdown_text += f"Tomorrow: {tomorrow_task}\n"
    if reflection.strip():
        shutdown_text += f"Notes: {reflection}\n"
    shutdown_text += "\nTime tracking:\n"
    shutdown_text += "\n".join(summary_lines)

    replace_placeholder(cfg.obsidian_daily_dir, "> _filled by wyndle wrap_", f"> {shutdown_text}")
    log_to_daily(
        cfg.obsidian_daily_dir,
        f"Shutdown at {time_utils.now_friendly()}. "
        f"Focused {total_focused}m. Tomorrow: **{tomorrow_task}**",
    )


def _sync_all_task_notes(cfg: WyndleConfig, state: State, tasks: list) -> None:
    """Sync subtask notes and elapsed times to task note files.

    Uses strict-match note merging: new/changed notes are appended
    with ``~open`` tag.  Existing tagged notes are preserved.
    """
    today = time_utils.now_date_str()
    for t in tasks:
        note = read_task_note(cfg, t.text)
        subtask_notes = read_subtask_notes(cfg.obsidian_daily_dir, t.text)
        subs = get_task_details(cfg.obsidian_daily_dir, t.text)
        for s in subs:
            display_text = strip_estimate(s.text)
            elapsed = state.get_subtask_elapsed_min(s.text)
            daily_notes = subtask_notes.get(display_text, [])
            sync_subtask_from_daily(
                note, display_text, elapsed, s.done,
                daily_notes, today, s.estimate_min,
            )
        if note.subtasks:
            write_task_note(cfg, note)
