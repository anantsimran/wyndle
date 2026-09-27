"""wyndle daemon — Install / manage the background notification service.

Uses macOS ``launchd`` to run :func:`wyndle.lib.notifier.check_and_notify`
every 60 seconds.  This fires native notification banners even when the
terminal is buried.

Sub-commands::

    wyndle daemon install    # write plist + load
    wyndle daemon uninstall  # unload + delete plist
    wyndle daemon start      # load existing plist
    wyndle daemon stop       # unload (keeps plist)
    wyndle daemon status     # is it running?
    wyndle daemon test       # fire a test banner
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from textwrap import dedent

from wyndle.lib import display
from wyndle.lib.config import WyndleConfig

PLIST_NAME = "com.wyndle.notifier"
PLIST_FILENAME = f"{PLIST_NAME}.plist"


def _plist_path() -> Path:
    """Return the path to the launchd plist file."""
    return Path.home() / "Library" / "LaunchAgents" / PLIST_FILENAME


def _find_wyndle_python() -> str:
    """Locate the Python interpreter that has wyndle installed.

    Search order:

    1. pipx venv at ``~/.local/pipx/venvs/wyndle/bin/python``.
    2. A ``.venv/bin/python`` or ``bin/python`` ancestor of the
       ``wyndle`` package directory.
    3. ``sys.executable`` as a fallback.

    Returns:
        Absolute path string to the Python binary.
    """
    # pipx
    pipx_python = Path.home() / ".local" / "pipx" / "venvs" / "wyndle" / "bin" / "python"
    if pipx_python.exists():
        return str(pipx_python)

    # walk up from the installed package
    import wyndle as _pkg
    pkg_dir = Path(_pkg.__file__).parent
    for parent in pkg_dir.parents:
        for candidate in (parent / ".venv" / "bin" / "python", parent / "bin" / "python"):
            if candidate.exists() and "wyndle" in str(parent).lower():
                return str(candidate)

    return sys.executable


def _generate_plist(python_path: str) -> str:
    """Generate the launchd plist XML for the notifier daemon.

    Args:
        python_path: Absolute path to the Python interpreter.

    Returns:
        Complete plist XML string.
    """
    return dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
          "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>Label</key>
            <string>{PLIST_NAME}</string>

            <key>ProgramArguments</key>
            <array>
                <string>{python_path}</string>
                <string>-m</string>
                <string>wyndle.lib.notifier</string>
            </array>

            <key>StartInterval</key>
            <integer>60</integer>

            <key>RunAtLoad</key>
            <true/>

            <key>StandardOutPath</key>
            <string>/tmp/wyndle-notifier.log</string>

            <key>StandardErrorPath</key>
            <string>/tmp/wyndle-notifier.err</string>

            <key>EnvironmentVariables</key>
            <dict>
                <key>PATH</key>
                <string>/usr/local/bin:/usr/bin:/bin</string>
            </dict>
        </dict>
        </plist>
    """)


# ---------------------------------------------------------------------------
# Public sub-command handlers
# ---------------------------------------------------------------------------

def install(cfg: WyndleConfig) -> None:
    """Install and load the launchd notification service.

    Writes the plist to ``~/Library/LaunchAgents/``, verifies that
    wyndle is importable from the detected Python, and loads the
    service.

    Args:
        cfg: Current configuration (used for display only).
    """
    display.header("Installing Background Notifications")

    plist = _plist_path()
    plist.parent.mkdir(parents=True, exist_ok=True)

    python_path = _find_wyndle_python()
    display.dim(f"Python: {python_path}")

    # Verify wyndle is importable
    result = subprocess.run(
        [python_path, "-c", "from wyndle.lib.notifier import check_and_notify; print('ok')"],
        capture_output=True, text=True,
    )
    if result.stdout.strip() != "ok":
        display.error(f"Can't import wyndle from {python_path}")
        display.dim("Make sure wyndle is installed: uv tool install . (from the repo)")
        display.dim(f"stderr: {result.stderr.strip()}")
        return

    # Unload if already present
    if plist.exists():
        subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)

    plist.write_text(_generate_plist(python_path))
    display.success(f"Plist written to {plist}")

    result = subprocess.run(["launchctl", "load", str(plist)], capture_output=True, text=True)
    if result.returncode == 0:
        display.success("Background notifier is running!")
    else:
        display.error(f"Failed to load: {result.stderr.strip()}")
        return

    display.console.print()
    display.dim("What you'll get:")
    display.dim("  - 'Day not started' nudge during work hours")
    display.dim("  - 'Nothing active' nudge if no block or break is running")
    display.dim("  - Auto-extend notifications when a block ends")
    display.dim("  - Hard stop warnings and escalation")
    display.dim("  - Milestone celebrations (60/120/180m)")
    display.console.print()
    display.dim("Logs: /tmp/wyndle-notifier.log")
    display.dim("Stop: wyndle daemon stop")
    display.dim("Remove: wyndle daemon uninstall")


def uninstall() -> None:
    """Unload and delete the launchd plist."""
    display.header("Removing Background Notifications")
    plist = _plist_path()
    if not plist.exists():
        display.dim("Not installed. Nothing to do.")
        return
    subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
    plist.unlink()
    display.success("Background notifier removed.")


def start() -> None:
    """Load (start) an already-installed plist."""
    plist = _plist_path()
    if not plist.exists():
        display.error("Not installed yet. Run: wyndle daemon install")
        return
    subprocess.run(["launchctl", "load", str(plist)], capture_output=True)
    display.success("Background notifier started.")


def stop() -> None:
    """Unload (stop) the daemon without deleting the plist."""
    plist = _plist_path()
    if not plist.exists():
        display.dim("Not installed.")
        return
    subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
    display.success("Background notifier stopped. Run 'wyndle daemon start' to resume.")


def status() -> None:
    """Check whether the daemon is currently running and show recent errors."""
    result = subprocess.run(
        ["launchctl", "list", PLIST_NAME], capture_output=True, text=True,
    )
    plist = _plist_path()

    if result.returncode == 0:
        display.success("Background notifier is running.")
        for line in result.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 3 and parts[0] != "-":
                display.dim(f"PID: {parts[0]}")
    else:
        if plist.exists():
            display.warn("Plist exists but service is not loaded. Run: wyndle daemon start")
        else:
            display.dim("Not installed. Run: wyndle daemon install")

    err_path = Path("/tmp/wyndle-notifier.err")
    if err_path.exists():
        errors = err_path.read_text().strip().splitlines()
        if errors:
            display.console.print()
            display.warn("Recent errors:")
            for line in errors[-5:]:
                display.dim(f"  {line}")


def test_notify() -> None:
    """Fire a single test notification to verify the setup works."""
    from wyndle.lib.notifier import notify
    notify("Wyndle Test", "If you see this, background notifications are working!", sound="Morse")
    display.success("Test notification sent. Check your notification center.")
