import pytest

from wyndle.lib import notifier


@pytest.fixture
def sent(monkeypatch):
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(notifier, "notify", lambda t, m, sound="Funk": calls.append((t, m)))
    return calls


def test_safe_format_leaves_unknown_placeholders():
    assert notifier._safe_format("{a} and {b}", a=1) == "1 and {b}"


def test_cooldown(state, clock):
    assert notifier._should_notify(state, "k", cooldown_min=5)
    clock.advance(minutes=4)
    assert not notifier._should_notify(state, "k", cooldown_min=5)
    clock.advance(minutes=1)
    assert notifier._should_notify(state, "k", cooldown_min=5)


def test_milestones_fire_once_per_day_every_day(state, clock, sent):
    for _day in range(3):
        state.set("today_focused_min", "65")
        notifier._check_milestones(state)
        clock.advance(minutes=1)
        notifier._check_milestones(state)
        state.clear_day()
        clock.advance(days=1)
    assert [t for t, _ in sent] == ["First Hour Done"] * 3


def test_scheduled_notification_fires_every_day(cfg, state, clock, sent):
    cfg.scheduled_notifications = [{"time": "10:00", "message": "hi"}]
    clock.set("2026-04-07T09:59:30")
    for _ in range(7 * 24 * 60):  # a week of launchd ticks, one per minute
        notifier._check_scheduled_notifications(cfg, state)
        clock.advance(minutes=1)
    assert len(sent) == 7


def test_hard_stop_escalation(cfg, state, clock, sent):
    cfg.hard_stop = "20:00"
    clock.set("2026-04-07T19:50:00")
    assert notifier._check_hard_stop(cfg, state) is False
    clock.set("2026-04-07T20:05:00")
    assert notifier._check_hard_stop(cfg, state) is True
    clock.set("2026-04-07T20:15:00")
    assert notifier._check_hard_stop(cfg, state) is True
    assert [t for t, _ in sent] == ["10m to Hard Stop", "Shutdown Time", "STOP WORKING"]


def test_extension_postpones_hard_stop(cfg, state, clock, sent):
    cfg.hard_stop = "20:00"
    state.set("today_extensions", "1")
    clock.set("2026-04-07T20:10:00")
    assert notifier._check_hard_stop(cfg, state) is False
    assert sent == []


def test_idle_is_silent_during_block(state, clock, sent):
    state.set("today_start_time", "08:00")
    state.set_block_active(True)
    notifier._check_idle_nothing_active(None, state)
    assert sent == []
    state.set_block_active(False)
    notifier._check_idle_nothing_active(None, state)
    assert [t for t, _ in sent] == ["Frozen?"]
