"""wyndle break — Take a tracked break.

Pauses the active subtask, runs a break timer, and offers to resume
the previous subtask when the break is over.  Break time is logged
to Obsidian separately from focus time.
"""

from __future__ import annotations

from wyndle.lib import display
from wyndle.lib.config import WyndleConfig
from wyndle.lib.notifier import notify
from wyndle.lib.obsidian import log_to_daily, parse_estimate, strip_estimate
from wyndle.lib.state import State
from wyndle.lib.timer import timer_display

# label, default minutes (0 = ask user)
BREAK_TYPES: dict[str, tuple[str, int]] = {
    "1": ("Lunch", 45),
    "2": ("Walk", 15),
    "3": ("Coffee / snack", 10),
    "4": ("Stretch / breathe", 5),
    "5": ("Custom", 0),
}


def run(cfg: WyndleConfig, state: State) -> None:
    """Execute the break flow.

    1. Pause any active subtask.
    2. Let the user pick a break type.
    3. Run a countdown timer.
    4. Fire a notification when done.
    5. Offer to resume the previous subtask.

    Args:
        cfg:   Current configuration.
        state: Current state store.
    """
    paused = state.pause_active_subtask()
    if paused:
        elapsed = state.get_subtask_elapsed_min(paused)
        display.dim(f"Paused: {strip_estimate(paused)} ({elapsed}m)")
        display.console.print()

    display.header("Break Time")

    display.accent("What kind of break?")
    for key, (name, duration) in BREAK_TYPES.items():
        display.dim(f"  {key}) {name}" + (f" ({duration}m)" if duration else ""))
    display.console.print()

    choice = display.prompt("Choice? [1-5]")
    break_name, default_min = BREAK_TYPES.get(choice, ("Break", 10))

    if default_min == 0:
        break_name = display.prompt("Break name:")
        min_str = display.prompt("How many minutes?")
        try:
            break_min = max(1, int(min_str))
        except ValueError:
            break_min = 10
    else:
        break_min = default_min

    break_label = f"Break: {break_name}"
    state.start_subtask_timer(break_label)

    display.console.print()
    display.dim(f"Starting {break_min}m break: {break_name}")
    display.console.print()

    if cfg.features.obsidian:
        log_to_daily(cfg.obsidian_daily_dir, f"Break started: **{break_name}** ({break_min}m)")

    timer_display(break_min * 60, break_name)

    if cfg.features.notifications:
        notify("Break Over", f"{break_name} — {break_min}m done. Ready to get back?")

    state.pause_active_subtask()
    elapsed = state.get_subtask_elapsed_min(break_label)

    if cfg.features.obsidian:
        log_to_daily(cfg.obsidian_daily_dir, f"Break ended: **{break_name}** ({elapsed}m actual)")

    display.console.print()
    display.success(f"Break done! ({elapsed}m)")

    if paused:
        display.console.print()
        if display.confirm(f"Resume '{strip_estimate(paused)}'?"):
            state.start_subtask_timer(paused)
            from wyndle.lib.timer import start_focus_block
            start_focus_block(paused, parse_estimate(paused), cfg, state)
            return

    display.dim("Run 'wyndle start' or 'wyndle switch' to continue working.")
