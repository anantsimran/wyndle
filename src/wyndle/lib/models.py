"""Shared data models used across Wyndle commands and libraries.

All inter-module data is passed as typed dataclasses rather than raw
dicts, giving IDE support and making interfaces self-documenting.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Valid subtask statuses in task note files.
VALID_STATUSES = ("open", "done", "deferred", "future")


@dataclass
class Task:
    """A high-level task from the daily note.

    Attributes:
        text:     Raw markdown text of the task.
        done:     Whether the checkbox is checked (``[x]``).
        line_num: Zero-based line number in the note file.
    """
    text: str
    done: bool = False
    line_num: int = 0


@dataclass
class SubTask:
    """A sub-task nested under a high-level task in Task Details.

    Attributes:
        text:          Raw text including the ``~Xm`` estimate.
        display_text:  Text with the estimate stripped for display.
        done:          Whether the checkbox is checked.
        line_num:      Zero-based line number in the note file.
        estimate_min:  Parsed time estimate in minutes (0 if absent).
        parent:        Name of the parent high-level task.
    """
    text: str
    display_text: str = ""
    done: bool = False
    line_num: int = 0
    estimate_min: int = 0
    parent: str = ""


@dataclass
class RemainingWork:
    """Snapshot of uncompleted work for the current day.

    Attributes:
        high_level: Unchecked high-level tasks.
        details:    Map of task name -> list of unchecked subtasks.
    """
    high_level: list[Task] = field(default_factory=list)
    details: dict[str, list[SubTask]] = field(default_factory=dict)


@dataclass
class TaskNoteSubtask:
    """A subtask entry within a persistent task note file.

    Attributes:
        name:          Subtask display name (no estimate suffix).
        added:         ISO date when first added to the task note.
        estimate_min:  Time estimate in minutes (from ``~Xm``).
        started:       ISO date when first worked on (empty if never).
        time_min:      Total minutes spent across all days.
        status:        One of ``open``, ``done``, ``deferred``, ``future``.
                       ``deferred`` and ``future`` subtasks stay in the task
                       note but are excluded from the daily note.  ``future``
                       items appear in ``wyndle status`` remaining counts.
        jira_link:     User-editable Jira ticket.
        notes:         Bullet-point notes.  Each note is a tuple of
                       ``(text, status_tag)`` where status_tag is
                       ``open``/``deferred``/``future``.
    """
    name: str
    added: str = ""
    estimate_min: int = 0
    started: str = ""
    time_min: int = 0
    status: str = "open"
    jira_link: str = ""
    notes: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class TaskNote:
    """Persistent task note tracking a high-level task across days.

    Stored as ``vault/tasks/<slug>.md``.  Created by morning, updated
    by wrap.

    Attributes:
        name:           Display name of the high-level task.
        created:        ISO date when task was first added.
        status:         ``open`` or ``done``.
        total_time_min: Sum of all subtask times (updated by wrap).
        days_worked:    ISO dates where time was logged.
        subtasks:       Ordered list of subtask entries.
    """
    name: str
    created: str = ""
    status: str = "open"
    total_time_min: int = 0
    days_worked: list[str] = field(default_factory=list)
    subtasks: list[TaskNoteSubtask] = field(default_factory=list)


@dataclass
class WorkSummary:
    """Aggregated work statistics for wrap output.

    Attributes:
        completed:    Number of subtasks completed today.
        total:        Total subtasks across all tasks.
        actual_min:   Total tracked minutes.
        estimated_min: Total estimated minutes.
        on_time:      Subtasks completed within their estimate.
        estimated_done: Done subtasks that had an estimate.
    """
    completed: int = 0
    total: int = 0
    actual_min: int = 0
    estimated_min: int = 0
    on_time: int = 0
    estimated_done: int = 0
