"""File-based key-value state that survives terminal restarts.

Each key is a file in ``~/.wyndle/state/``.  The value is the file's
text content.  This keeps the implementation dependency-free (no
SQLite, no JSON merging) and trivially inspectable from the shell::

    cat ~/.wyndle/state/today_started   # "true"

Subtask time tracking
---------------------
Each subtask is keyed by a 10-char MD5 prefix of its normalised text:

``st_<key>_elapsed``
    Accumulated seconds (written as an ``int`` string).
``st_<key>_active_since``
    Unix epoch when the timer started (``0`` = paused).
``today_active_subtask``
    The hash key of the currently running subtask.
``today_active_subtask_text``
    The raw text of the currently running subtask.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from wyndle.lib import time_utils
from wyndle.lib.markdown_dom import strip_estimate


def _subtask_key(text: str) -> str:
    """Derive a short deterministic key from subtask text.

    The estimate and task-tier markers are stripped so that editing them
    does not create a new timer entry.

    Args:
        text: Raw subtask text, may include ``~30m`` etc.

    Returns:
        10-character hex string.
    """
    clean = strip_estimate(text).lower()
    return hashlib.md5(clean.encode()).hexdigest()[:10]


class State:
    """Simple key-value store backed by individual files in a directory.

    Args:
        state_dir: Path to the directory used for storage.
                   Created automatically if it doesn't exist.
    """

    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)

    # -- Primitive accessors --

    def set(self, key: str, value: str) -> None:
        """Write *value* to the file named *key*."""
        (self.state_dir / key).write_text(value)

    def get(self, key: str, default: str = "") -> str:
        """Read the value for *key*, returning *default* if missing."""
        path = self.state_dir / key
        return path.read_text().strip() if path.exists() else default

    def get_int(self, key: str, default: int = 0) -> int:
        """Read *key* as an integer, returning *default* on failure."""
        try:
            return int(self.get(key, str(default)))
        except ValueError:
            return default

    def exists(self, key: str) -> bool:
        """Return ``True`` if *key* has been written."""
        return (self.state_dir / key).exists()

    def clear(self, key: str) -> None:
        """Delete *key* if it exists."""
        (self.state_dir / key).unlink(missing_ok=True)

    # -- Day lifecycle --

    def clear_day(self) -> None:
        """Remove all ``today_*`` and ``st_*`` files for a fresh day."""
        for pattern in ("today_*", "st_*"):
            for path in self.state_dir.glob(pattern):
                path.unlink(missing_ok=True)

    def is_new_day(self) -> bool:
        """Return ``True`` if the stored date differs from today."""
        return self.get("today_date", "") != time_utils.now_date_str()

    # -- Subtask timer --

    def start_subtask_timer(self, subtask_text: str) -> None:
        """Begin timing *subtask_text*, pausing any active subtask first.

        If the subtask already has accumulated time it is preserved;
        only the ``active_since`` epoch is reset.

        Args:
            subtask_text: Raw subtask text (used for key derivation).
        """
        self.pause_active_subtask()
        key = _subtask_key(subtask_text)
        if not self.get_int(f"st_{key}_started"):
            self.set(f"st_{key}_started", str(time_utils.epoch_now()))
        self.set(f"st_{key}_active_since", str(time_utils.epoch_now()))
        self.set("today_active_subtask", key)
        self.set("today_active_subtask_text", subtask_text)
        self.set("today_last_subtask_text", subtask_text)

    def pause_active_subtask(self) -> str | None:
        """Pause the currently active subtask and flush elapsed time.

        Returns:
            The raw text of the paused subtask, or ``None`` if nothing
            was active.
        """
        if self.exists("today_ui_kind"):
            self.set_block_active(False)
            for key in ("kind", "deadline", "duration", "started", "task"):
                self.clear(f"today_ui_{key}")
        active_key = self.get("today_active_subtask", "")
        if not active_key:
            return None
        active_text = self.get("today_active_subtask_text", "")
        active_since = self.get_int(f"st_{active_key}_active_since", 0)
        if active_since > 0:
            delta = max(0, time_utils.epoch_now() - active_since)
            prev = self.get_int(f"st_{active_key}_elapsed", 0)
            self.set(f"st_{active_key}_elapsed", str(prev + delta))
            self.set(f"st_{active_key}_active_since", "0")
        self.clear("today_active_subtask")
        self.clear("today_active_subtask_text")
        return active_text or None

    def get_subtask_elapsed(self, subtask_text: str) -> int:
        """Total elapsed seconds for *subtask_text*, including live time.

        If the subtask is currently active, the live (un-flushed)
        interval is added to the stored total.

        Args:
            subtask_text: Raw subtask text.

        Returns:
            Elapsed seconds.
        """
        key = _subtask_key(subtask_text)
        elapsed = self.get_int(f"st_{key}_elapsed", 0)
        if self.get("today_active_subtask", "") == key:
            active_since = self.get_int(f"st_{key}_active_since", 0)
            if active_since > 0:
                elapsed += max(0, time_utils.epoch_now() - active_since)
        return elapsed

    def get_subtask_elapsed_min(self, subtask_text: str) -> int:
        """Total elapsed **minutes** for *subtask_text* (truncated)."""
        return self.get_subtask_elapsed(subtask_text) // 60

    def get_subtask_started(self, subtask_text: str) -> int:
        """First time this subtask's timer was started today."""
        return self.get_int(f"st_{_subtask_key(subtask_text)}_started")

    def set_subtask_elapsed(self, subtask_text: str, seconds: int) -> None:
        """Replace accumulated time without interrupting a running interval."""
        key = _subtask_key(subtask_text)
        self.set(f"st_{key}_elapsed", str(seconds))
        if self.is_subtask_active(subtask_text):
            self.set(f"st_{key}_active_since", str(time_utils.epoch_now()))

    def is_subtask_active(self, subtask_text: str) -> bool:
        """Return ``True`` if *subtask_text* is the currently timed subtask."""
        return self.get("today_active_subtask", "") == _subtask_key(subtask_text)

    def get_active_subtask_text(self) -> str | None:
        """Return the raw text of the active subtask, or ``None``."""
        text = self.get("today_active_subtask_text", "")
        return text if text else None

    def get_last_subtask_text(self) -> str | None:
        """Return the raw text of the most recently active subtask.

        Unlike :meth:`get_active_subtask_text`, this returns the last
        subtask even after it has been paused — used by ``wyndle restart``.
        """
        text = self.get("today_last_subtask_text", "")
        return text if text else None

    # -- Focus block tracking --

    def set_block_active(self, active: bool) -> None:
        """Mark whether a focus block timer is currently running.

        The daemon checks this to avoid firing notifications mid-block.
        """
        if active:
            self.set("today_block_active", "true")
            self.clear("today_block_end")
        else:
            self.clear("today_block_active")

    def is_block_active(self) -> bool:
        """Return ``True`` if a focus block timer is currently running."""
        if self.exists("today_ui_deadline"):
            return self.get_int("today_ui_deadline") > time_utils.epoch_now()
        return self.get("today_block_active", "") == "true"
