import json
import threading
from http.client import HTTPConnection

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
