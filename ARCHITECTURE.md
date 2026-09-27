# Architecture

For a practical modification guide covering all three interfaces, see
[DEVELOPING.md](DEVELOPING.md). The browser dashboard uses `lib/dashboard.py`
through the local server in `commands/ui.py`; its modular assets live in `web/`.
The `vscode/` extension embeds that same dashboard and shares its backend.

## Module Layout

```
src/wyndle/
  __init__.py                 # Version, architecture overview
  cli.py                      # Click command router (lazy imports), auto-wrap
  default_config.yaml
  commands/
    morning.py                # Carryover, chores, new tasks
    start.py                  # wyndle start + wyndle switch
    restart.py                # wyndle restart [minutes]
    next_cmd.py               # wyndle next (close current -> start next)
    break_cmd.py              # wyndle break
    stuck.py                  # wyndle stuck
    status.py                 # wyndle status (with remaining time + future counts)
    wrap.py                   # wyndle wrap + auto-wrap (work summary, task note sync)
    reflect.py                # wyndle reflect (weekly review)
    daemon.py                 # wyndle daemon (launchd management)
  lib/
    markdown_dom.py           # DOM-based markdown parser (no Obsidian dependency)
    obsidian.py               # Daily note reading/writing via markdown_dom
    task_notes.py             # Persistent per-task note CRUD and sync
    models.py                 # Task, SubTask, TaskNote, WorkSummary dataclasses
    config.py                 # YAML config, generic dataclass hydration
    state.py                  # File-based key-value state, subtask timers
    time_utils.py             # Time parsing, formatting, math
    timer.py                  # Focus block countdown, overflow loop
    display.py                # Rich terminal UI helpers
    notifier.py               # Background macOS notifications (launchd)
```

## Markdown DOM (markdown_dom.py)

The DOM parser is the foundation layer.  It replaces the previous regex-based line
iteration and decouples all note operations from Obsidian.

### Block Model

```
MarkdownDoc
  .frontmatter     FrontmatterBlock | None    (YAML between --- markers)
  .preamble         list[str]                  (lines before first heading)
  .blocks           list[HeadingBlock]         (flat, document order)

FrontmatterBlock
  .raw_lines        list[str]                  (original lines including ---)
  .data             dict[str, Any]             (parsed key-value pairs)

HeadingBlock
  .level            int                        (1 = #, 2 = ##, 3 = ###, ...)
  .title            str                        (heading text, stripped)
  .heading_line     str                        (original line with # prefix)
  .content          list[str]                  (body lines until next heading)

NoteItem                                        (nested list tree node)
  .text             str                        (content without bullet marker)
  .indent           int                        (indentation depth, 0 = top)
  .marker           str                        (-, *, +, 1., 1) etc.)
  .children         list[NoteItem]             (nested items)
```

### List Parsing

The DOM handles all standard markdown list markers:

| Marker | Example |
|--------|---------|
| `-` | `- unordered item` |
| `*` | `* asterisk item` |
| `+` | `+ plus item` |
| `1.` | `1. numbered (dot)` |
| `1)` | `1) numbered (paren)` |

Nesting is determined by indentation (spaces or tabs).  `get_checkbox_notes`
flattens nested items into a single list.  `get_nested_notes` preserves
the tree structure via `NoteItem.children`.

### Hierarchy

Blocks are stored flat.  Nesting is determined by heading level at query time:

```markdown
## Task Details        <- level 2
### Project Alpha      <- level 3, child of Task Details
- [ ] Read docs ~30m   <- content of Project Alpha
  - some note          <- content of Project Alpha
### Daily Chores       <- level 3, sibling of Project Alpha
```

`doc.get_subsections(parent)` returns direct children (one level deeper).
`doc.find_subsection(parent, title)` finds a child by exact title (case-insensitive).
It is deliberately not a substring match, so `Auth refactor` can never resolve to
(and overwrite) a sibling `### Auth`.

### Query API

| Method | Returns | Use |
|--------|---------|-----|
| `find_section(title, level)` | `HeadingBlock \| None` | Find first matching section |
| `get_subsections(parent)` | `list[HeadingBlock]` | Direct child headings |
| `find_subsection(parent, title)` | `HeadingBlock \| None` | Child by exact title |
| `get_checkboxes(block)` | `list[(idx, done, text)]` | Parse `- [x]`/`- [ ]` lines |
| `get_checkbox_notes(block)` | `dict[str, list[str]]` | Indented notes per checkbox (flattened) |
| `get_nested_notes(block)` | `list[NoteItem]` | Full nested tree of all list items |

### Mutation API

| Method | Effect |
|--------|--------|
| `replace_content(block, lines)` | Replace all content lines |
| `append_content(block, lines)` | Append to content |
| `insert_after(anchor, block)` | Insert after anchor + children |
| `insert_before(anchor, block)` | Insert before anchor |
| `remove_subsection(sub)` | Remove sub + children |
| `append_block(block)` | Append to end of document |
| `update_frontmatter(data)` | Replace frontmatter |

### Serialization

`doc.serialize()` rebuilds the full markdown.  Content lines are preserved
verbatim -- only modified blocks change.  Always ends with a newline.

### Inline Text Helpers

Located in `markdown_dom.py`, used by both `obsidian.py` and `task_notes.py`:

