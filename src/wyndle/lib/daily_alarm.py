"""Build and store a work/buffer/break schedule from today's Markdown tasks.

The plan records task IDs and clock boundaries, not a second task list. Task
names and completion state are resolved from the daily note on each read.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from uuid import uuid4

from wyndle.lib import time_utils
from wyndle.lib.config import WyndleConfig
from wyndle.lib.state import State

_PLAN_KEY = "today_alarm_plan"
_TIME = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d\Z")
_MAX_WORK_BLOCKS = 200


def _minutes(data: dict, key: str, minimum: int, maximum: int,
             default: int | None = None) -> int:
    value = data.get(key, default)
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{key} must be between {minimum} and {maximum} minutes.")
    return value


def _start_epoch(value: object) -> int:
    if not isinstance(value, str) or not _TIME.fullmatch(value):
        raise ValueError("start must be a time in HH:MM format.")
    today = time_utils.now().date()
    return int(datetime.combine(today, time_utils.parse_time(value)).timestamp())


def build_plan(cfg: WyndleConfig, tasks: list[dict], data: dict) -> dict:
    """Validate a selection and divide its remaining estimates into blocks."""
    start = data.get("start")
    cursor = _start_epoch(start)
    work_minutes = _minutes(data, "workMinutes", 5, 120)
    work_mode = data.get("workMode", "fixed")
    if work_mode not in ("fixed", "estimate"):
        raise ValueError("workMode must be fixed or estimate.")
    buffer_minutes = _minutes(data, "bufferMinutes", 1, 60, 5)
    break_minutes = _minutes(data, "breakMinutes", 1, 60)
    selected = data.get("taskIds")
    if (not isinstance(selected, list) or not 1 <= len(selected) <= 60
            or any(not isinstance(task_id, str) for task_id in selected)
            or len(set(selected)) != len(selected)):
        raise ValueError("Choose 1 to 60 distinct tasks for the plan.")

    available = {task["id"]: task for task in tasks if not task["done"]}
    if any(task_id not in available for task_id in selected):
        raise ValueError("A selected task changed. Refresh and try again.")

    day_end = _start_epoch("23:59") + 60
    limit = _start_epoch(cfg.hard_stop) if cfg.features.hard_stop else day_end
    limit_name = "your hard stop" if cfg.features.hard_stop else "midnight"
    if cursor >= limit:
        raise ValueError(f"Start the plan before {limit_name}.")

    blocks: list[dict] = []
    work_count = 0
    for task_id in selected:
        task = available[task_id]
        remaining = math.ceil((task["estimate"] * 60 - task["elapsed"]) / 60)
        if remaining <= 0:
            remaining = work_minutes  # An unfinished or unestimated task still gets a block.
        if work_mode == "estimate" and remaining > 480:
            raise ValueError(
                "A task needs more than 480 minutes. Use fixed blocks or shorten its estimate."
            )
        while remaining:
            if work_count >= _MAX_WORK_BLOCKS:
                raise ValueError("The plan has too many work blocks. Choose fewer tasks.")
            minutes = remaining if work_mode == "estimate" else min(work_minutes, remaining)
            work_end = cursor + minutes * 60
            buffer_end = work_end + buffer_minutes * 60
            break_end = buffer_end + break_minutes * 60
            if break_end > limit:
                raise ValueError(f"The plan runs past {limit_name}. "
                                 "Choose fewer tasks or an earlier start.")
            blocks.extend((
                {"kind": "work", "start": cursor, "end": work_end,
                 "minutes": minutes, "taskId": task_id},
                {"kind": "buffer", "start": work_end, "end": buffer_end,
                 "minutes": buffer_minutes, "taskId": ""},
                {"kind": "break", "start": buffer_end, "end": break_end,
                 "minutes": break_minutes, "taskId": ""},
            ))
            cursor = break_end
            remaining -= minutes
            work_count += 1

    return {"id": uuid4().hex, "start": start, "workMinutes": work_minutes,
            "workMode": work_mode,
            "bufferMinutes": buffer_minutes, "breakMinutes": break_minutes,
            "selectedTaskIds": selected, "blocks": blocks}


def save_plan(cfg: WyndleConfig, state: State, tasks: list[dict], data: dict) -> None:
    """Replace today's plan only after all settings and task IDs validate."""
    plan = build_plan(cfg, tasks, data)
    state.set(_PLAN_KEY, json.dumps(plan, separators=(",", ":")))


def clear_plan(state: State) -> None:
    state.clear(_PLAN_KEY)


def read_plan(state: State, tasks: list[dict]) -> dict | None:
    """Return the schedule with live names and completion state from Markdown."""
    raw = state.get(_PLAN_KEY)
    if not raw:
        return None
    try:
        plan = json.loads(raw)
        if not isinstance(plan, dict) or not isinstance(plan.get("blocks"), list):
            return None
    except (TypeError, ValueError):
        return None
    by_id = {task["id"]: task for task in tasks}
    blocks = []
    for block in plan["blocks"]:
        if not isinstance(block, dict):
            return None
        task = by_id.get(block.get("taskId")) if block.get("kind") == "work" else None
        title = task["title"] if task else {
            "work": "Task changed", "buffer": "Buffer", "break": "Break",
        }.get(block.get("kind"), "Block")
        blocks.append({**block,
                       "title": title,
                       "parent": task["parent"] if task else "",
                       "done": bool(task and task["done"]),
                       "missing": block.get("kind") == "work" and task is None})
    return {**plan, "blocks": blocks}
