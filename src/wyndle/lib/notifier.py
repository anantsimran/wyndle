"""Background notifier — macOS notification banners via launchd.

Called every 60 seconds by the launchd daemon.  Reads state files,
evaluates conditions, and fires native macOS banners.

Notification types
------------------
day_not_started
    Escalating nudges if ``wyndle morning`` hasn't been run.
idle_nothing_active
    No focus block or break is running.
auto_extend
    A block timer finished but the subtask is still active — the timer
    keeps running silently and a nudge is sent.
hard stop
    Escalating warnings as the configured stop time approaches and passes.
milestones
    Celebrations at 60 / 120 / 180 minutes of focused time.
post-wrap
    Wind-down and bedtime reminders after ``wyndle wrap``.

Configuration
-------------
Set ``features.notifications: false`` in ``~/.wyndle/config.yaml`` to
disable all macOS banners.  The daemon will still run but do nothing.
"""

from __future__ import annotations

import subprocess
import sys
from string import Formatter

from wyndle.lib import time_utils
from wyndle.lib.config import WyndleConfig, load_config
from wyndle.lib.state import State

# ---------------------------------------------------------------------------
# Notification catalogue
# ---------------------------------------------------------------------------
# Each entry defines a template for one notification type.
#
#   title / message   — may contain ``{placeholder}`` vars filled at runtime.
#   sound             — macOS system sound name.
#   cooldown_min      — minimum minutes between repeated fires of the same key.

NOTIFICATION_CONFIG: dict[str, dict] = {
    # -- Day Not Started --
    "day_not_started": {
        "title": "Wyndle",
        "message": "Day not started. Open terminal -> wyndle morning",
        "sound": "Morse",
        "cooldown_min": 30,
    },
    "day_not_started_late": {
        "title": "Wyndle — Late Start",
        "message": "No judgment. wyndle morning. One task.",
        "sound": "Morse",
        "cooldown_min": 20,
    },
    "day_not_started_severe": {
        "title": "Wyndle — Very Late",
        "message": "Only {mins_left} left. wyndle morning — pick ONE thing.",
        "sound": "Sosumi",
        "cooldown_min": 20,
    },
    # -- Idle --
    "idle_nothing_active": {
        "title": "Nothing Active",
        "message": "No focus block or break running. wyndle start or wyndle break",
        "sound": "Morse",
        "cooldown_min": 15,
    },
    "idle_frozen": {
        "title": "Frozen?",
        "message": "wyndle stuck — let's break it down.",
        "sound": "Submarine",
        "cooldown_min": 30,
    },
    # -- Auto-extend --
    "auto_extend": {
        "title": "Still Working?",
        "message": "Block ended on '{subtask}'. Timer still running. "
                   "wyndle start for new block or wyndle break.",
        "sound": "Morse",
        "cooldown_min": 15,
    },
    # -- Hard Stop --
    "stop_60": {
        "title": "1 Hour Left",
        "message": "Hard stop at {hard_stop}. {focused}m focused. Plan your last block.",
        "sound": "Morse",
        "cooldown_min": 30,
    },
    "stop_30": {
        "title": "30 Minutes Left",
        "message": "{mins_to_stop}m left. Start wrapping up.",
        "sound": "Sosumi",
        "cooldown_min": 15,
    },
    "stop_15": {
        "title": "{mins_to_stop}m to Hard Stop",
        "message": "Finish what you're doing. wyndle wrap soon.",
        "sound": "Sosumi",
        "cooldown_min": 10,
    },
    "at_stop": {
        "title": "Shutdown Time",
        "message": "It's {now_friendly}. Run wyndle wrap.{ext_msg}",
        "sound": "Funk",
        "cooldown_min": 5,
    },
    "past_grace": {
        "title": "STOP WORKING",
        "message": "{effective_past}m past hard stop. wyndle wrap. NOW.",
        "sound": "Funk",
        "cooldown_min": 3,
    },
    "way_past": {
        "title": "SERIOUSLY. STOP.",
        "message": "{effective_past}m past stop. Close the laptop.",
        "sound": "Funk",
        "cooldown_min": 2,
    },
    # -- Post-Wrap --
    "wind_down": {
        "title": "Wind Down",
        "message": "Phone on charger in another room. Dim the lights.",
        "sound": "Purr",
        "cooldown_min": 20,
    },
    "go_to_sleep": {
        "title": "Bedtime",
        "message": "{sleep_msg}",
        "sound": "Purr",
        "cooldown_min": 15,
    },
    # -- Milestones --
    "milestone_180": {
        "title": "3 Hours Focused!",
        "message": "180m of real work. Exceptional day.",
        "sound": "Morse",
        "cooldown_min": 0,  # once-per-day guard lives in _check_milestones
    },
    "milestone_120": {
        "title": "2 Hours Focused!",
        "message": "120m today. Solid.",
        "sound": "Morse",
        "cooldown_min": 0,  # once-per-day guard lives in _check_milestones
    },
    "milestone_60": {
        "title": "First Hour Done",
        "message": "60m focused. Real progress.",
        "sound": "Morse",
        "cooldown_min": 0,  # once-per-day guard lives in _check_milestones
    },
}

