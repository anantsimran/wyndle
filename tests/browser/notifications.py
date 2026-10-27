"""Notification regression flows: uv run --with playwright python tests/browser/notifications.py.

Uses Chrome, isolated notes, real service-worker registration, and mocked OS
delivery so the tests do not display banners or require a physical phone.
"""

import json
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from wyndle.commands.ui import make_server
from wyndle.lib import dashboard, reminders
from wyndle.lib.config import WyndleConfig
from wyndle.lib.state import State

MOCK_DELIVERY = """
window.sentAlerts = [];
window.notificationPermission = 'granted';
window.failDelivery = false;
window.Notification = class {
  static get permission() { return window.notificationPermission; }
  static async requestPermission() { return window.notificationPermission; }
  constructor() { throw new TypeError('Mobile browsers require a service worker'); }
};
ServiceWorkerRegistration.prototype.showNotification = async function(title, options) {
  if (window.failDelivery) throw new Error('OS delivery failed');
  window.sentAlerts.push({title, ...options});
};
"""


def main():
    with tempfile.TemporaryDirectory(prefix="wyndle-alerts-") as directory:
        root = Path(directory)

        class TestConfig(WyndleConfig):
            @property
            def wyndle_dir(self):
                return root / "state-home"

        cfg = TestConfig(notes_dir=str(root / "notes"), daily_chores=[])
        cfg.ensure_dirs()
        state = State(cfg.state_dir)
        dashboard.dispatch(cfg, state, "morning", {"carryover": []})
        data = dashboard.dispatch(cfg, state, "add", {"title": "Test boundary", "estimate": 15})
        data = dashboard.dispatch(
            cfg,
            state,
            "focus",
            {
                "id": data["tasks"][0]["id"],
                "minutes": 5,
            },
        )
        start = data["now"]
        data["timer"]["end"] = start + 2
        data["dailyAlarm"] = {
            "id": "test-plan",
            "selectedTaskIds": [],
            "blocks": [
                {
                    "kind": "break",
                    "start": start + 4,
                    "end": start + 500,
                    "minutes": 5,
                    "taskId": "",
                    "title": "Break",
                    "done": False,
                    "missing": False,
                },
            ],
        }
        server = make_server(cfg, state, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}"
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="chrome", headless=True)
                context = browser.new_context()
                context.add_init_script(MOCK_DELIVERY)
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                clock_start = datetime.fromtimestamp(start, timezone.utc)
                page.clock.install(time=clock_start)
                page.clock.pause_at(clock_start)

                def serve_status(route):
                    data["now"] = page.evaluate("Date.now() / 1000")
                    data["reminders"] = reminders.events(data)
                    route.fulfill(
                        status=200, content_type="application/json", body=json.dumps(data)
                    )

                page.route("**/api/status", serve_status)
                page.goto(url)
                page.get_by_role("button", name="Enable timer alerts").click()
                page.get_by_role("button", name="Test alert", exact=True).click()
                expect(page.locator("#toast")).to_contain_text("Test alert submitted")
                assert page.evaluate("sentAlerts.length") == 1
                assert page.evaluate(
                    "navigator.serviceWorker.getRegistration().then(r => !!r.active)"
                )
                page.evaluate(
                    "sentAlerts.length = 0; localStorage.setItem('wyndle-daily-alerts', 'true')"
                )
                page.evaluate(
                    "dispatchEvent(new StorageEvent('storage', {key: 'wyndle-daily-alerts'}))"
                )
                page.clock.fast_forward(3000)
                expect(page.locator("#toast")).to_contain_text("block finished")
                page.clock.fast_forward(1500)
                expect(page.locator("#toast")).to_contain_text("Break time")
                assert page.evaluate("sentAlerts.length") == 2

                # A delayed tab must deliver the latest boundary, even >60 seconds late.
                page.clock.fast_forward(380000)
                expect(page.locator("#toast")).to_contain_text("block finished")
                assert page.evaluate("sentAlerts.filter(x => x.tag === 'wyndle-timer').length") == 2

                # Permission denial is actionable; in-page reminders still work.
                page.evaluate("notificationPermission = 'denied'")
                page.get_by_role("button", name="Test alert", exact=True).click()
                expect(page.locator("#focus-alert-status")).to_contain_text("browser settings")
                expect(page.locator("#toast")).to_contain_text("In-page reminders only")
                page.evaluate("notificationPermission = 'granted'; failDelivery = true")
                page.get_by_role("button", name="Test alert", exact=True).click()
                expect(page.locator("#focus-alert-status")).to_contain_text(
                    "could not show a banner"
                )

                # Navigate to Daily Alarm: timer preference persists and no old alerts replay.
                page.goto(url + "/daily")
                expect(page.locator("#enable-alerts")).to_have_text("Disable page alerts")
                page.get_by_role("button", name="Test alert", exact=True).click()
                expect(page.locator("#toast")).to_contain_text("Test alert submitted")
                assert page.evaluate("sentAlerts.length") == 1
                page.clock.fast_forward(1000)
                assert page.evaluate("sentAlerts.length") == 1
                assert not errors, errors

                # Exercise the actual iframe handshake and delivery; arbitrary hosts
                # must not receive task titles through the VS Code bridge.
                wrapper = """<iframe src="https://wyndle.test/"></iframe><script>
                    window.hostAlerts = [];
                    addEventListener('message', event => {
                      if (event.data?.type === 'wyndle.host.request')
                        event.source.postMessage({type: 'wyndle.host.ready'}, event.origin);
                      if (event.data?.type === 'wyndle.alert') hostAlerts.push(event.data.event);
                    });
                </script>"""
                for origin, expected in (
                    ("https://test.vscode-cdn.net", "VS Code notifications"),
                    ("https://untrusted.example", "Open Wyndle in your browser"),
                ):
                    embedded = context.new_page()
                    embedded.route(origin + "/", lambda route: route.fulfill(
                        content_type="text/html", body=wrapper))
                    embedded.route("https://wyndle.test/**", lambda route: route.fulfill(
                        response=context.request.get(
                            url + route.request.url.removeprefix("https://wyndle.test"))))
                    embedded.goto(origin + "/")
                    frame = embedded.frame_locator("iframe")
                    # Embedded storage may be partitioned from the top-level page.
                    button = frame.locator("#focus-alerts")
                    expect(button).to_be_visible()
                    if button.inner_text().startswith("Enable"):
                        button.click()
                    expect(frame.locator("#focus-alert-status")).to_contain_text(expected)
                    frame.get_by_role("button", name="Test alert", exact=True).click()
                    if "vscode" in origin:
                        expect(frame.locator("#toast")).to_contain_text("Test alert submitted")
                        assert embedded.evaluate("hostAlerts.length") == 1
                    else:
                        expect(frame.locator("#toast")).to_contain_text("In-page reminders only")
                        assert embedded.evaluate("hostAlerts.length") == 0
                    embedded.close()
                context.close()
                browser.close()
                print(
                    "Notification flows passed: mobile delivery, timer/daily boundaries, "
                    "delayed tabs, permissions, failures, navigation."
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    main()
