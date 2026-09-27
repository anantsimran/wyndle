"""wyndle stuck — Interactive diagnostic for when you can't start.

Presents five common ADHD-related blocks and walks the user through
a targeted micro-intervention for each:

1. Don't know where to start -> decompose into first physical action.
2. Can't make myself do it   -> activation energy gap strategies.
3. Task feels too big        -> shrink to a 15-minute version.
4. Keep getting distracted   -> distraction redirect checklist.
5. Frozen                    -> body-first nervous-system reset.

Each handler ends with a short timer so the user takes *some* action
before leaving the command.
"""

from __future__ import annotations

import random

from wyndle.lib import display
from wyndle.lib.config import WyndleConfig
from wyndle.lib.daily_notes import log_to_daily
from wyndle.lib.state import State
from wyndle.lib.timer import timer_display

_SHRINK_PROMPTS = [
    "That sounds like a project, not a task. What's the FIRST physical action?",
    "Smaller. What would the first 2 minutes look like?",
    "If you could only do ONE step right now, what is it?",
    "What file would you open first? Start there.",
    "Imagine you're explaining to someone: 'First, I would...' — finish that sentence.",
]


def run(cfg: WyndleConfig, state: State) -> None:
    """Present the stuck diagnostic and run the matching handler.

    Args:
        cfg:   Current configuration.
        state: Current state store.
    """
    display.header("Stuck? Let's break it down.")

    current_task = state.get("today_current_task", "")
    if current_task:
        display.dim(f"Current task: {current_task}")
        display.console.print()

    display.accent("What's happening right now?")
    display.console.print()
    display.dim("1) I don't know WHERE to start")
    display.dim("2) I know what to do but CAN'T make myself do it")
    display.dim("3) The task feels too big / overwhelming")
    display.dim("4) I keep getting distracted")
    display.dim("5) I'm just... frozen")
    display.console.print()
    choice = display.prompt("Number?")
    display.console.print()

    handler = {
        "1": _dont_know_where,
        "2": _cant_make_myself,
        "3": _too_big,
        "4": _distracted,
    }.get(choice, _frozen)
    handler(cfg, state, current_task)


def _log(cfg: WyndleConfig, msg: str) -> None:
    """Log a stuck event to the daily note if the feature is enabled."""
    if cfg.features.notes:
        log_to_daily(cfg.daily_dir, msg)


def _dont_know_where(cfg: WyndleConfig, state: State, task: str) -> None:
    """Handler: user doesn't know where to begin."""
    display.accent(random.choice(_SHRINK_PROMPTS))
    display.console.print()
    action = display.prompt("So, what's the first physical action?")
    display.success("Great. Do ONLY that. Nothing else.")
    display.dim("Starting a 2-minute timer. Just do that one thing.")
    display.console.print()
    timer_display(120, "just the one thing")
    _log(cfg, f"Stuck on **{task}** -> unblocked with: {action}")


def _cant_make_myself(cfg: WyndleConfig, state: State, task: str) -> None:
    """Handler: user knows what to do but can't initiate."""
    display.accent("This is the ADHD activation energy gap. Try one of these:")
    display.console.print()
    display.dim("-> Put on music you like (background dopamine)")
    display.dim("-> Narrate what you're doing out loud")
    display.dim("-> Set a 5-min timer: 'I only have to do this for 5 minutes'")
    display.dim("-> Change your physical position")
    display.console.print()
    if display.confirm("Want a 5-minute 'just try it' timer?"):
        timer_display(300, "just trying")
        display.success("Five minutes done. Keep going or start a block.")
    _log(cfg, f"Stuck (activation energy) on **{task}**")


def _too_big(cfg: WyndleConfig, state: State, task: str) -> None:
    """Handler: task feels overwhelming."""
    display.accent("Let's shrink it until it's not scary.")
    display.console.print()
    big_task = display.prompt("Describe the task in one sentence:")
    display.console.print()
    display.accent("Now: what's a version of this that takes 15 minutes MAX?")
    tiny_version = display.prompt("The tiny version:")
    display.console.print()
    display.success("Do the tiny version. That's your only job.")
    display.dim("Starting 15-minute block...")
    display.console.print()
    timer_display(cfg.timer.short_block * 60, "tiny version")
    _log(cfg, f"Stuck on **{big_task}** -> shrunk to: {tiny_version}")


def _distracted(cfg: WyndleConfig, state: State, task: str) -> None:
    """Handler: user keeps getting pulled away."""
    display.accent("Distraction is your brain seeking dopamine. Let's redirect it.")
    display.console.print()
    display.dim("Quick checklist:")
    display.dim("-> Phone: face down, in another room?")
    display.dim("-> Browser: close non-work tabs (all of them)")
    display.dim("-> Notifications: DND mode on?")
    display.console.print()
    distraction = display.prompt("What were you about to distract yourself with?")
    display.dim(f"'{distraction}' will still be there after your focus block.")
    display.console.print()
    if display.confirm("Ready to re-focus? Start a 15-min block?"):
        timer_display(cfg.timer.short_block * 60, "re-focused")
    _log(cfg, f"Stuck (distracted by {distraction}) on **{task}**")


def _frozen(cfg: WyndleConfig, state: State, task: str) -> None:
    """Handler: user is completely frozen (nervous system overwhelmed)."""
    display.accent("Frozen is okay. Your nervous system is overwhelmed.")
    display.accent("We're going to do a body-first reset.")
    display.console.print()
    display.bold_print("Stand up. Take 3 deep breaths (4 in, 7 hold, 8 out).")
    display.bold_print("Shake your hands out for 10 seconds.")
    display.console.print()
    display.dim("60-second timer. Just breathe.")
    timer_display(60, "breathing")
    display.console.print()
    display.accent("Now: what is ONE tiny thing you can do in 2 minutes?")
    tiny_action = display.prompt("Anything. What is it?")
    display.dim("Do it now. 2 minutes.")
    timer_display(120, "unfreezing")
    _log(cfg, f"Stuck (frozen) -> tiny action: {tiny_action}")
