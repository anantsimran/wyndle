"""wyndle next -- Close current subtask and start the next one.

Convenience command that combines the end-of-subtask flow with
starting a new focus block.  Pauses the active subtask, offers
to mark it done, then hands off to ``wyndle start``.
"""

from __future__ import annotations

from wyndle.commands.start import close_active_subtask
from wyndle.commands.start import run as start_run
from wyndle.lib import display
from wyndle.lib.config import WyndleConfig
from wyndle.lib.daily_notes import get_all_subtasks
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

    if not close_active_subtask(cfg, state):
        display.dim("No active sub-task to close.")
        display.console.print()

    remaining = [s for s in get_all_subtasks(cfg.daily_dir) if not s.done]
    if not remaining:
        display.success("All sub-tasks complete. Run 'wyndle wrap' to end the day.")
        return

    display.dim(f"{len(remaining)} sub-tasks remaining.")
    display.console.print()
    start_run(cfg, state)
