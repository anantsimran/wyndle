import json
import threading
from http.client import HTTPConnection
from urllib.parse import urlencode

import pytest

from wyndle.commands.ui import ASSETS, make_server


@pytest.fixture
def server(cfg, state, clock):
    instance = make_server(cfg, state, 0)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    yield instance
    instance.shutdown()
    instance.server_close()
    thread.join()


def send(server, method, path, body=None, headers=None):
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    connection.request(method, path, body, headers or {})
    response = connection.getresponse()
    result = (response.status, response.read(), dict(response.headers))
    connection.close()
    return result


def test_serves_all_packaged_assets_and_status(server):
    for path in ASSETS:
        code, body, headers = send(server, "GET", path)
        assert code == 200 and body
        assert "Content-Security-Policy" in headers
    code, body, _ = send(server, "GET", "/api/status")
    assert code == 200 and json.loads(body)["app"] == "wyndle"
    assert send(server, "GET", "/../../config.yaml")[0] == 404


def test_browser_icons_are_linked_and_served(server):
    code, page, _ = send(server, "GET", "/")
    assert code == 200
    assert b'/favicon.png' in page
    for path, mime, signature in (
        ("/favicon.png", "image/png", b"\x89PNG\r\n\x1a\n"),
        ("/favicon.ico", "image/x-icon", b"\x00\x00\x01\x00"),
    ):
        code, body, headers = send(server, "GET", path)
        assert code == 200
        assert headers["Content-Type"].startswith(mime)
        assert body.startswith(signature)


def test_actions_require_local_origin_and_json_header(server):
    body = json.dumps({"action": "morning"})
    headers = {"Content-Type": "application/json", "X-Wyndle-Client": "dashboard"}
    assert send(server, "POST", "/api/action", body)[0] == 403
    assert send(server, "POST", "/api/action", body,
                {**headers, "Origin": "https://example.com"})[0] == 403
    assert send(server, "GET", "/api/status", headers={"Host": "evil.example"})[0] == 403
    assert send(server, "POST", "/api/action", body, headers)[0] == 200
    assert send(server, "POST", "/api/action", "[]", headers)[0] == 400
    assert send(server, "POST", "/api/action", "not-json", headers)[0] == 400


def test_allowed_hosts_accept_only_listed_https_host(cfg, state, clock, monkeypatch):
    monkeypatch.setenv("WYNDLE_ALLOWED_HOSTS", " mac.tail1234.ts.net, ")
    instance = make_server(cfg, state, 0)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        remote = {"Host": "mac.tail1234.ts.net"}
        body = json.dumps({"action": "morning"})
        action = {**remote, "Content-Type": "application/json", "X-Wyndle-Client": "dashboard"}
        assert send(instance, "GET", "/api/status", headers=remote)[0] == 200
        assert send(instance, "POST", "/api/action", body,
                    {**action, "Origin": "https://mac.tail1234.ts.net"})[0] == 200
        assert send(instance, "POST", "/api/action", body,
                    {**action, "Origin": "http://mac.tail1234.ts.net"})[0] == 403
        assert send(instance, "GET", "/api/status", headers={"Host": "other.ts.net"})[0] == 403
        assert send(instance, "GET", "/api/status")[0] == 200
    finally:
        instance.shutdown()
        instance.server_close()
        thread.join()


def test_notes_index_and_raw_task_note_access(server, cfg):
    daily = cfg.daily_dir / "2026-04-06.md"
    task = cfg.tasks_dir / "project-alpha.md"
    weekly = cfg.weekly_dir / "2026-04-07-reflect.md"
    daily.write_text("# Monday's work\n\n- [x] One step\n")
    task_markdown = "# Project Alpha\n\n## Notes\n- A detail to keep\n"
    task.write_text(task_markdown)
    weekly.write_text("# Weekly Review\n\nA small win.\n")
    (cfg.tasks_dir / "ignored.txt").write_text("not a Markdown note")

    code, body, _ = send(server, "GET", "/api/notes")
    assert code == 200
    notes = json.loads(body)
    assert set(notes) == {"daily", "tasks", "weekly"}
    assert {entry["name"] for entry in notes["daily"]} == {daily.name}
    assert {entry["name"] for entry in notes["tasks"]} == {task.name}
    assert {entry["name"] for entry in notes["weekly"]} == {weekly.name}
    task_entry = next(entry for entry in notes["tasks"] if entry["name"] == task.name)
    assert task_entry["title"] == "Project Alpha"

    path = "/api/note?" + urlencode({"kind": "tasks", "name": task.name})
    code, body, _ = send(server, "GET", path)
    assert code == 200
    assert json.loads(body) == {
        "kind": "tasks", "name": task.name, "title": "Project Alpha",
        "markdown": task_markdown,
    }