_formatter = Formatter()


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _safe_format(template: str, **kwargs: object) -> str:
    """Format a string template, silently skipping missing placeholders.

    Args:
        template: String with ``{name}`` placeholders.
        **kwargs: Values to substitute.

    Returns:
        Formatted string.
    """
    result = template
    for _, field_name, _, _ in _formatter.parse(template):
        if field_name is not None and field_name in kwargs:
            result = result.replace("{" + field_name + "}", str(kwargs[field_name]))
    return result


def notify(title: str, message: str, sound: str = "Funk") -> None:
    """Fire a native macOS notification banner.

    No-op on non-macOS platforms.

    Args:
        title:   Notification title.
        message: Notification body text.
        sound:   macOS system sound name (e.g. ``Morse``, ``Funk``).
    """
    if sys.platform != "darwin":
        return
    title = title.replace('"', '\\"')
    message = message.replace('"', '\\"')
    script = (
        f'display notification "{message}" '
        f'with title "{title}" sound name "{sound}"'
    )
    try:
        subprocess.run(
            ["osascript", "-e", script],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def _should_notify(state: State, key: str, cooldown_min: int = 5) -> bool:
    """Return ``True`` if enough time has passed since the last fire of *key*.

    Also updates the cooldown timestamp when returning ``True``.

    Args:
        state:        Current :class:`State` instance.
        key:          Notification key (e.g. ``"stop_30"``).
        cooldown_min: Minimum minutes between fires.
    """
    lock_key = f"_notify_{key}"
    last = state.get_int(lock_key, 0)
    now = time_utils.epoch_now()
    if now - last < cooldown_min * 60:
        return False
    state.set(lock_key, str(now))
    return True


def _fire(state: State, key: str, **kwargs: object) -> bool:
    """Look up *key* in :data:`NOTIFICATION_CONFIG` and fire if cooldown allows.

    Args:
        state:    Current :class:`State` instance.
        key:      Key into :data:`NOTIFICATION_CONFIG`.
        **kwargs: Template variables for the title/message.

    Returns:
        ``True`` if the notification was actually sent.
    """
    entry = NOTIFICATION_CONFIG.get(key)
    if entry is None:
        return False
    if not _should_notify(state, key, cooldown_min=entry.get("cooldown_min", 5)):
        return False
    notify(
        _safe_format(entry["title"], **kwargs),
        _safe_format(entry["message"], **kwargs),
        entry.get("sound", "Funk"),
    )
    return True


# ---------------------------------------------------------------------------
# Condition checkers
# ---------------------------------------------------------------------------

def _check_day_not_started(cfg: WyndleConfig, state: State) -> bool:
    """Fire escalating nudges if the day hasn't been started yet.

    Returns ``True`` if the day is *not* started (caller should skip
    other checks).
    """
    today = time_utils.now_date_str()
    if state.get("today_date", "") == today and state.get("today_started", "false") == "true":
        return False

    now_dt = time_utils.now()
    if now_dt < time_utils.time_to_datetime(cfg.work_start):
        return True
    if now_dt > time_utils.time_to_datetime(cfg.hard_stop):
        return True

    sev_dt = time_utils.time_to_datetime(cfg.late_thresholds.severe)
    mod_dt = time_utils.time_to_datetime(cfg.late_thresholds.moderate)

    if now_dt >= sev_dt:
        _fire(state, "day_not_started_severe",
              mins_left=time_utils.hours_minutes(time_utils.minutes_until(cfg.hard_stop)))
    elif now_dt >= mod_dt:
        _fire(state, "day_not_started_late")
    else:
        _fire(state, "day_not_started")
    return True


def _check_idle_nothing_active(cfg: WyndleConfig, state: State) -> None:
    """Notify if no focus block and no break is currently active.

    If a subtask *is* active but the block timer has ended, this
    triggers the **auto-extend** notification instead.

    v1.2.1: skips entirely when ``today_block_active`` is set, fixing
    the bug where stale ``today_block_end`` caused mid-block notifications.
    """
    # Block is live (main or overflow) — do nothing
    if state.is_block_active():
        return

    active = state.get("today_active_subtask", "")
    if active:
        # Active subtask — check for auto-extend (block ended but timer kept running)
        block_end = state.get_int("today_block_end", 0)
        if block_end > 0:
            since_end = (time_utils.epoch_now() - block_end) // 60
            if since_end >= 5:
                from wyndle.lib.obsidian import strip_estimate
                subtask_text = state.get("today_active_subtask_text", "your task")
                _fire(state, "auto_extend", subtask=strip_estimate(subtask_text)[:40])
        return

    # Nothing active at all
    day_start = state.get("today_start_time", "")
    if not day_start:
        return
    try:
        idle = time_utils.now() - time_utils.time_to_datetime(day_start)
        idle_min = int(idle.total_seconds() / 60)
    except (ValueError, TypeError):
        return
    if idle_min < 10:
        return

    focused = state.get_int("today_focused_min", 0)
    if focused == 0 and idle_min > 45:
        _fire(state, "idle_frozen")
    else:
        _fire(state, "idle_nothing_active")


def _check_hard_stop(cfg: WyndleConfig, state: State) -> bool:
    """Fire escalating hard-stop warnings.

    Returns ``True`` if the user is at or past their stop time (caller
    should skip other checks).
    """
    if not cfg.features.hard_stop:
        return False

    mins_to_stop = time_utils.minutes_until(cfg.hard_stop)
    extensions = state.get_int("today_extensions", 0)
    extended_min = extensions * cfg.hard_stop_settings.extension_min
    max_ext = cfg.hard_stop_settings.max_extensions
    grace = cfg.hard_stop_settings.grace_min
    effective_past = -mins_to_stop - extended_min

    if 30 < mins_to_stop <= 60:
        _fire(state, "stop_60", hard_stop=cfg.hard_stop,
              focused=state.get_int("today_focused_min", 0))
        return False
    if 15 < mins_to_stop <= 30:
        _fire(state, "stop_30", mins_to_stop=mins_to_stop)
        return False
    if 0 < mins_to_stop <= 15:
        _fire(state, "stop_15", mins_to_stop=mins_to_stop)
        return False
    if 0 <= effective_past < grace:
        ext_msg = f" Or extend ({extensions}/{max_ext} used)." if extensions < max_ext else ""
        _fire(state, "at_stop", now_friendly=time_utils.now_friendly(), ext_msg=ext_msg)
        return True
    if grace <= effective_past < grace + 20:
        _fire(state, "past_grace", effective_past=int(effective_past))
        return True
    if effective_past >= grace + 20:
        _fire(state, "way_past", effective_past=int(effective_past))
        return True
    return False


def _check_post_wrap(cfg: WyndleConfig, state: State) -> None:
    """Fire wind-down and bedtime reminders after ``wyndle wrap``."""
    try:
        sleep_dt = time_utils.time_to_datetime(cfg.sleep_target)
        mins_to_sleep = int((sleep_dt - time_utils.now()).total_seconds() / 60)
        if 0 < mins_to_sleep <= 30:
            _fire(state, "wind_down")
        elif -30 < mins_to_sleep <= 0:
            tomorrow = state.get("tomorrow_first_task", "")
            msg = "Past your sleep target. Rest."
            if tomorrow:
                msg += f" Tomorrow: {tomorrow[:50]}"
            _fire(state, "go_to_sleep", sleep_msg=msg)
    except (ValueError, TypeError):
        pass


def _check_milestones(state: State) -> None:
    """Fire milestone celebrations at 60/120/180 minutes, once per day each.

    The once-per-day guard is a ``today_*`` marker (wiped by
    :meth:`State.clear_day`) rather than the cooldown, which would
    suppress the same milestone on the following days.
    """
    focused = state.get_int("today_focused_min", 0)
    for threshold in (180, 120, 60):
        if focused >= threshold:
            marker = f"today_milestone_{threshold}"
            if not state.exists(marker):
                if _fire(state, f"milestone_{threshold}"):
                    state.set(marker, "true")
            return


def _check_scheduled_notifications(cfg: WyndleConfig, state: State) -> None:
    """Fire config-driven notifications at their scheduled times.

    Each entry in ``cfg.scheduled_notifications`` has a ``time`` (HH:MM)
    and either a static ``message`` or a dynamic ``type``.

    Supported dynamic types:

    ``remaining_work``
        Computes the sum of estimates for uncompleted subtasks and
        sends a message like ``"~45m of estimated work remaining"``.

    Each notification fires at most once per day: the fire window is
    two minutes, so a 12-hour cooldown keyed by the scheduled time
    blocks repeats.  A full 1440-minute cooldown would not work, since
    each day's fire lands a little later than the last and eventually
    falls outside the window.
    """
    now_dt = time_utils.now()
    for entry in cfg.scheduled_notifications:
        sched_time = entry.get("time", "")
        if not sched_time:
            continue
        try:
            target = time_utils.time_to_datetime(sched_time)
        except (ValueError, TypeError):
            continue
        # Fire if we're within 2 minutes after the scheduled time
        delta_sec = (now_dt - target).total_seconds()
        if not (0 <= delta_sec <= 120):
            continue
        cooldown_key = f"sched_{sched_time.replace(':', '')}"
        if not _should_notify(state, cooldown_key, cooldown_min=720):
            continue
        notif_type = entry.get("type", "")
        if notif_type == "remaining_work":
            _fire_remaining_work(cfg)
        else:
            message = entry.get("message", "")
            if message:
                notify("Wyndle", message, sound="Morse")


def _fire_remaining_work(cfg: WyndleConfig) -> None:
    """Send a notification with the total estimated minutes remaining."""
    from wyndle.lib.obsidian import get_remaining_estimate_min
    remaining = get_remaining_estimate_min(cfg.obsidian_daily_dir)
    if remaining > 0:
        msg = f"~{time_utils.hours_minutes(remaining)} of estimated work remaining"
        notify("Wyndle", msg, sound="Morse")
    else:
        notify("Wyndle", "No estimated work remaining. Nice!", sound="Morse")


# ---------------------------------------------------------------------------
# Main entry point (called by launchd every 60s)
# ---------------------------------------------------------------------------

def check_and_notify() -> None:
    """Run all notification checks in priority order.

    Called by the launchd daemon.  Exits early when a higher-priority
    condition (day not started, wrapped, hard stop) fires.
    """
    cfg = load_config()
    if not cfg.features.notifications:
        return
    state = State(cfg.state_dir)

    if _check_day_not_started(cfg, state):
        return
    if state.get("today_wrapped", "false") == "true":
        _check_post_wrap(cfg, state)
        return
    if _check_hard_stop(cfg, state):
        return
    _check_idle_nothing_active(cfg, state)
    _check_milestones(state)
    _check_scheduled_notifications(cfg, state)


def main() -> None:
    """Entry point for ``python -m wyndle.lib.notifier``."""
    try:
        check_and_notify()
    except Exception:
        pass


if __name__ == "__main__":
    main()
