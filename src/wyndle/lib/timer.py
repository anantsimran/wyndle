"""Focus block timer — 5 / 15 / 30 minute blocks with macOS notifications.

The timer is a blocking countdown displayed in the terminal.  When it
finishes, a macOS notification fires (if enabled) and the user is
prompted for their next action.

Auto-extend
-----------
When a block ends, ``today_block_end`` is written to state.  The
background daemon (:mod:`wyndle.lib.notifier`) checks this value and
sends a nudge notification if no new command is run, but the subtask
timer keeps running so no time is lost.
"""

from __future__ import annotations

import sys
import time

from wyndle.lib import display, time_utils
from wyndle.lib.config import WyndleConfig
from wyndle.lib.daily_notes import strip_estimate
from wyndle.lib.notifier import notify
from wyndle.lib.state import State


def timer_display(total_seconds: int, label: str) -> None:
    """Show a live countdown timer in the terminal.

    Renders a progress bar that updates every second.  The colour
    shifts to orange in the last 60 seconds.  Handles ``Ctrl+C``
    gracefully (the timer simply stops early).

    Args:
        total_seconds: Duration of the countdown.
        label:         Short label shown alongside the progress bar.
    """
    start = time.time()
    remaining = total_seconds

    sys.stdout.write("\033[?25l")  # hide cursor
    sys.stdout.flush()

    try:
        while remaining > 0:
            mins = remaining // 60
            secs = remaining % 60
            progress = int((total_seconds - remaining) * 30 / max(total_seconds, 1))
            bar = "█" * progress + "░" * (30 - progress)

            colour = "\033[38;5;75m"
            if remaining < 60:
                colour = "\033[38;5;214m"

            sys.stdout.write(
                f"\r{colour}  ⏱  {mins:02d}:{secs:02d}  "
                f"\033[38;5;245m[{bar}]\033[0m  "
                f"\033[38;5;245m{label}\033[0m  "
            )
            sys.stdout.flush()
            time.sleep(1)
            elapsed = int(time.time() - start)
            remaining = max(0, total_seconds - elapsed)
    finally:
        sys.stdout.write("\033[?25h\n")  # show cursor
        sys.stdout.flush()


def _choose_block_length(cfg: WyndleConfig) -> int:
    """Prompt the user to pick a block duration.

    Options are drawn from the ``timer`` config section:
    ``micro_block`` (5m), ``short_block`` (15m), ``long_block`` (30m).

    Args:
        cfg: Current configuration.

    Returns:
        Chosen duration in minutes.
    """
    display.accent("How long?")
    display.dim(f"1) {cfg.timer.micro_block} minutes")
    display.dim(f"2) {cfg.timer.short_block} minutes")
    display.dim(f"3) {cfg.timer.long_block} minutes")
    display.console.print()
    choice = display.prompt("Choice? [1/2/3]")

    if choice == "1":
        return cfg.timer.micro_block
    if choice == "3":
        return cfg.timer.long_block
    return cfg.timer.short_block


def start_focus_block(
    subtask_text: str,
    estimate_min: int,
    cfg: WyndleConfig,
    state: State,
    block_min_override: int = 0,
) -> None:
    """Run a focus block then overflow loop until Ctrl+C.

    Flow: choose duration -> main timer -> infinite 5-min overflows.
    ``today_block_active`` stays True throughout so the daemon never
    fires mid-block.  Ctrl+C breaks to the "What next?" menu.

    Args:
        subtask_text:      Raw subtask text (with ``~Xm`` estimate).
        estimate_min:      Parsed estimate in minutes (``0`` if none).
        cfg:               Current configuration.
        state:             Current state store.
        block_min_override: If > 0, skip the duration prompt and use
                           this value directly.
    """
    display_name = strip_estimate(subtask_text)
    _show_estimate_context(state, subtask_text, estimate_min, display_name)

    block_min = block_min_override if block_min_override > 0 else _choose_block_length(cfg)

    display.console.print()
    display.dim(f"Starting {block_min}m block. Notification at each boundary.")
    display.console.print()

    state.set_block_active(True)
    try:
        _run_main_block(block_min, display_name, subtask_text, estimate_min, cfg, state)
        _run_overflow_loop(display_name, subtask_text, estimate_min, cfg, state)
    except KeyboardInterrupt:
        pass
    finally:
        state.set_block_active(False)
        state.set("today_block_end", str(time_utils.epoch_now()))

    _show_block_summary(state, subtask_text, estimate_min, cfg)
    _prompt_next_action(subtask_text, estimate_min, cfg, state)


