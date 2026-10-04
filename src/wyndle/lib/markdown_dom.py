"""DOM-based markdown parser for structured note files.

Parses markdown into an ordered list of heading-delimited blocks with
optional YAML frontmatter.  Supports querying by heading text/level,
mutation (replace, append, insert), and lossless serialization.

Works with any markdown editor or plain files.

Block model::

    MarkdownDoc
      .frontmatter   FrontmatterBlock | None
      .preamble      list[str]        (lines before first heading)
      .blocks        list[HeadingBlock]  (flat, in document order)

Nesting is determined by heading level: ``##`` contains ``###`` etc.
Use :meth:`MarkdownDoc.get_subsections` to walk the hierarchy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Inline text helpers (used by multiple modules)
# ---------------------------------------------------------------------------

_ESTIMATE_RE = re.compile(r"~(\d+)m")
_PRIORITY_RE = re.compile(r"(?<!\S)~p0\b", re.IGNORECASE)
_OPTIONAL_RE = re.compile(r"(?<!\S)~optional\b", re.IGNORECASE)
_TASK_STATS_RE = re.compile(r"\s*<!-- wyndle:start=(\d+);end=(\d+);elapsed=(\d+) -->")
_STATUS_RE = re.compile(r"~(open|done|deferred|future)\b")
_ADDED_RE = re.compile(r"\(added:\s*(\d{4}-\d{2}-\d{2})\)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)")

# Matches -, *, + bullet markers and numbered lists (1. or 1))
_LIST_ITEM_RE = re.compile(r"^(\s*)([-*+]|\d+[.)]) (.*)")
# Checkbox specifically
_CHECKBOX_RE = re.compile(r"^(\s*)- \[([ xX])\] (.*)")


def parse_estimate(text: str) -> int:
    """Extract a ``~Xm`` minute estimate from *text*.  Returns 0 if absent."""
    match = _ESTIMATE_RE.search(text)
    return int(match.group(1)) if match else 0


def strip_estimate(text: str) -> str:
    """Return a daily subtask's display name without Wyndle metadata."""
    text = _ESTIMATE_RE.sub("", text)
    text = _PRIORITY_RE.sub("", text)
    text = _OPTIONAL_RE.sub("", text)
    return _TASK_STATS_RE.sub("", text).strip()


def parse_priority(text: str) -> bool:
    """Whether a subtask has the non-negotiable ``~p0`` marker."""
    return bool(_PRIORITY_RE.search(text))


def parse_optional(text: str) -> bool:
    """Whether a subtask has the ``~optional`` marker, unless it is P0."""
    return bool(_OPTIONAL_RE.search(text)) and not parse_priority(text)


def parse_task_stats(text: str) -> tuple[int, int, int]:
    """Return (first start, completion, tracked seconds) from a checkbox."""
    match = _TASK_STATS_RE.search(text)
    return tuple(map(int, match.groups())) if match else (0, 0, 0)


def format_task_text(text: str, estimate: int, priority: bool,
                     optional: bool = False,
                     started: int = 0, ended: int = 0, elapsed: int = 0) -> str:
    """Build a subtask checkbox label while keeping its plain Markdown title."""
    title = strip_estimate(text)
    suffix = f" ~{estimate}m" if estimate else ""
    suffix += " ~p0" if priority else ""
    suffix += " ~optional" if optional and not priority else ""
    if started or ended or elapsed:
        suffix += f" <!-- wyndle:start={started};end={ended};elapsed={elapsed} -->"
    return title + suffix


def parse_status_tag(text: str) -> tuple[str, str]:
    """Extract ``~open``/``~done``/``~deferred``/``~future`` from *text*.

    Returns:
        Tuple of ``(cleaned_text, status_string)``.  Status is ``""``
        when no tag is found.
    """
    match = _STATUS_RE.search(text)
    if not match:
        return text, ""
    clean = (text[: match.start()].rstrip() + " " + text[match.end() :].lstrip()).strip()
    return clean, match.group(1)


def parse_added_date(text: str) -> tuple[str, str]:
    """Extract ``(added: YYYY-MM-DD)`` from *text*.

    Returns:
        Tuple of ``(cleaned_text, iso_date_string)``.  Date is ``""``
        when not found.
    """
    match = _ADDED_RE.search(text)
    if not match:
        return text, ""
    clean = (text[: match.start()].rstrip() + " " + text[match.end() :].lstrip()).strip()
    return clean, match.group(1)


