"""wyndle morning -- Start your day with yesterday's context.

Flow (v1.3.0):

1. Auto-wrap yesterday if forgotten (syncs notes + times to task notes).
2. Clear day state.
3. Show yesterday's shutdown notes.
4. Carry-over tasks with open subtasks + open notes from task notes.
5. Prompt for new high-level tasks (creates task note files).
6. Write everything to the daily note.

v1.3.0 changes:
- Daily chores are NOT added to High Level Tasks.
- Daily chores are the FIRST section in Task Details.
- Only ``~open`` subtasks and ``~open`` notes carry over.
"""

from __future__ import annotations

from wyndle.lib import display, time_utils
from wyndle.lib.config import WyndleConfig
from wyndle.lib.obsidian import (
    create_daily_note,
    get_high_level_tasks,
    get_yesterday_remaining,
    get_yesterday_wrap,
    log_to_daily,
    read_subtask_notes,
    write_high_level_tasks,
    write_task_details,
)
from wyndle.lib.state import State
from wyndle.lib.task_notes import (
    create_task_note,
    generate_daily_subtasks,
    read_task_note,
    sync_subtask_from_daily,
    write_task_note,
)


_CHORES_TASK_NAME = "Daily Chores"


def auto_wrap_yesterday(cfg: WyndleConfig, state: State) -> None:
    """Sync yesterday's work to task notes if wrap was forgotten.

    Called from ``_setup()`` in cli.py so that ANY command triggers
    auto-wrap.  Must run BEFORE ``clear_day()`` so state timers are
    still available.
    """
    if not cfg.features.obsidian:
        return
    stored_date = state.get("today_date", "")
    if not stored_date or stored_date == time_utils.now_date_str():
        return
    if state.get("today_wrapped", "false") == "true":
        return
    display.dim("  Yesterday wasn't wrapped. Auto-syncing task notes...")
    tasks = get_high_level_tasks(cfg.obsidian_daily_dir, stored_date)
    for t in tasks:
        _sync_task_to_note(cfg, state, t.text, stored_date)
    display.success("Auto-wrap complete.")
    display.console.print()


def _sync_task_to_note(
    cfg: WyndleConfig, state: State, task_name: str, date_str: str,
) -> None:
    """Sync one task's subtask notes and times to its task note file."""
    from wyndle.lib.obsidian import get_task_details, strip_estimate

    note = read_task_note(cfg, task_name)
    subtask_notes = read_subtask_notes(cfg.obsidian_daily_dir, task_name, date_str)
    subs = get_task_details(cfg.obsidian_daily_dir, task_name, date_str)
    for s in subs:
        display_text = strip_estimate(s.text)
        elapsed = state.get_subtask_elapsed_min(s.text)
        daily_notes = subtask_notes.get(display_text, [])
        sync_subtask_from_daily(
            note, display_text, elapsed, s.done,
            daily_notes, date_str, s.estimate_min,
        )
    if note.subtasks:
        write_task_note(cfg, note)


def run(cfg: WyndleConfig, state: State) -> None:
    """Execute the full morning flow."""
    auto_wrap_yesterday(cfg, state)
    _init_day(state)

    mins_available = time_utils.minutes_until(cfg.hard_stop)
    hours_available = time_utils.hours_minutes(mins_available)

    display.header(f"Good morning, {cfg.user_name}")

    if cfg.features.obsidian:
        create_daily_note(cfg.obsidian_daily_dir)

    if mins_available <= 0:
        _recovery_mode(cfg, state)
        return

    _show_late_context(cfg, hours_available)
    _show_yesterday_wrap(cfg)

    # Carry-over tasks (excluding daily chores)
    yesterday_tasks = [
        t for t in get_yesterday_remaining(cfg.obsidian_daily_dir)
        if t != _CHORES_TASK_NAME
    ]
    carry = _prompt_carryover(yesterday_tasks)
    new_tasks = _prompt_new_tasks()

    carried = yesterday_tasks if carry else []
    if cfg.features.obsidian:
        # 1. Write chores as FIRST Task Details section (not in High Level Tasks)
        _add_chores_task(cfg)
        # 2. Carry-over tasks (High Level Tasks + Task Details)
        if carried:
            _carry_over_tasks(cfg, carried)
        # 3. New tasks
        _add_new_tasks(cfg, new_tasks)

    all_tasks = carried + new_tasks
    _show_summary(cfg, state, all_tasks, hours_available)


def _init_day(state: State) -> None:
    """Reset state if it's a new calendar day."""
    if state.is_new_day():
        state.clear_day()
        state.set("today_date", time_utils.now_date_str())


def _carry_over_tasks(cfg: WyndleConfig, task_names: list[str]) -> None:
    """Write carried-over tasks with their open subtasks + open notes.

    Falls back to yesterday's daily note when the task note has no
    open subtasks.
    """
    from datetime import timedelta

    write_high_level_tasks(cfg.obsidian_daily_dir, task_names)
    yesterday = (time_utils.now().date() - timedelta(days=1)).isoformat()
    for name in task_names:
        subtask_md = generate_daily_subtasks(cfg, name)
        if not subtask_md:
            subtask_md = _subtasks_from_yesterday(cfg, name, yesterday)
        if subtask_md:
            write_task_details(cfg.obsidian_daily_dir, name, subtask_md)