| Function | Input | Output |
|----------|-------|--------|
| `parse_estimate(text)` | `"Read docs ~30m"` | `30` |
| `strip_estimate(text)` | `"Read docs ~30m"` | `"Read docs"` |
| `parse_status_tag(text)` | `"item ~future"` | `("item", "future")` |
| `parse_added_date(text)` | `"item (added: 2026-04-01)"` | `("item", "2026-04-01")` |
| `strip_all_metadata(text)` | `"item ~30m ~open (added: ...)"` | `"item"` |

## Data Flow

```
                 Morning                            Wrap
                 =======                            ====

Task Note        read open subtasks                 read current note
(vault/tasks/)   + open notes                       strict-match merge notes
                       |                                  ^
                       v                                  |
Daily Note       write checkboxes                   read checkboxes + notes
(vault/daily/)   + indented notes                   read elapsed from state
                 (no status tags)                         ^
                       |                                  |
                       v                                  |
User             edits in any editor     -->    State (subtask timers)
```

### Sync Rules

**Morning carryover** (task note -> daily note):
- Only subtasks with `status: open` are written to daily note
- Only notes tagged `~open` are carried over
- `~deferred` and `~future` items stay in task note
- Status tags are NOT written to daily note

**Wrap sync** (daily note -> task note):
- Each daily note line is compared exactly against existing task note notes
- Exact match: existing entry preserved (with its status tag)
- No match: appended as new `~open` note
- Existing `~deferred`/`~future` notes are never modified by wrap
- Does not overwrite `deferred` or `future` subtask status

### Task Note Format (v1.3.0)

```markdown
---
task: Project Alpha
created: 2026-03-31
status: open
total_time_min: 32
days_worked: [2026-04-02]
---

# Project Alpha

## Subtasks
- Create action plan ~15m ~done (added: 2026-04-01)
- Read docs ~45m ~open (added: 2026-04-01)
- Future work ~30m ~future (added: 2026-04-02)

## Create action plan
- started: 2026-04-01
- time_min: 15
- jira_link: PROJ-123
### Notes
- Found good resource ~open
- Parked idea ~deferred

## Read docs
- started: 2026-04-01
- time_min: 0
- jira_link:
### Notes
```

The `## Subtasks` summary section is the single source of truth for subtask
status, estimate, and added date.  Detail sections hold time, jira links,
and notes.

### Daily Note Format (v1.3.0)

```markdown
---
date: 2026-04-01
day: Wednesday
type: daily
---

# Wednesday -- 2026-04-01

## High Level Tasks (Priority Order)
- [ ] Project Alpha
- [ ] Another Project

## Task Details
### Daily Chores
- [ ] Plan the day ~15m
- [ ] Reply to Slack ~15m
- [ ] Meetings ~15m

### Project Alpha
- [ ] Read docs ~30m
  - Found good resource
- [ ] Write code ~45m

## Log
_Auto-logged by Wyndle_

## Shutdown Notes
> _filled by wyndle wrap_
```

Daily Chores are NOT in High Level Tasks.  They are always the first
subsection in Task Details.  They reset daily (no persistent task note).

## State Management

File-based key-value store in `~/.wyndle/state/`.

| Key | Content | Set by |
|-----|---------|--------|
| `today_date` | `YYYY-MM-DD` | morning |
| `today_started` | `true` | morning |
| `today_start_time` | `HH:MM` | morning |
| `today_one_thing` | task name | morning |
| `today_current_task` | task name | start |
| `today_focused_min` | integer | timer |
| `today_wrapped` | `true` | wrap, auto-wrap |
| `today_block_active` | `true` | timer, break |
| `today_block_end` | unix epoch | timer |
| `today_active_subtask` | hash key | start/switch/restart |
| `today_active_subtask_text` | raw text | start/switch/restart |
| `today_last_subtask_text` | raw text | start/switch/restart |
| `today_milestone_<min>` | `true` | notifier |
| `tomorrow_first_task` | task name | wrap |
| `st_<hash>_elapsed` | seconds (int) | state |
| `st_<hash>_active_since` | unix epoch | state |

## Key Design Decisions

**DOM-based parsing.** `markdown_dom.py` provides a structured parser that works
with any markdown editor.  No Obsidian-specific assumptions.

**Status tags in task notes only.** `~open`/`~deferred`/`~future` tags exist
only in `vault/tasks/*.md`.  Daily notes are clean checkboxes.

**Strict-match note sync.** Wrap compares daily note lines exactly against task
note lines.  Changed lines are appended as new rather than overwriting.

**Typed models.** All data flows through dataclasses in `models.py`.

**Generic config hydration.** `_hydrate(cls, data)` recursively builds nested
dataclasses from YAML dicts.

**File-based state.** One file per key.  Crash-proof, shell-inspectable.

**Lazy imports.** Command modules imported inside Click handlers.

**Auto-wrap.** `_setup()` in cli.py calls `wrap.auto_wrap_yesterday`, which syncs
the previous day to task notes on the first command of a new day and then marks
it wrapped so later commands do not sync (and add its time) again.

**Centralized clock.** All time reads go through `time_utils.now()`; tests freeze
it with the `clock` fixture in `tests/conftest.py`.

**Chores as Task Details only.** Daily chores are trackable subtasks but do not
clutter the High Level Tasks priority list.
