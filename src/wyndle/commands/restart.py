"""wyndle restart [minutes] — Restart the last focus block.

Resumes the most recently active subtask and starts a new focus block
with the specified duration, skipping the interactive duration prompt.

Usage::

    wyndle restart        # restart last subtask, prompt for duration
    wyndle restart 5      # restart with a 5-minute block
    wyndle restart 15     # restart with a 15-minute block
    wyndle restart 30     # restart with a 30-minute block
"""

from __future__ import annotations

from wyndle.lib import display
from wyndle.lib.config import WyndleConfig
from wyndle.lib.daily_notes import log_to_daily, parse_estimate, strip_estimate
from wyndle.lib.state import State
from wyndle.lib.timer import start_focus_block

_VALID_DURATIONS = {5, 15, 30}


def _resolve_subtask_text(state: State) -> str | None:
    """Find the subtask to restart.

    Checks active subtask first, then falls back to the last-used
    subtask stored in state.

    Returns:
        Raw subtask text, or ``None`` if nothing found.
    """
    return state.get_active_subtask_text() or state.get_last_subtask_text()


def _parse_duration(raw: str) -> int:
    """Parse and validate a duration string.

    Args:
        raw: User-supplied minutes string (e.g. ``"15"``).

    Returns:
        Duration in minutes, or ``0`` if invalid (will trigger
        the interactive prompt in ``start_focus_block``).
    """
    try:
        mins = int(raw)
    except (ValueError, TypeError):
        return 0
    return mins if mins in _VALID_DURATIONS else 0


def run(cfg: WyndleConfig, state: State, minutes: str = "") -> None:
    """Restart the last focus block with an optional fixed duration.

    Args:
        cfg:     Current configuration.
        state:   Current state store.
        minutes: Duration string (``"5"``, ``"15"``, or ``"30"``).
                 Empty or invalid triggers the interactive prompt.
    """
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