def _show_estimate_context(
    state: State, subtask_text: str, estimate_min: int, display_name: str,
) -> None:
    """Print estimate and elapsed info before starting a block."""
    elapsed_before = state.get_subtask_elapsed_min(subtask_text)
    display.header(f"Focus: {display_name}")
    if estimate_min:
        display.info(f"Estimated: [bold]{estimate_min}m[/bold]")
        if elapsed_before:
            remaining_est = estimate_min - elapsed_before
            display.info(
                f"Already done: [bold]{elapsed_before}m[/bold] "
                f"({remaining_est}m remaining est.)"
            )
    elif elapsed_before:
        display.dim(f"Already done: {elapsed_before}m")
    display.console.print()


def _run_main_block(
    block_min: int, display_name: str, subtask_text: str,
    estimate_min: int, cfg: WyndleConfig, state: State,
) -> None:
    """Run the main timed block and fire the completion notification."""
    timer_display(block_min * 60, display_name[:40])
    _notify_block_done(block_min, display_name, subtask_text, estimate_min, cfg, state)


def _run_overflow_loop(
    display_name: str, subtask_text: str,
    estimate_min: int, cfg: WyndleConfig, state: State,
) -> None:
    """Run infinite 5-min overflow blocks until Ctrl+C."""
    while True:
        display.dim("  5m overflow started...")
        timer_display(300, f"{display_name[:35]} +5m")
        _notify_block_done(5, display_name, subtask_text, estimate_min, cfg, state)


def _notify_block_done(
    block_min: int, display_name: str, subtask_text: str,
    estimate_min: int, cfg: WyndleConfig, state: State,
) -> None:
    """Fire notification and update focused-minute counter."""
    elapsed_now = state.get_subtask_elapsed_min(subtask_text)
    est_info = f" (est: {estimate_min}m)" if estimate_min else ""
    if cfg.features.notifications:
        notify(f"⏱ {block_min}m done — 5m overflow started",
               f"'{display_name[:40]}' — {elapsed_now}m total{est_info}")
    prev = state.get_int("today_focused_min", 0)
    state.set("today_focused_min", str(prev + block_min))


def _show_block_summary(
    state: State, subtask_text: str, estimate_min: int, cfg: WyndleConfig,
) -> None:
    """Print summary after Ctrl+C breaks the overflow loop."""
    display_name = strip_estimate(subtask_text)
    elapsed_now = state.get_subtask_elapsed_min(subtask_text)
    est_info = f" (est: {estimate_min}m)" if estimate_min else ""
    total_focused = state.get_int("today_focused_min", 0)

    display.console.print()
    display.success(f"Block ended: {display_name}")
    display.dim(f"  Sub-task total: {elapsed_now}m{est_info}")
    display.dim(f"  Day total: {total_focused}m focused")

    mins_to_stop = time_utils.minutes_until(cfg.hard_stop)
    if 0 < mins_to_stop < 30:
        display.warn(f"Hard stop in {time_utils.hours_minutes(mins_to_stop)}.")


def _prompt_next_action(
    subtask_text: str, estimate_min: int,
    cfg: WyndleConfig, state: State,
) -> None:
    """Show the post-block menu."""
    display.console.print()
    display.accent("What next?")
    display.dim("1) Another block on same sub-task")
    display.dim("2) Switch to different sub-task")
    display.dim("3) Open your daily note to update")
    display.dim("4) Done for now")
    display.console.print()
    next_choice = display.prompt("Choice? [1/2/3/4]")

    if next_choice == "1":
        start_focus_block(subtask_text, estimate_min, cfg, state)
    elif next_choice == "2":
        from wyndle.commands.start import switch_task
        switch_task(cfg, state)
    elif next_choice == "3":
        from wyndle.lib.daily_notes import open_daily_note
        open_daily_note(cfg.daily_dir)
        display.dim("Daily note opened. Run 'wyndle start' when ready.")
    else:
        state.pause_active_subtask()
        display.dim("Sub-task paused. Run 'wyndle start' or 'wyndle switch' to continue.")