def test_note_and_stats_routes_reject_invalid_queries(server, cfg):
    outside = cfg.notes_path / "outside.md"
    outside.write_text("private marker")
    for query, expected in [
        ({"kind": "unknown", "name": "outside.md"}, 400),
        ({"kind": "tasks", "name": "../outside.md"}, 400),
        ({"kind": "tasks", "name": "missing.md"}, 404),
    ]:
        code, body, _ = send(server, "GET", "/api/note?" + urlencode(query))
        assert code == expected
        assert b"private marker" not in body

    for days in (7, 30):
        code, body, _ = send(server, "GET", f"/api/stats?days={days}")
        assert code == 200
        assert json.loads(body)["days"] == days
    assert send(server, "GET", "/api/stats?days=14")[0] == 400
    assert send(server, "GET", "/api/notes", headers={"Host": "evil.example"})[0] == 403

    link = cfg.tasks_dir / "linked.md"
    try:
        link.symlink_to(outside)
    except OSError:
        return  # Symlink creation needs elevated privileges on some platforms.
    assert send(server, "GET", "/api/note?kind=tasks&name=linked.md")[0] == 400
    code, body, _ = send(server, "GET", "/api/notes")
    assert code == 200
    assert not any(entry["name"] == link.name for entry in json.loads(body)["tasks"])


def test_notes_and_stats_api_read_markdown_and_live_progress(server, cfg, clock):
    cfg.daily_chores.clear()
    yesterday = cfg.daily_dir / "2026-04-06.md"
    yesterday.write_text(
        "# Monday's work\n\n"
        "## High Level Tasks\n- [x] Project\n\n"
        "## Task Details\n### Project\n- [x] Finished ~15m\n- [ ] Next ~20m\n\n"
        "## Shutdown Notes\n> Total focused: 35m\n"
    )
    task = cfg.tasks_dir / "project.md"
    task_markdown = "# Project notes\n\n<script>kept as text</script>\n"
    task.write_text(task_markdown)
    review = cfg.weekly_dir / "2026-04-06-review.md"
    review.write_text("# Weekly review\n\nA small win.\n")

    code, body, _ = send(server, "GET", "/api/notes")
    assert code == 200
    listed = json.loads(body)
    assert {entry["name"] for entry in listed["daily"]} == {yesterday.name}
    assert {entry["name"] for entry in listed["tasks"]} == {task.name}
    assert {entry["name"] for entry in listed["weekly"]} == {review.name}
    path = "/api/note?" + urlencode({"kind": "tasks", "name": task.name})
    code, body, _ = send(server, "GET", path)
    assert code == 200
    assert json.loads(body)["markdown"] == task_markdown

    headers = {"Content-Type": "application/json", "X-Wyndle-Client": "dashboard"}

    def action(name, data=None):
        code, body, _ = send(server, "POST", "/api/action",
                             json.dumps({"action": name, "data": data or {}}), headers)
        assert code == 200, body
        return json.loads(body)

    action("morning", {"carryover": False})
    task_id = action("add", {"title": "Live step"})["tasks"][0]["id"]
    action("focus", {"id": task_id})
    clock.advance(minutes=8)

    code, body, _ = send(server, "GET", "/api/stats")
    assert code == 200
    week = json.loads(body)
    assert (week["days"], week["trackedDays"]) == (7, 2)
    assert (week["focusedMinutes"], week["completedTasks"], week["totalTasks"]) == (43, 1, 3)
    today, previous = week["daily"][:2]
    assert (today["date"], today["focusedMinutes"], today["totalTasks"]) == (
        "2026-04-07", 8, 1,
    )
    assert (previous["date"], previous["focusedMinutes"], previous["completedTasks"]) == (
        "2026-04-06", 35, 1,
    )

    code, body, _ = send(server, "GET", "/api/stats?days=30")
    assert code == 200
    month = json.loads(body)
    assert (month["days"], month["trackedDays"], month["focusedMinutes"]) == (30, 2, 43)


@pytest.mark.parametrize("path", [
    "/api/notes?unexpected=1",
    "/api/note?kind=tasks",
    "/api/note?kind=tasks&name=one.md&name=two.md",
    "/api/note?kind=tasks&name=bad%5Cname.md",
    "/api/stats?days=",
    "/api/stats?days=7&days=30",
    "/api/stats?unexpected=7",
])
def test_history_api_rejects_malformed_queries(server, path):
    code, _, _ = send(server, "GET", path)
    assert code == 400
