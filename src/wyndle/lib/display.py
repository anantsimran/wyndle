"""Terminal display helpers built on :pypi:`rich`.

Every user-facing print statement goes through this module so the
visual style is consistent.  Colours are defined once as module-level
constants and referenced everywhere else.
"""

from __future__ import annotations

from rich.console import Console
from rich.text import Text

console = Console()

# -- Colour palette --
ACCENT = "dodger_blue1"
WARN = "dark_orange"
ALERT = "red1"
SUCCESS = "pale_green3"
DIM = "grey62"
BOLD = "bold"


def header(msg: str) -> None:
    """Print a section header with horizontal rules above and below."""
    console.print()
    console.print(f"{'─' * 60}", style=DIM)
    console.print(f"  {msg}", style=BOLD)
    console.print(f"{'─' * 60}", style=DIM)
    console.print()


def accent(msg: str) -> None:
    """Print an accent-coloured line (blue)."""
    console.print(f"  {msg}", style=ACCENT)


def success(msg: str) -> None:
    """Print a success line with a check-mark prefix."""
    console.print(f"  ✓ {msg}", style=SUCCESS)


def warn(msg: str) -> None:
    """Print a warning line with a triangle prefix."""
    console.print(f"  ⚠ {msg}", style=WARN)


def error(msg: str) -> None:
    """Print an error line with a cross prefix."""
    console.print(f"  ✗ {msg}", style=ALERT)


def dim(msg: str) -> None:
    """Print a subdued / secondary-info line."""
    console.print(f"  {msg}", style=DIM)


def bold_print(msg: str) -> None:
    """Print a bold line."""
    console.print(f"  {msg}", style=BOLD)


def info(msg: str, style: str = "") -> None:
    """Print an informational line with an optional Rich style override."""
    console.print(f"  {msg}", style=style or "")


def prompt(question: str) -> str:
    """Prompt the user for free-text input and return their answer.

    Args:
        question: The prompt text shown before the cursor.
    """
    return console.input(Text(f"  ▸ {question} ", style=ACCENT))


def confirm(question: str) -> bool:
    """Ask a yes/no question.  Returns ``True`` for *y* or *yes*."""
    answer = console.input(Text(f"  ▸ {question} [y/n] ", style=ACCENT))
    return answer.strip().lower() in ("y", "yes")
