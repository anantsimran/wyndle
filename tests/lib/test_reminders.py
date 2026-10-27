from wyndle.lib import dashboard, notifier, reminders


def focused(cfg, state):
    dashboard.dispatch(cfg, state, "morning", {"carryover": []})
    data = dashboard.dispatch(cfg, state, "add", {"title": "One step", "estimate": 15})
    return dashboard.dispatch(cfg, state, "focus", {"id": data["tasks"][-1]["id"], "minutes": 5})


def test_focus_overtime_and_break_boundaries(cfg, state, clock):
    data = focused(cfg, state)
    deadline = data["timer"]["end"]
    assert reminders.due(data["reminders"], deadline - 1, data["now"]) == []
    event = reminders.due(data["reminders"], deadline, data["now"])[0]
    assert event["title"] == "5m block finished"
    clock.advance(minutes=16)
    data = dashboard.snapshot(cfg, state)
    latest = reminders.due(data["reminders"], data["now"], deadline)[0]
    assert latest["at"] == deadline + 600
    assert latest["id"] != event["id"]
    dashboard.dispatch(cfg, state, "break", {"minutes": 5})
    clock.advance(minutes=5)
    data = dashboard.snapshot(cfg, state)
    assert (
        reminders.due(data["reminders"], data["now"], data["now"] - 1)[0]["title"]
        == "Break finished"
    )


def test_daemon_retries_failed_boundary_and_deduplicates(cfg, state, clock, monkeypatch):
    focused(cfg, state)
    clock.advance(minutes=5)
    calls = []

    def deliver(title, body):
        calls.append(title)
        return len(calls) > 1

    monkeypatch.setattr(notifier, "notify", deliver)
    for _ in range(3):
        notifier._check_dashboard_reminders(cfg, state)
    assert calls == ["5m block finished"] * 2
    dashboard.dispatch(cfg, state, "pause", {})
    clock.advance(minutes=5)
    notifier._check_dashboard_reminders(cfg, state)
    assert len(calls) == 2


def test_daily_plan_is_delivered_without_changing_tracking(cfg, state, clock):
    data = focused(cfg, state)
    data = dashboard.dispatch(
        cfg,
        state,
        "alarm_plan",
        {
            "start": "10:01",
            "workMinutes": 5,
            "bufferMinutes": 2,
            "breakMinutes": 3,
            "taskIds": [data["tasks"][-1]["id"]],
        },
    )
    start = data["now"]
    clock.advance(minutes=6)
    data = dashboard.snapshot(cfg, state)
    due = reminders.due(data["reminders"], data["now"], start)
    assert len(due) == 2
    assert [event["body"] for event in due if event["channel"] == "daily"] == [
        "Buffer time. Wrap up this block; pause focus."
    ]
    assert data["timer"]["kind"] == "focus"
    dashboard.dispatch(cfg, state, "wrap", {"tomorrow": "Rest"})
    assert dashboard.snapshot(cfg, state)["reminders"] == []
