"""Optional real-browser flow: python tests/browser/smoke.py (requires playwright).

Uses an isolated temporary notes folder and the locally installed Chrome browser.
Screenshots are written to /tmp/wyndle-desktop.png and /tmp/wyndle-sidebar.png.
"""

import tempfile
import threading
from datetime import datetime, timedelta
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

        cfg = TestConfig(notes_dir=str(root / "notes"), daily_chores=[])
        cfg.ensure_dirs()
        yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()
        daily_markdown = (
            "# Yesterday's work\n\n"
            "## High Level Tasks\n- [x] Project\n\n"
            "## Task Details\n### Project\n- [x] Finished ~15m\n- [ ] Next ~20m\n\n"
            "## Shutdown Notes\n> Total focused: 12m\n"
        )
        (cfg.daily_dir / f"{yesterday}.md").write_text(daily_markdown)
        task_markdown = "# Project notes\n\n<img src=x onerror=alert(1)> stays text\n"
        (cfg.tasks_dir / "project.md").write_text(task_markdown)
        (cfg.weekly_dir / "review.md").write_text("# Weekly review\n\nA small win.\n")
        state = State(cfg.state_dir)
        server = make_server(cfg, state, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        errors = []
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="chrome", headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 1150})
                page.context.grant_permissions(["notifications"])
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{server.server_port}")
                expect(page.locator(".hero-art img")).to_be_visible()
                assert page.locator(".hero-art img").evaluate(
                    "img => img.complete && img.naturalWidth > 0"
                )
                assert page.evaluate("""async () => {
                    const icon = document.querySelector('link[rel="icon"][href="/favicon.png"]');
                    if (!icon) return false;
                    const image = new Image();
                    image.src = icon.href;
                    try { await image.decode(); return image.naturalWidth > 0; }
                    catch { return false; }
                }""")

                page.get_by_role("button", name="Notes", exact=True).click()
                expect(page.locator("#note-markdown")).to_be_visible()
                assert page.locator("#note-markdown").text_content() == daily_markdown
                page.locator("#notes-select").select_option(label="Project notes · project.md")
                expect(page.locator("#note-markdown")).to_have_text(task_markdown)
                assert page.locator("#note-markdown img").count() == 0
                page.locator("#notes-refresh").click()
                expect(page.locator("#notes-select option:checked")).to_have_attribute(
                    "data-kind", "tasks"
                )
                expect(page.locator("#note-markdown")).to_have_text(task_markdown)
                page.locator("#notes-select").select_option(label="Weekly review · review.md")
                expect(page.locator("#note-title")).to_have_text("Weekly review")
                page.locator("#notes-close").click()

                page.get_by_role("button", name="Stats", exact=True).click()
                expect(page.locator("#history-days")).to_have_text("1 / 7")
                expect(page.locator("#history-focus")).to_have_text("12m")
                expect(page.locator("#history-tasks")).to_have_text("1 / 2")
                page.locator("#stats-month").click()
                expect(page.locator("#history-days")).to_have_text("1 / 30")
                expect(page.locator("#stats-month")).to_have_attribute("aria-pressed", "true")
                page.locator("#stats-close").click()

                page.get_by_role("button", name="Start my day").click()
                expect(page.locator("#workspace")).to_be_visible()
                titles = ["Sketch the first screen", "Write one small test", "Read the tricky bit"]
                for title, tier in zip(titles, ("p0", "regular", "optional")):
                    page.locator(f'input[name="task-tier"][value="{tier}"]').check()
                    page.locator("#task-title").fill(title)
                    page.locator("#task-title").press("Enter")
                    expect(page.get_by_role("button", name=f"Complete {title}")).to_be_visible()
                expect(page.locator("#remaining-p0")).to_have_text("1")
                expect(page.locator("#remaining-regular")).to_have_text("1")
                expect(page.locator("#remaining-optional")).to_have_text("1")
                page.get_by_role("button", name="Move Read the tricky bit up in Today").click()
                second_title = page.locator("#tasks .task-row").nth(1).locator(".task-title")
                expect(second_title).to_contain_text(
                    "Read the tricky bit"
                )
                expect(page.get_by_role(
                    "button", name="Move Read the tricky bit up in Today"
                )).to_be_focused()
                assert page.locator("#tasks .task-row").evaluate_all(
                    "rows => rows.map(row => "
                    "row.querySelector('.task-title').firstChild.textContent)"
                ) == ["Sketch the first screen", "Read the tricky bit", "Write one small test"]
                page.get_by_role("button", name="Mark P0 Read the tricky bit").click()
                expect(page.locator("#remaining-p0")).to_have_text("2")
                expect(page.locator("#remaining-optional")).to_have_text("0")
                page.get_by_role("button", name="Mark optional Read the tricky bit").click()
                expect(page.locator("#remaining-p0")).to_have_text("1")
                expect(page.locator("#remaining-optional")).to_have_text("1")
                page.get_by_role("link", name="Daily alarm").click()
                expect(page.get_by_role("heading", name="Build your day")).to_be_visible()
                page.locator("#plan-start").fill("10:00")
                page.get_by_role("button", name="Save daily plan").click()
                expect(page.locator("#timeline .block")).to_have_count(9)
                page.get_by_role("button", name="Enable page alerts").click()
                expect(page.locator("#enable-alerts")).to_have_text("Disable page alerts")
                page.get_by_role("link", name="Dashboard").click()
                page.get_by_role("button", name="Edit Read the tricky bit").click()
                page.locator("#edit-estimate").fill("7")
                page.locator("#edit-elapsed").fill("9")
                page.get_by_role("button", name="Save changes").click()
                expect(page.locator("#tasks .task-row.overdue")).to_have_count(1)
                page.get_by_role("button", name="Complete Read the tricky bit").click()
                expect(page.locator("#remaining-optional")).to_have_text("0")
                page.locator("#completed-label").click()
                expect(page.locator("#completed-tasks .task-meta")).to_contain_text("Total 9m")
                page.get_by_role("button", name="Mark Read the tricky bit not done").click()
                expect(page.locator("#remaining-optional")).to_have_text("1")
                page.get_by_role("button", name="Focus on Sketch the first screen").click()
                expect(page.locator("#live-dot")).to_be_visible()
                page.reload()
                expect(page.locator("#live-dot")).to_be_visible()
                expect(page.locator("#stat-focus")).to_have_text("9m")
                page.screenshot(path="/tmp/wyndle-desktop.png", full_page=True)
                page.set_viewport_size({"width": 340, "height": 1000})
                page.emulate_media(color_scheme="dark")
                page.wait_for_timeout(250)  # Let the theme transition settle for the screenshot.
                expect(page.locator("#stat-focus")).to_have_text("9m")
                page.screenshot(path="/tmp/wyndle-sidebar.png", full_page=True)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                for width in (320, 375, 768, 1024):
                    page.set_viewport_size({"width": width, "height": 1000})
                    expect(page.locator("#task-tiers")).to_be_visible()
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= innerWidth"
                    ), width
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
                page.get_by_role("button", name="Stats", exact=True).click()
                expect(page.locator("#history-days")).to_have_text("2 / 7")
                expect(page.locator("#history-tasks")).to_have_text("2 / 5")
                page.locator("#stats-close").click()
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
