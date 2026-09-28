"""Wyndle CLI — Click command router.

All commands follow a lazy-import pattern: the setup (config + state)
runs first, then the command module is imported and called.  This keeps
startup fast even when only ``wyndle help`` is invoked.
"""

from __future__ import annotations

import click

from wyndle.lib.config import WyndleConfig, init_default_config, load_config
from wyndle.lib.state import State


def _setup() -> tuple[WyndleConfig, State]:
    """Load config, ensure directories, auto-wrap yesterday, and return (config, state).

    Auto-wrap runs on every command so that switching to a new day
    always syncs the previous day's work to task note files, even if
    the user forgot to run ``wyndle wrap``.
    """
    init_default_config()
    cfg = load_config()
    cfg.ensure_dirs()
    state = State(cfg.state_dir)
    from wyndle.commands.wrap import auto_wrap_yesterday
    auto_wrap_yesterday(cfg, state)
    return cfg, state


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------

@click.group(invoke_without_command=True, epilog=(
    "How to use: wyndle help --guide. In the dashboard, choose How to use."
))
@click.pass_context
def main(ctx: click.Context) -> None:
    """Wyndle -- ADHD-Aware Productivity System for the Terminal."""
    if ctx.invoked_subcommand is None:
        _help_screen()


# ---------------------------------------------------------------------------
# Day-flow commands
# ---------------------------------------------------------------------------

@main.command()
@click.option("--port", type=click.IntRange(1, 65535), default=8765, show_default=True)
@click.option("--browser/--no-browser", default=True, help="Open the dashboard in your browser.")
def ui(port: int, browser: bool) -> None:
    """Open the local web dashboard."""
    from wyndle.commands.ui import run
    try:
        run(port, browser)
    except OSError as exc:
        raise click.ClickException(
            f"Could not start dashboard: {exc}. Try --port with another port."
        ) from exc


@main.command()
def morning() -> None:
    """Start your day: yesterday recap -> add tasks -> open your notes."""
    cfg, state = _setup()
    from wyndle.commands.morning import run
    run(cfg, state)


@main.command()
@click.argument("task", nargs=-1)
def start(task: tuple[str, ...]) -> None:
    """Begin a timed focus block (picks sub-task from your daily note)."""
    cfg, state = _setup()
    from wyndle.commands.start import run
    run(cfg, state, " ".join(task))


@main.command()
def switch() -> None:
    """Switch to a different sub-task (pauses current one)."""
    cfg, state = _setup()
    from wyndle.commands.start import switch_task
    switch_task(cfg, state)


@main.command(name="break")
def break_cmd() -> None:
    """Take a break -- lunch, walk, stretch. Tracked in your daily note."""
    cfg, state = _setup()
    from wyndle.commands.break_cmd import run
    run(cfg, state)


@main.command()
def stuck() -> None:
    """Can't start? Interactive diagnostic to decompose the block."""
    cfg, state = _setup()
    from wyndle.commands.stuck import run
    run(cfg, state)


@main.command(name="next")
def next_cmd() -> None:
    """Close current sub-task and start the next one."""
    cfg, state = _setup()
    from wyndle.commands.start import next_task
    next_task(cfg, state)


@main.command()
def status() -> None:
    """What's left? Shows est vs actual per sub-task."""
    cfg, state = _setup()
    from wyndle.commands.status import run
    run(cfg, state)


@main.command(name="open")
def open_cmd() -> None:
    """Open today's daily note for editing."""
    cfg, state = _setup()
    from wyndle.lib.daily_notes import create_daily_note, open_daily_note
    create_daily_note(cfg.daily_dir)
    open_daily_note(cfg.daily_dir)
    from wyndle.lib.display import success
    success("Opening today's daily note...")


@main.command()
def wrap() -> None:
    """Shutdown ritual -- time tracking summary + tomorrow's plan."""
    cfg, state = _setup()
    from wyndle.commands.wrap import run
    run(cfg, state)


@main.command()
@click.argument("minutes", default="")
def restart(minutes: str) -> None:
    """Restart the last focus block (optionally with 5, 15, or 30 min)."""
    cfg, state = _setup()
    from wyndle.commands.start import restart_task
    restart_task(cfg, state, minutes)


@main.command()
@click.argument("period", default="weekly")
def reflect(period: str) -> None:
    """Review -- weekly (default) or monthly. Shows subtask + day summary."""
    cfg, state = _setup()
    from wyndle.commands.reflect import run
    run(cfg, state, monthly=period.lower() == "monthly")


# ---------------------------------------------------------------------------
# Daemon sub-group
# ---------------------------------------------------------------------------

@main.group()
def daemon() -> None:
    """Background notifications (macOS launchd)."""


@daemon.command(name="install")
def daemon_install() -> None:
    """Install the background notification service."""
    cfg, _state = _setup()
    from wyndle.commands.daemon import install
    install(cfg)


