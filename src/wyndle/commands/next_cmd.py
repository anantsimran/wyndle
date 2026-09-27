"""wyndle next -- Close current subtask and start the next one.

Convenience command that combines the end-of-subtask flow with
starting a new focus block.  Pauses the active subtask, offers
to mark it done, then hands off to ``wyndle start``.
"""

from __future__ import annotations

from wyndle.lib import display
from wyndle.lib.config import WyndleConfig
from wyndle.lib.obsidian import (
    get_all_subtasks,
    log_to_daily,
    mark_subtask_done,
    strip_estimate,
)
from wyndle.lib.state import State


def run(cfg: WyndleConfig, state: State) -> None:
    """Pause current subtask, optionally mark done, then start next.

    Args:
        cfg:   Current configuration.
        state: Current state store.
    """
    if state.get("today_started", "false") != "true":
        display.warn("Day not started yet.")
        display.dim("Run 'wyndle morning' first.")
        return

    paused = state.pause_active_subtask()
    if paused:
        elapsed = state.get_subtask_elapsed_min(paused)
        display_name = strip_estimate(paused)
        display.info(f"Current: [bold]{display_name}[/bold] ({elapsed}m elapsed)")
        display.console.print()
        if display.confirm("Mark this sub-task as done?"):
            if mark_subtask_done(cfg.obsidian_daily_dir, paused):
                display.success(f"Marked done: {display_name}")
                if cfg.features.obsidian:
                    log_to_daily(
                        cfg.obsidian_daily_dir,
                        f"Completed: **{display_name}** ({elapsed}m)",
                    )
            display.console.print()
    else:
        display.dim("No active sub-task to close.")
        display.console.print()

    # Show remaining subtasks for context
    remaining = [s for s in get_all_subtasks(cfg.obsidian_daily_dir) if not s.done]
    if not remaining:
        display.success("All sub-tasks complete. Run 'wyndle wrap' to end the day.")
        return

    display.dim(f"{len(remaining)} sub-tasks remaining.")
    display.console.print()

    # Hand off to start
    from wyndle.commands.start import run as start_run
    start_run(cfg, state)
