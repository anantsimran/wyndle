"""Shared fixtures: a controllable clock, an isolated home/notes folder, and state."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from wyndle.lib import time_utils
from wyndle.lib.config import WyndleConfig
from wyndle.lib.state import State


class Clock:
    """Mutable stand-in for ``time_utils.now``."""

    def __init__(self, start: datetime) -> None:
        self.current = start

    def __call__(self) -> datetime:
        return self.current

    def set(self, value: str) -> None:
        self.current = datetime.fromisoformat(value)

    def advance(self, **kwargs: float) -> None:
        self.current += timedelta(**kwargs)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    c = Clock(datetime(2026, 4, 7, 10, 0))  # a Tuesday
    monkeypatch.setattr(time_utils, "now", c)
    return c


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def cfg(home: Path) -> WyndleConfig:
    c = WyndleConfig(notes_dir=str(home / "notes"), daily_chores=["Reply to Slack"])
    c.ensure_dirs()
    return c


@pytest.fixture
def state(cfg: WyndleConfig) -> State:
    return State(cfg.state_dir)


@pytest.fixture
def answers(monkeypatch: pytest.MonkeyPatch):
    """Feed scripted replies to ``display.prompt`` / ``display.confirm``."""
    from wyndle.lib import display

    queue: list[str] = []
    monkeypatch.setattr(display, "prompt", lambda q: queue.pop(0))
    monkeypatch.setattr(
        display, "confirm", lambda q: queue.pop(0).lower() in ("y", "yes"),
    )
    return queue
