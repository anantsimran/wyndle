"""Notification events derived from a dashboard snapshot, without changing timers."""

from __future__ import annotations


def events(data: dict) -> list[dict]:
    """Return the current/next timer boundary and today's planned boundaries."""
    if not data.get("started") or data.get("wrapped"):
        return []
    result = []
    timer = data["timer"]
    kind = timer["kind"]
    if kind:
        end = timer["end"]
        index = max(0, int((data["now"] - end) // 300)) if kind == "focus" else 0
        for boundary in range(index, index + (2 if kind == "focus" else 1)):
            at = end + boundary * 300
            minutes = round(timer["duration"] / 60) if boundary == 0 else 5
            result.append({
                "id": f"{data['date']}:{kind}:{end}:{boundary}", "channel": "timer", "at": at,
                "title": "Break finished" if kind == "break" else f"{minutes}m block finished",
                "body": "Ready for the next step?" if kind == "break" else
                        f"{timer['title'] or 'Focus'} · 5m overflow started",
                "url": "/",
            })
    alarm = data.get("dailyAlarm")
    if alarm and alarm["blocks"]:
        for block in alarm["blocks"]:
            if block["kind"] == "work" and (block["done"] or block["missing"]):
                continue
            body = {"buffer": "Buffer time. Wrap up this block; pause focus.",
                    "break": "Break time."}.get(block["kind"], f"Time for {block['title']}.")
            result.append({"id": f"{alarm['id']}:{block['start']}", "channel": "daily",
                           "at": block["start"], "title": "Daily alarm", "body": body,
                           "url": "/daily"})
        at = alarm["blocks"][-1]["end"]
        result.append({"id": f"{alarm['id']}:{at}", "channel": "daily", "at": at,
                       "title": "Daily alarm", "body": "Today's planned blocks are complete.",
                       "url": "/daily"})
    return result


def due(events: list[dict], now: float, since: float) -> list[dict]:
    """Use only the latest crossed event per channel, avoiding a burst after sleep."""
    latest = {}
    for event in sorted(events, key=lambda item: item["at"]):
        if since < event["at"] <= now:
            latest[event["channel"]] = event
    return list(latest.values())
