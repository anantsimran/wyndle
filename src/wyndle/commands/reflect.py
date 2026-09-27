"""wyndle reflect -- Weekly and monthly review.

Scans daily notes for the given period, extracts per-subtask time data
and daily start/end times, then prompts for reflection.

Usage::

    wyndle reflect            # weekly (last 7 days)
    wyndle reflect monthly    # monthly (last 30 days)

v1.3.0: adds subtask completion summary (done vs undone with times)
and day-by-day start/end time listing.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from wyndle.lib import display, time_utils
from wyndle.lib.config import WyndleConfig
from wyndle.lib.markdown_dom import MarkdownDoc
from wyndle.lib.state import State

_EST_ACTUAL_RE = re.compile(r"~(\d+)m\s*->\s*(\d+)m")
# Legacy format: "est: Xm  actual: Ym" or "est: —  actual: Ym"
_LEGACY_EST_ACTUAL_RE = re.compile(r"est:\s*(?:~?(\d+)m|.)\s+actual:\s*(\d+)m")
_STARTED_RE = re.compile(r"Day started")
_SHUTDOWN_RE = re.compile(r"Shutdown at (\d{2}:\d{2} [AP]M)")
_DAY_STARTED_TIME_RE = re.compile(r"\*\*(\d{2}:\d{2} [AP]M)\*\* .+ Day started")


def run(cfg: WyndleConfig, state: State, monthly: bool = False) -> None:
    """Execute the review flow.

    Args:
        cfg:     Current configuration.
        state:   Current state store.
        monthly: If True, scan 30 days instead of 7.
    """
    days = 30 if monthly else 7
    period = "Monthly" if monthly else "Weekly"
    display.header(f"{period} Review")
    display.dim(f"Scanning the last {days} days...")
    display.console.print()

    day_data = _scan_daily_notes(cfg, days)
    _print_day_summary(day_data)
    done_subs, undone_subs, on_time, estimated = _scan_subtask_data(cfg, days)
    _print_subtask_summary(done_subs, undone_subs, on_time, estimated)

    worked, didnt_work, tweak = _prompt_reflection()

    if cfg.features.notes:
        _save_review(cfg, period, days, day_data, done_subs, undone_subs,
                     on_time, estimated, worked, didnt_work, tweak)

    display.success("Review complete. Carry that one tweak forward.")


# ---------------------------------------------------------------------------
# Day scanning
# ---------------------------------------------------------------------------


def _scan_daily_notes(
    cfg: WyndleConfig, days: int,
) -> list[dict]:
    """Scan daily notes and extract metadata for each day.

    Returns:
        List of dicts with keys: date, exists, start_time, end_time,
        focused_min, task_count, completed_count.
    """
    today = date.today()
    results: list[dict] = []
    for i in range(days):
        check_date = today - timedelta(days=i)
        date_str = check_date.isoformat()
        note_path = cfg.daily_dir / f"{date_str}.md"
        entry = {"date": date_str, "exists": note_path.exists()}
        if not note_path.exists():
            results.append(entry)
            continue
        doc = MarkdownDoc(note_path.read_text())
        entry["start_time"], entry["end_time"] = _extract_times(doc)
        entry["focused_min"] = _extract_focused(doc)
        done, total = _count_tasks(doc)
        entry["completed_count"] = done
        entry["task_count"] = total
        results.append(entry)
    return results


def _extract_times(doc: MarkdownDoc) -> tuple[str, str]:
    """Extract day start and shutdown times from the Log section."""
    log = doc.find_section("Log", level=2)
    start_time = ""
    end_time = ""
    if log is None:
        return start_time, end_time
    for line in log.content:
        if not start_time:
            m = _DAY_STARTED_TIME_RE.search(line)
            if m:
                start_time = m.group(1)
        m = _SHUTDOWN_RE.search(line)
        if m:
            end_time = m.group(1)
    return start_time, end_time


def _extract_focused(doc: MarkdownDoc) -> int:
    """Extract focused minutes from shutdown notes."""
    shutdown = doc.find_section("Shutdown Notes", level=2)
    if shutdown is None:
        return 0
    for line in shutdown.content:
        stripped = line.strip().lstrip("> ").strip()
        if stripped.startswith("Total focused:"):
            m = re.search(r"(\d+)m", stripped)
            if m:
                return int(m.group(1))
    return 0


def _count_tasks(doc: MarkdownDoc) -> tuple[int, int]:
    """Count completed and total high-level tasks."""
    section = doc.find_section("High Level Tasks", level=2)
    if section is None:
        return 0, 0
    cbs = doc.get_checkboxes(section)
    total = len(cbs)
    done = sum(1 for _, checked, _ in cbs if checked)
    return done, total


def _print_day_summary(day_data: list[dict]) -> None:
    """Print per-day start/end times and focused minutes."""
    display.accent("Day Summary:")
    display.console.print()
    tracked = 0
    total_focused = 0
    for d in day_data:
        marker = "\u2713" if d["exists"] else "\u2717"
        if not d["exists"]:
            display.dim(f"  {marker} {d['date']}")
            continue
        tracked += 1
        start = d.get("start_time", "")
        end = d.get("end_time", "")
        focused = d.get("focused_min", 0)
        total_focused += focused
        completed = d.get("completed_count", 0)
        total = d.get("task_count", 0)
        time_range = f"{start} - {end}" if start and end else start or "?"
        parts = [time_range]
        if focused:
            parts.append(f"{focused}m focused")
        if total:
            parts.append(f"{completed}/{total} tasks")
        display.dim(f"  {marker} {d['date']}  {' | '.join(parts)}")
    display.console.print()
    display.info(f"  Days tracked: [bold]{tracked}/{len(day_data)}[/bold]")
    if total_focused:
        display.info(f"  Total focused: [bold]{time_utils.hours_minutes(total_focused)}[/bold]")
    display.console.print()


# ---------------------------------------------------------------------------
# Subtask scanning
# ---------------------------------------------------------------------------


def _scan_subtask_data(
    cfg: WyndleConfig, days: int,
) -> tuple[list[tuple[str, int, int]], list[tuple[str, int]], int, int]:
    """Scan shutdown notes for subtask completion data.

    Handles both v1.3.0 format (``~30m -> 15m``) and legacy format
    (``est: 30m  actual: 15m`` or ``est: ---  actual: 0m``).

    Returns:
        Tuple of (done_list, undone_list, on_time_count, estimated_count).
        done_list: [(name, est_min, actual_min), ...]
        undone_list: [(name, est_min), ...]
    """
    today = date.today()
    done_subs: list[tuple[str, int, int]] = []
    undone_subs: list[tuple[str, int]] = []
    on_time = 0
    estimated = 0

    for i in range(days):
        check_date = today - timedelta(days=i)
        note_path = cfg.daily_dir / f"{check_date.isoformat()}.md"
        if not note_path.exists():
            continue
        doc = MarkdownDoc(note_path.read_text())
        shutdown = doc.find_section("Shutdown Notes", level=2)
        if shutdown is None:
            continue
        for line in shutdown.content:
            parsed = _parse_subtask_line(line)
            if parsed is None:
                continue
            is_done, name, est_min, actual_min = parsed
            if is_done:
                done_subs.append((name, est_min, actual_min))
                if est_min > 0:
                    estimated += 1
                    if actual_min <= est_min:
                        on_time += 1
            else:
                undone_subs.append((name, est_min))

    return done_subs, undone_subs, on_time, estimated


def _parse_subtask_line(line: str) -> tuple[bool, str, int, int] | None:
    """Parse a single subtask time-tracking line from shutdown notes.

    Returns:
        Tuple of ``(is_done, name, est_min, actual_min)`` or None.
    """
    stripped = line.strip().lstrip("> ").strip()
    if not stripped:
        return None
    is_done = stripped.startswith("\u2713")
    is_undone = stripped.startswith("\u2610")
    if not is_done and not is_undone:
        return None

    # Try v1.3.0 format: "~30m -> 15m"
    m = _EST_ACTUAL_RE.search(stripped)
    if m:
        name = stripped[:m.start()].strip()
        name = _strip_marker(name)
        from wyndle.lib.markdown_dom import strip_estimate
        name = strip_estimate(name)
        return is_done, name, int(m.group(1)), int(m.group(2))

    # Try legacy format: "est: 30m  actual: 15m" or "est: —  actual: 0m"
    m = _LEGACY_EST_ACTUAL_RE.search(stripped)
    if m:
        name = stripped[:m.start()].strip()
        name = _strip_marker(name)
        est = int(m.group(1)) if m.group(1) else 0
        actual = int(m.group(2))
        # Strip ~Xm from name; use as fallback estimate
        from wyndle.lib.markdown_dom import parse_estimate, strip_estimate
        inline_est = parse_estimate(name)
        name = strip_estimate(name)
        if est == 0 and inline_est > 0:
            est = inline_est
        return is_done, name, est, actual

    return None


def _strip_marker(text: str) -> str:
    """Remove done/undone marker prefix from a subtask name."""
    for prefix in ("\u2713 ", "\u2610 ", "  "):
        if text.startswith(prefix):
            return text[len(prefix):].strip()
    return text.strip()


def _print_subtask_summary(
    done_subs: list[tuple[str, int, int]],
    undone_subs: list[tuple[str, int]],
    on_time: int,
    estimated: int,
) -> None:
    """Print subtask completion summary."""
    if not done_subs and not undone_subs:
        display.dim("  No subtask data found in shutdown notes.")
        display.console.print()
        return

    if done_subs:
        display.accent(f"Completed subtasks: {len(done_subs)}")
        total_est = sum(e for _, e, _ in done_subs)
        total_actual = sum(a for _, _, a in done_subs)
        for name, est, actual in done_subs:
            delta = actual - est
            sign = "+" if delta >= 0 else ""
            display.dim(f"  \u2713 {name}  ~{est}m -> {actual}m ({sign}{delta}m)")
        display.console.print()
        display.info(
            f"  Total: [bold]{time_utils.hours_minutes(total_est)}[/bold] estimated, "
            f"[bold]{time_utils.hours_minutes(total_actual)}[/bold] actual"
        )
        if estimated > 0:
            pct = int(on_time / estimated * 100)
            display.info(
                f"  On-time: [bold]{on_time}/{estimated} ({pct}%)[/bold] within estimate"
            )
        display.console.print()

    if undone_subs:
        display.accent(f"Incomplete subtasks: {len(undone_subs)}")
        total_undone_est = sum(e for _, e in undone_subs)
        for name, est in undone_subs:
            display.dim(f"  \u2610 {name}  ~{est}m")
        display.console.print()
        display.info(
            f"  Unfinished estimate: [bold]{time_utils.hours_minutes(total_undone_est)}[/bold]"
        )
        display.console.print()


# ---------------------------------------------------------------------------
# Reflection prompts
# ---------------------------------------------------------------------------


def _prompt_reflection() -> tuple[str, str, str]:
    """Prompt for review reflection.  Returns (worked, didnt_work, tweak)."""
    worked = display.prompt("What worked well?")
    didnt_work = display.prompt("What didn't work?")
    tweak = display.prompt("ONE tweak for next period?")
    return worked, didnt_work, tweak


# ---------------------------------------------------------------------------
# Save review file
# ---------------------------------------------------------------------------


def _save_review(
    cfg: WyndleConfig, period: str, days: int,
    day_data: list[dict],
    done_subs: list[tuple[str, int, int]],
    undone_subs: list[tuple[str, int]],
    on_time: int, estimated: int,
    worked: str, didnt_work: str, tweak: str,
) -> None:
    """Write the review to a markdown file in the weekly/ directory."""
    weekly_dir = cfg.notes_path / "weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)
    suffix = "monthly" if days > 7 else "reflect"
    path = weekly_dir / f"{time_utils.now_date_str()}-{suffix}.md"

    tracked = sum(1 for d in day_data if d["exists"])
    total_focused = sum(d.get("focused_min", 0) for d in day_data if d["exists"])

    lines = [
        "---",
        f"date: {time_utils.now_date_str()}",
        f"type: {period.lower()}-review",
        "---",
        "",
        f"# {period} Review -- {time_utils.now_date_str()}",
        "",
        "## What Worked",
        worked,
        "",
        "## What Didn't Work",
        didnt_work,
        "",
        "## One Tweak",
        tweak,
        "",
        f"## Days Tracked: {tracked}/{len(day_data)}",
        f"Total focused: {time_utils.hours_minutes(total_focused)}",
        "",
        "## Day Summary",
    ]
    for d in day_data:
        if not d["exists"]:
            lines.append(f"- {d['date']}: no data")
            continue
        start = d.get("start_time", "?")
        end = d.get("end_time", "?")
        focused = d.get("focused_min", 0)
        completed = d.get("completed_count", 0)
        total = d.get("task_count", 0)
        lines.append(
            f"- {d['date']}: {start} - {end} | "
            f"{focused}m focused | {completed}/{total} tasks"
        )

    if done_subs or undone_subs:
        lines.extend(["", "## Subtask Summary"])
        if done_subs:
            lines.append("")
            lines.append(f"### Completed ({len(done_subs)})")
            for name, est, actual in done_subs:
                lines.append(f"- {name}  ~{est}m -> {actual}m")
            total_est = sum(e for _, e, _ in done_subs)
            total_actual = sum(a for _, _, a in done_subs)
            lines.append("")
            lines.append(
                f"Total: {time_utils.hours_minutes(total_est)} estimated, "
                f"{time_utils.hours_minutes(total_actual)} actual"
            )
        if estimated > 0:
            pct = int(on_time / estimated * 100)
            lines.append(f"On-time: {on_time}/{estimated} ({pct}%)")
        if undone_subs:
            lines.append("")
            lines.append(f"### Incomplete ({len(undone_subs)})")
            for name, est in undone_subs:
                lines.append(f"- {name}  ~{est}m")
            total_undone = sum(e for _, e in undone_subs)
            lines.append("")
            lines.append(f"Unfinished estimate: {time_utils.hours_minutes(total_undone)}")

    path.write_text("\n".join(lines) + "\n")
    display.success(f"Saved to {path}")