def strip_all_metadata(text: str) -> str:
    """Remove Wyndle's inline estimate, status, tier, and date metadata."""
    text = _ESTIMATE_RE.sub("", text)
    text = _STATUS_RE.sub("", text)
    text = _ADDED_RE.sub("", text)
    text = _PRIORITY_RE.sub("", text)
    text = _OPTIONAL_RE.sub("", text)
    text = _TASK_STATS_RE.sub("", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Block dataclasses
# ---------------------------------------------------------------------------


@dataclass
class FrontmatterBlock:
    """YAML frontmatter between ``---`` markers."""

    raw_lines: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class HeadingBlock:
    """A markdown heading and all content lines until the next heading."""

    level: int
    title: str
    heading_line: str
    content: list[str] = field(default_factory=list)


@dataclass
class NoteItem:
    """A single list item in a nested note tree.

    Attributes:
        text:     Content text (without the bullet marker).
        indent:   Indentation depth (0 = top-level under parent).
        marker:   Original marker string (``-``, ``*``, ``+``, ``1.``).
        children: Nested items at the next indentation level.
    """
    text: str
    indent: int = 0
    marker: str = "-"
    children: list[NoteItem] = field(default_factory=list)


def _indent_level(line: str) -> int:
    """Count leading spaces / tabs (tab = 4 spaces) to determine depth."""
    spaces = 0
    for ch in line:
        if ch == " ":
            spaces += 1
        elif ch == "\t":
            spaces += 4
        else:
            break
    return spaces


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------


class MarkdownDoc:
    """DOM representation of a markdown document.

    Parses the input text into :class:`FrontmatterBlock` (optional),
    preamble lines, and an ordered list of :class:`HeadingBlock`.

    Args:
        text: Raw markdown string to parse.
    """

    def __init__(self, text: str) -> None:
        self.frontmatter: FrontmatterBlock | None = None
        self.preamble: list[str] = []
        self.blocks: list[HeadingBlock] = []
        self._parse(text)

    # -- Parsing ----------------------------------------------------------

    def _parse(self, text: str) -> None:
        """Split *text* into frontmatter + heading-delimited blocks."""
        lines = text.splitlines()
        idx = self._parse_frontmatter(lines)
        current: HeadingBlock | None = None
        for i in range(idx, len(lines)):
            m = _HEADING_RE.match(lines[i])
            if m:
                if current is not None:
                    self.blocks.append(current)
                current = HeadingBlock(
                    level=len(m.group(1)),
                    title=m.group(2).strip(),
                    heading_line=lines[i],
                )
            elif current is not None:
                current.content.append(lines[i])
            else:
                self.preamble.append(lines[i])
        if current is not None:
            self.blocks.append(current)

    def _parse_frontmatter(self, lines: list[str]) -> int:
        """Parse optional YAML frontmatter.  Returns the body start index."""
        if not lines or lines[0].strip() != "---":
            return 0
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                fm_lines = lines[: i + 1]
                data = _parse_yaml_flat(lines[1:i])
                self.frontmatter = FrontmatterBlock(raw_lines=fm_lines, data=data)
                return i + 1
        return 0

    # -- Queries ----------------------------------------------------------

    def find_section(self, title_contains: str, level: int = 0) -> HeadingBlock | None:
        """Return the first block whose title contains *title_contains*.

        Args:
            title_contains: Case-insensitive substring to match.
            level: If non-zero, restrict to this heading level.
        """
        needle = title_contains.lower()
        for block in self.blocks:
            if level and block.level != level:
                continue
            if needle in block.title.lower():
                return block
        return None

    def get_subsections(self, parent: HeadingBlock) -> list[HeadingBlock]:
        """Return direct child headings (one level deeper) under *parent*."""
        try:
            idx = self.blocks.index(parent)
        except ValueError:
            return []
        children: list[HeadingBlock] = []
        for block in self.blocks[idx + 1 :]:
            if block.level <= parent.level:
                break
            if block.level == parent.level + 1:
                children.append(block)
        return children

    def find_subsection(self, parent: HeadingBlock, title: str) -> HeadingBlock | None:
        """Find a subsection of *parent* by exact title (case-insensitive).

        Deliberately not a substring match: ``"Auth refactor"`` must never
        resolve to a sibling ``### Auth``, or writes would replace it.
        """
        needle = title.strip().lower()
        for sub in self.get_subsections(parent):
            if sub.title.lower() == needle:
                return sub
        return None

    def get_checkboxes(self, block: HeadingBlock) -> list[tuple[int, bool, str]]:
        """Parse checkbox lines in *block*'s content.

        Handles ``- [x]``, ``- [X]``, and ``- [ ]`` at any indent level.

        Returns:
            List of ``(content_line_index, checked, raw_text_after_marker)``.
        """
        results: list[tuple[int, bool, str]] = []
        for i, line in enumerate(block.content):
            m = _CHECKBOX_RE.match(line)
            if m:
                checked = m.group(2).lower() == "x"
                results.append((i, checked, m.group(3).strip()))
        return results

    def get_checkbox_notes(self, block: HeadingBlock) -> dict[str, list[str]]:
        """Map ``{display_text: [note_line, ...]}`` from indented items.

        Collects all list items (``-``, ``*``, ``+``, numbered) nested
        under each checkbox.  Multi-level nesting is flattened into a
        single list preserving the raw text.

        Display text has the ``~Xm`` estimate stripped.
        """
        notes: dict[str, list[str]] = {}
        current = ""
        checkbox_indent = -1
        for line in block.content:
            cb = _CHECKBOX_RE.match(line)
            if cb:
                raw = cb.group(3).strip()
                current = strip_estimate(raw)
                checkbox_indent = len(cb.group(1))
                notes.setdefault(current, [])
                continue
            if not current:
                continue
            m = _LIST_ITEM_RE.match(line)
            if m and len(m.group(1)) > checkbox_indent:
                notes[current].append(m.group(3).strip())
            elif line.strip() and _indent_level(line) > checkbox_indent:
                # Continuation line (no bullet) but still indented
                notes[current].append(line.strip())
            elif not line.strip():
                continue  # blank lines within a block
            elif _indent_level(line) <= checkbox_indent:
                # Back to checkbox level or above -- stop collecting
                if not _CHECKBOX_RE.match(line):
                    current = ""
        return notes

    def get_nested_notes(self, block: HeadingBlock) -> list[NoteItem]:
        """Parse all list items in *block* into a nested tree.

        Handles ``-``, ``*``, ``+``, and numbered (``1.``, ``1)``)
        markers.  Nesting is determined by indentation level.

        Returns:
            Top-level :class:`NoteItem` objects with ``children``
            populated recursively.
        """
        flat: list[tuple[int, str, str]] = []  # (indent, marker, text)
        for line in block.content:
            m = _LIST_ITEM_RE.match(line)
            if m:
                flat.append((len(m.group(1)), m.group(2), m.group(3).strip()))
        return _build_note_tree(flat, 0) if flat else []

    # -- Mutations --------------------------------------------------------

    def replace_content(self, block: HeadingBlock, lines: list[str]) -> None:
        """Replace all content lines of *block*."""
        block.content = list(lines)

    def append_content(self, block: HeadingBlock, lines: list[str]) -> None:
        """Append *lines* to the end of *block*'s content."""
        block.content.extend(lines)

    def insert_after(self, anchor: HeadingBlock, new_block: HeadingBlock) -> None:
        """Insert *new_block* after *anchor* and all its nested children."""
        idx = self.blocks.index(anchor) + 1
        while idx < len(self.blocks) and self.blocks[idx].level > anchor.level:
            idx += 1
        self.blocks.insert(idx, new_block)

    def insert_before(self, anchor: HeadingBlock, new_block: HeadingBlock) -> None:
        """Insert *new_block* immediately before *anchor*."""
        self.blocks.insert(self.blocks.index(anchor), new_block)

    def remove_subsection(self, sub: HeadingBlock) -> None:
        """Remove *sub* and all its nested children from the block list."""
        idx = self.blocks.index(sub)
        end = idx + 1
        while end < len(self.blocks) and self.blocks[end].level > sub.level:
            end += 1
        del self.blocks[idx:end]

    def append_block(self, block: HeadingBlock) -> None:
        """Append *block* to the end of the document."""
        self.blocks.append(block)

    def update_frontmatter(self, data: dict[str, Any]) -> None:
        """Replace frontmatter data and regenerate raw lines."""
        self.frontmatter = FrontmatterBlock(
            raw_lines=_serialize_yaml_flat(data),
            data=data,
        )

    # -- Serialization ----------------------------------------------------

    def serialize(self) -> str:
        """Rebuild the full markdown document as a string."""
        parts: list[str] = []
        if self.frontmatter:
            parts.extend(self.frontmatter.raw_lines)
        parts.extend(self.preamble)
        for block in self.blocks:
            parts.append(block.heading_line)
            parts.extend(block.content)
        result = "\n".join(parts)
        if not result.endswith("\n"):
            result += "\n"
        return result


def _build_note_tree(
    items: list[tuple[int, str, str]], min_indent: int,
) -> list[NoteItem]:
    """Recursively build a nested NoteItem tree from flat (indent, marker, text) tuples."""
    result: list[NoteItem] = []
    i = 0
    while i < len(items):
        indent, marker, text = items[i]
        if indent < min_indent:
            break
        node = NoteItem(text=text, indent=indent, marker=marker)
        # Collect children (deeper indent)
        children_items: list[tuple[int, str, str]] = []
        j = i + 1
        while j < len(items) and items[j][0] > indent:
            children_items.append(items[j])
            j += 1
        if children_items:
            node.children = _build_note_tree(children_items, children_items[0][0])
        result.append(node)
        i = j
    return result


# ---------------------------------------------------------------------------
# YAML helpers (minimal, no external dependency)
# ---------------------------------------------------------------------------


def _parse_yaml_flat(lines: list[str]) -> dict[str, Any]:
    """Parse flat YAML key-value pairs (handles bracket lists)."""
    data: dict[str, Any] = {}
    for line in lines:
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        val = val.strip().strip('"').strip("'")
        if val.startswith("[") and val.endswith("]"):
            items = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",") if v.strip()]
            data[key.strip()] = items
        else:
            data[key.strip()] = val
    return data


def _serialize_yaml_flat(data: dict[str, Any]) -> list[str]:
    """Serialize a flat dict to YAML frontmatter lines (with --- delimiters)."""
    lines = ["---"]
    for key, val in data.items():
        if isinstance(val, list):
            items = ", ".join(str(v) for v in val)
            lines.append(f"{key}: [{items}]")
        else:
            lines.append(f"{key}: {val}")
    lines.append("---")
    return lines