def _subtasks_from_yesterday(
    cfg: WyndleConfig, task_name: str, yesterday: str,
) -> str:
    """Read open subtasks from yesterday's daily note as a fallback."""
    from wyndle.lib.obsidian import get_task_details, strip_estimate, read_subtask_notes

    subs = get_task_details(cfg.obsidian_daily_dir, task_name, yesterday)
    if not subs:
        return ""
    notes = read_subtask_notes(cfg.obsidian_daily_dir, task_name, yesterday)
    lines: list[str] = []
    for s in subs:
        if s.done:
            continue
        est = f" ~{s.estimate_min}m" if s.estimate_min else ""
        lines.append(f"- [ ] {s.display_text}{est}")
        for n in notes.get(s.display_text, []):
            lines.append(f"  - {n}")
    return "\n".join(lines)


def _add_new_tasks(cfg: WyndleConfig, task_names: list[str]) -> None:
    """Write new tasks to daily note and create task note files."""
    if task_names:
        write_high_level_tasks(cfg.obsidian_daily_dir, task_names)
    for name in task_names:
        create_task_note(cfg, name)


def _add_chores_task(cfg: WyndleConfig) -> None:
    """Write daily chores as the first section in Task Details.

    Chores are NOT added to High Level Tasks (v1.3.0 change).
    Each chore becomes a subtask with ``~Xm`` estimate.
    Chores reset daily -- no persistent task note.
    """
    if not cfg.daily_chores:
        return
    est = cfg.chore_estimate_min
    subtask_lines = [f"- [ ] {chore} ~{est}m" for chore in cfg.daily_chores]
    write_task_details(
        cfg.obsidian_daily_dir, _CHORES_TASK_NAME,
        "\n".join(subtask_lines), prepend=True,
    )


def _recovery_mode(cfg: WyndleConfig, state: State) -> None:
    """Handle past-hard-stop morning with a single prep task."""
    display.warn("You're past your hard stop time. Today is a recovery day.")
    reply = display.prompt("ONE thing to prep for tomorrow? (or 'skip')")
    if reply.lower() != "skip":
        state.set("tomorrow_first_task", reply)
        if cfg.features.obsidian:
            log_to_daily(cfg.obsidian_daily_dir, f"Prepped for tomorrow: **{reply}**")
        display.success("Tomorrow-you will thank you.")
    state.set("today_started", "true")
    state.set("today_start_time", time_utils.now_time_str())


def _show_late_context(cfg: WyndleConfig, hours_available: str) -> None:
    """Print late-start warnings and available time."""
    now_dt = time_utils.now()
    if now_dt >= time_utils.time_to_datetime(cfg.late_thresholds.severe):
        display.warn("Very late -- pick ONE thing. That's enough.")
    elif now_dt >= time_utils.time_to_datetime(cfg.late_thresholds.moderate):
        display.warn("Moderate late start. Enough for 2-3 focused blocks.")
    display.info(f"It's [bold]{time_utils.now_friendly()}[/bold]. "
                 f"You have [bold]{hours_available}[/bold] left.")
    display.console.print()


def _show_yesterday_wrap(cfg: WyndleConfig) -> None:
    """Display yesterday's shutdown notes."""
    display.accent("Yesterday's Wrap")
    display.console.print()
    wrap = get_yesterday_wrap(cfg.obsidian_daily_dir)
    if wrap:
        for line in wrap.splitlines():
            display.dim(f"  {line}")
    else:
        display.dim("  No wrap from yesterday.")
    display.console.print()


def _prompt_carryover(yesterday_tasks: list[str]) -> bool:
    """Show and prompt for carrying over yesterday's unfinished tasks."""
    if not yesterday_tasks:
        return False
    display.accent("Unfinished from yesterday:")
    for i, t in enumerate(yesterday_tasks, 1):
        display.dim(f"  {i}) {t}")
    display.console.print()
    return display.confirm("Carry these over to today?")


def _prompt_new_tasks() -> list[str]:
    """Prompt user to enter new high-level tasks."""
    display.console.print()
    display.accent("Any NEW high-level tasks for today?")
    display.dim("Enter tasks one per line. Empty line when done.")
    display.console.print()
    new_tasks: list[str] = []
    while True:
        task = display.prompt("Task (or Enter to finish):")
        if not task.strip():
            break
        new_tasks.append(task.strip())
    return new_tasks


def _show_summary(
    cfg: WyndleConfig, state: State,
    all_tasks: list[str], hours_available: str,
) -> None:
    """Print plan summary and finalize day state."""
    display.console.print()
    display.header("Today's Plan")
    if all_tasks:
        for t in all_tasks:
            display.dim(f"  - {t}")
    display.console.print()
    display.dim(f"Daily chores: {', '.join(cfg.daily_chores)}")
    display.info(f"Hard stop: [bold]{cfg.hard_stop}[/bold] ({hours_available} from now)")

    if cfg.features.obsidian:
        log_to_daily(cfg.obsidian_daily_dir,
                     f"Day started. Tasks: {', '.join(all_tasks) if all_tasks else 'none added'}")

    state.set("today_started", "true")
    state.set("today_start_time", time_utils.now_time_str())
    if all_tasks:
        state.set("today_one_thing", all_tasks[0])

    display.console.print()
    display.success("Day initialized.")
    display.console.print()
    display.accent("Next steps:")
    display.dim("  wyndle open    -> Open note, add sub-tasks with estimates")
    display.dim("  wyndle start   -> Begin a focus block")
    display.dim("  wyndle status  -> See what's left today")
