"""Optional real-browser flow: python tests/browser/smoke.py (requires playwright).

Uses an isolated temporary notes folder and the locally installed Chrome browser.
Screenshots are written to /tmp/wyndle-desktop.png and /tmp/wyndle-sidebar.png.
"""

import tempfile
import threading
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from wyndle.commands.ui import make_server
from wyndle.lib.config import WyndleConfig
from wyndle.lib.state import State


def main():
    with tempfile.TemporaryDirectory(prefix="wyndle-browser-") as directory:
        root = Path(directory)

        class TestConfig(WyndleConfig):
            @property
            def wyndle_dir(self):
                return root / "state-home"

        cfg = TestConfig(obsidian_vault=str(root / "notes"), daily_chores=[])
        state = State(cfg.state_dir)
        server = make_server(cfg, state, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        errors = []
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="chrome", headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 1150})
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{server.server_port}")
                expect(page.locator(".hero-art img")).to_be_visible()
                assert page.locator(".hero-art img").evaluate(
                    "img => img.complete && img.naturalWidth > 0"
                )
                page.get_by_role("button", name="Start my day").click()
                expect(page.locator("#workspace")).to_be_visible()
                titles = ["Sketch the first screen", "Write one small test", "Read the tricky bit"]
                for title in titles:
                    page.locator("#task-title").fill(title)
                    page.locator("#task-title").press("Enter")
                    expect(page.get_by_text(title, exact=True).first).to_be_visible()
                page.get_by_role("button", name="Focus on Sketch the first screen").click()
                expect(page.locator("#live-dot")).to_be_visible()
                page.reload()
                expect(page.locator("#live-dot")).to_be_visible()
                page.screenshot(path="/tmp/wyndle-desktop.png", full_page=True)
                page.set_viewport_size({"width": 340, "height": 1000})
                page.emulate_media(color_scheme="dark")
                page.wait_for_timeout(250)  # Let the theme transition settle for the screenshot.
                page.screenshot(path="/tmp/wyndle-sidebar.png", full_page=True)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.get_by_role("button", name="Pause focus").click()
                expect(page.locator("#live-dot")).to_be_hidden()
                page.get_by_role("button", name="Take a 5 min break").click()
                expect(page.locator("#focus-title")).to_have_text("Even a journey needs rest.")
                page.get_by_role("button", name="Pause", exact=True).click()
                page.get_by_role("button", name="Add note to Sketch the first screen").click()
                page.locator("#note-input").fill("<script> stays text")
                page.get_by_role("button", name="Save note").click()
                expect(page.locator("#note-dialog")).not_to_be_visible()
                page.get_by_text("1 note", exact=True).click()
                expect(page.get_by_text("<script> stays text", exact=True)).to_be_visible()
                page.get_by_role("button", name="Complete Sketch the first screen").click()
                expect(page.locator("#stat-done")).to_have_text("1 / 3")
                page.locator("#wrap-toggle").click()
                page.locator("#tomorrow").fill("Take the next step")
                page.get_by_role("button", name="Finish my day").click()
                expect(page.locator("#finished")).to_be_visible()
                assert state.get("today_wrapped") == "true"
                assert not errors, errors
                browser.close()
                print("Browser flow passed; desktop and sidebar screenshots saved to /tmp.")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    main()