@daemon.command(name="uninstall")
def daemon_uninstall() -> None:
    """Remove the background notification service."""
    from wyndle.commands.daemon import uninstall
    uninstall()


@daemon.command(name="start")
def daemon_start() -> None:
    """Start the notification service."""
    from wyndle.commands.daemon import start
    start()


@daemon.command(name="stop")
def daemon_stop() -> None:
    """Stop the notification service (keeps it installed)."""
    from wyndle.commands.daemon import stop
    stop()


@daemon.command(name="status")
def daemon_status() -> None:
    """Check if the notification service is running."""
    from wyndle.commands.daemon import status
    status()


@daemon.command(name="test")
def daemon_test() -> None:
    """Fire a test notification to verify it works."""
    from wyndle.commands.daemon import test_notify
    test_notify()


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

def _help_screen() -> None:
    """Render the full help screen with usage guide."""
    from wyndle.lib.display import accent, bold_print, console, dim, header

    header("Wyndle -- ADHD-Aware Productivity System")
    console.print()

    accent("  [bold]Dashboard[/bold]")
    bold_print("[bold]wyndle ui[/bold]         Open the web UI (also available in VS Code)")
    bold_print("[bold]wyndle help --guide[/bold]  Read the dashboard's How to use guide")
    dim("  Notes: browse saved daily, task, and review Markdown in the dashboard")
    dim("  Stats: review 7 or 30 days of focus time and completed steps")
    console.print()

    accent("  [bold]Day Flow[/bold]")
    bold_print("[bold]wyndle morning[/bold]    Start day (yesterday recap -> add tasks)")
    bold_print("[bold]wyndle start[/bold]      Pick a sub-task -> timed focus block")
    bold_print("[bold]wyndle restart[/bold]    Restart last block (wyndle restart 5/15/30)")
    bold_print("[bold]wyndle switch[/bold]     Switch sub-task (pauses current one)")
    bold_print("[bold]wyndle next[/bold]       Close current sub-task, start next one")
    bold_print("[bold]wyndle break[/bold]      Take a break -- lunch, walk (tracked)")
    bold_print("[bold]wyndle stuck[/bold]      Can't start? Decompose the block.")
    bold_print("[bold]wyndle wrap[/bold]       Shutdown ritual + time tracking summary")
    console.print()

    accent("  [bold]Info & Editing[/bold]")
    bold_print("[bold]wyndle status[/bold]     Remaining tasks with est vs actual time")
    bold_print("[bold]wyndle open[/bold]       Open today's daily note")
    bold_print("[bold]wyndle reflect[/bold]    Weekly review (subtask + day summary)")
    bold_print("[bold]wyndle reflect monthly[/bold]  Monthly review")
    console.print()

    accent("  [bold]System[/bold]")
    bold_print("[bold]wyndle daemon[/bold]     Background notifications (install/start/stop)")
    bold_print("[bold]wyndle help[/bold]       This help screen")
    console.print()

    dim("[bold]Quick Start[/bold]")
    dim("───────────")
    dim("1. [bold]wyndle morning[/bold] -- shows yesterday's wrap, add tasks")
    dim("")
    dim("2. [bold]wyndle open[/bold] -- edit your daily note:")
    dim("   Reorder high-level tasks (top = highest priority)")
    dim("   Add sub-tasks with time estimates:")
    dim("       ### Build auth flow")
    dim("       - [ ] Read OAuth docs ~30m")
    dim("       - [ ] Set up middleware ~45m")
    dim("")
    dim("3. [bold]wyndle start[/bold] -- pick task -> pick sub-task")
    dim("   Choose 5, 15, or 30 min block")
    dim("   macOS notification when timer ends")
    dim("   Time tracked per sub-task automatically")
    dim("   Block auto-extends if you keep working")
    dim("")
    dim("   [bold]wyndle restart 15[/bold] -- restart last block (5, 15, or 30 min)")
    dim("")
    dim("4. [bold]wyndle break[/bold] -- lunch, walk, coffee, stretch")
    dim("   Pauses active sub-task, starts break timer")
    dim("   Offers to resume previous sub-task after")
    dim("")
    dim("5. [bold]wyndle status[/bold] -- estimated vs actual time")
    dim("")
    dim("6. [bold]wyndle wrap[/bold] -- end of day")
    dim("   Prints planned vs actual summary")
    dim("   Sets tomorrow's first task")
    console.print()

    dim("Config: ~/.wyndle/config.yaml")
    dim("Notes:  ~/Documents/Wyndle  (edit in config)")


@main.command(name="help")
@click.option("--guide", is_flag=True, help="Read the same How to use guide as the dashboard.")
def help_cmd(guide: bool) -> None:
    """Show full help screen with usage guide."""
    if guide:
        from rich.markdown import Markdown

        from wyndle.lib.display import console
        from wyndle.lib.help import guide_markdown

        console.print(Markdown(guide_markdown()))
    else:
        _help_screen()


if __name__ == "__main__":
    main()
