# Wyndle v1.3.0

Terminal-based productivity system built for ADHD. File-based state that survives terminal crashes. Works with any markdown editor.

Wyndle manages a single daily loop: morning planning, timed focus blocks, break tracking, and a shutdown ritual that shows exactly how your planned time compared to actual time spent.

---

## Table of Contents

- [Installation](#installation)
- [Post-Install Setup](#post-install-setup)
- [Publishing to GitHub](#publishing-to-github)
- [Commands Reference](#commands-reference)
- [Daily Workflow](#daily-workflow)
- [Use Cases](#use-cases)
- [Daily Note Format](#daily-note-format)
- [Task Notes](#task-notes)
- [Status Tags](#status-tags)
- [Background Notifications](#background-notifications)
- [Configuration](#configuration)
- [Architecture](#architecture)
- [State Management](#state-management)
- [Troubleshooting](#troubleshooting)
- [Changelog](#changelog)

---

## Installation

Requires Python 3.10+.

### pipx (recommended)

```bash
brew install pipx
pipx ensurepath
pipx install wyndle

# Or from a local clone
git clone https://github.com/anantsimran/wyndle.git
cd wyndle
pipx install .
```

### pip

```bash
pip install wyndle
```

### From source (development)

```bash
git clone https://github.com/anantsimran/wyndle.git
cd wyndle
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Verify

```bash
wyndle help
```

---

## Post-Install Setup

### 1. Edit your config

On first run wyndle creates `~/.wyndle/config.yaml` with defaults:

```bash
$EDITOR ~/.wyndle/config.yaml
```

Key fields:

```yaml
user_name: "your-name"
obsidian_vault: "~/Documents/ObsidianVault"
work_start: "09:30"
hard_stop: "20:00"
```

### 2. Install background notifications (macOS)

```bash
wyndle daemon install
wyndle daemon test
```

### 3. Start your first day

```bash
wyndle morning
```

---

## Publishing to GitHub

### First-time setup

```bash
cd wyndle
git init
git add .
git commit -m "Initial commit"
```

Create a new repository on GitHub (do NOT initialize with README/license/gitignore since you already have these locally), then:

```bash
git remote add origin git@github.com:anantsimran/wyndle.git
git branch -M main
git push -u origin main
```

### Subsequent pushes

```bash
git add .
git commit -m "description of changes"
git push
```

### Tagging a release

```bash
git tag -a v1.3.0 -m "v1.3.0 release"
git push origin v1.3.0
```

### Publishing to PyPI (optional)

```bash
pip install build twine
python -m build
twine upload dist/*
```

### SSH key setup (if needed)

```bash
ssh-keygen -t ed25519 -C "your@email.com"
cat ~/.ssh/id_ed25519.pub
# Copy output -> GitHub Settings -> SSH and GPG keys -> New SSH key
ssh -T git@github.com  # verify
```

---

## Commands Reference

### wyndle morning

Start your day. Shows yesterday's shutdown notes, carries over unfinished tasks (with open subtasks and open notes from task note files), prompts for new tasks, and writes to today's daily note.

Daily chores are added as subtasks in Task Details (not in High Level Tasks). They are always the first section and reset daily.

If yesterday was not wrapped, auto-syncs subtask notes and elapsed times to task note files before starting the new day.

```bash
wyndle morning
```

### wyndle start [task]

Pick a high-level task, then a subtask, then run a timed focus block (5, 15, or 30 minutes). When the timer ends, a macOS notification fires and the block auto-extends in 5-minute overflow increments until Ctrl+C.

```bash
wyndle start
wyndle start "Build auth flow"
```

After each block: another block, switch subtask, open editor, or stop.

### wyndle restart [minutes]

Resume the last subtask. Accepts an optional duration to skip the interactive prompt.

```bash
wyndle restart        # prompt for duration
wyndle restart 5      # 5-minute block
wyndle restart 15     # 15-minute block
wyndle restart 30     # 30-minute block
```

### wyndle next

Close the current subtask and start the next one. Pauses the active subtask, asks whether to mark it done, shows remaining count, then hands off to the task/subtask picker.

```bash
wyndle next
```

### wyndle switch

Pause current subtask, show all remaining subtasks across all tasks, pick one. Elapsed time on the paused subtask is preserved.

```bash
wyndle switch
```

### wyndle break

Pause active subtask, start a break timer. After the break, offers to resume.

| Choice | Type | Duration |
|--------|------|----------|
| 1 | Lunch | 45m |
| 2 | Walk | 15m |
| 3 | Coffee / snack | 10m |
| 4 | Stretch / breathe | 5m |
| 5 | Custom | you pick |

```bash
wyndle break
```

### wyndle stuck

Interactive diagnostic for ADHD paralysis. Five handlers: don't know where to start, can't make myself, too big, distracted, frozen. Each ends with a micro-timer.

```bash
wyndle stuck
```

### wyndle status

Dashboard: day metadata, active task indicator, per-task est vs actual, completed tasks, estimated work time remaining, slack/overcommit calculation, and backlog counts from task notes (including ~future subtasks).

```bash
wyndle status
```

### wyndle open

Open today's daily note in the configured editor. Creates the note from template if needed.

```bash
wyndle open
```

### wyndle wrap

Shutdown ritual. Prints a Work Done section (completed/total subtasks, actual vs estimated, on-time stats), per-task time breakdown with planned-vs-actual totals, and prompts for reflection and tomorrow's first task. Syncs subtask notes and times to task note files using strict-match merging.

```bash
wyndle wrap
```

### wyndle reflect [weekly|monthly]

Review over time. Scans daily notes, shows a day-by-day summary (start time, end time, focused minutes, task completion), a subtask summary (completed with allotted vs spent time, then incomplete), and prompts for what worked, what didn't, and one tweak.

```bash
wyndle reflect            # last 7 days
wyndle reflect monthly    # last 30 days
```

### wyndle daemon

Background notification service (macOS launchd).

```bash
wyndle daemon install     # write plist + load
wyndle daemon uninstall   # unload + delete plist
wyndle daemon start       # load existing plist
wyndle daemon stop        # unload without deleting
wyndle daemon status      # check if running
wyndle daemon test        # fire a test notification
```

### wyndle help

Full help screen with usage guide.

---

## Daily Workflow

```
09:30  wyndle morning          # plan the day, chores auto-added
09:32  wyndle open             # add subtasks + estimates in editor
09:35  wyndle start            # pick task, pick subtask, 15m block
09:50  [notification]          # block done, overflow starts
10:05  [Ctrl+C]               # done, pick "switch" or "next"
10:06  wyndle next             # mark done, start next subtask
10:21  wyndle break            # walk break
10:36  wyndle restart 15       # resume last subtask, 15m block
10:51  wyndle status           # check remaining work + time left
...
19:45  wyndle wrap             # shutdown, syncs task notes
```

---

## Use Cases

### Late start (past 10:30 AM)

`wyndle morning` adjusts messaging by severity. Past hard stop, it switches to recovery mode: prep one thing for tomorrow.

### Switching contexts mid-day

`wyndle switch` shows all remaining subtasks grouped by parent. Previous subtask's time is frozen and resumes later. `wyndle next` is faster when you want to close the current subtask and pick the next one in one step.

### Resuming after a break or terminal crash

`wyndle restart 15` picks up the last subtask immediately. No menus.

### Estimating poorly

`wyndle wrap` shows planned-vs-actual delta per subtask and a Work Done section with completion percentage. `wyndle reflect` shows aggregate trends across the week or month. Calibrate over days.

### Can't start working at all

`wyndle stuck` covers five ADHD blocks. Each handler ends with a micro-timer to force one action.

### Working past stop time

Daemon fires escalating notifications: 60m, 30m, 15m, at stop, past grace (3m cooldown), way past (2m cooldown). Configurable or disableable.

### Forgetting to wrap yesterday

`wyndle morning` auto-wraps: reads yesterday's daily note, syncs subtask notes and times to task note files, then starts today. Auto-wrap runs on ANY command, not just morning.

### Tracking daily chores

Chores appear as subtasks under "Daily Chores" in Task Details (not in High Level Tasks). Track with `wyndle start` like any task. Default chores: Plan the day, Reply to Slack, Meetings. Resets daily, not carried over.

### Parking work for later

Set `status: deferred` in a task note to park a subtask. It stays in the task note but never appears in the daily note, start picker, or status. Change back to `open` to re-activate.

Set `status: future` for work you want to track in backlog counts (visible in `wyndle status`) but not in today's daily note.

### Checking how much work is left

`wyndle status` shows estimated remaining work time and whether you have enough time before hard stop (slack) or are overcommitted.

### Weekly and monthly reviews

`wyndle reflect` scans the past 7 days. `wyndle reflect monthly` scans 30 days. Both show per-day start/end times, per-subtask done/undone with times, and aggregate stats.

### Forgetting to start the day

Daemon sends escalating "day not started" nudges during work hours.

### Block ended but you kept working

Subtask timer continues via 5-minute overflow blocks. Daemon sends auto-extend nudge. No time lost.

### Multiple machines

State is local (`~/.wyndle/state/`). Vault syncs daily notes and task notes between machines via your editor's sync mechanism (iCloud, Syncthing, etc.).

### Disabling features

```yaml
features:
  obsidian: false
  notifications: false
  hard_stop: false
```

### Notes with different bullet formats

The markdown parser handles all standard list markers: `-`, `*`, `+`, and numbered lists (`1.`, `1)`). Nested indentation at any depth is supported. Use whatever format is natural in your editor.

---

## Daily Note Format

Created at `<vault>/daily/YYYY-MM-DD.md`:

```markdown
---
date: 2026-03-27
day: Thursday
type: daily
---

# Thursday -- 2026-03-27

## High Level Tasks (Priority Order)
- [ ] Build auth flow
- [ ] Write API tests

## Task Details
### Daily Chores
- [ ] Plan the day ~15m
- [ ] Reply to Slack ~15m
- [ ] Meetings ~15m

### Build auth flow
- [ ] Read OAuth docs ~30m
  - Found good resource at oauth.net
  - Need to check token refresh flow
- [ ] Set up middleware ~45m

## Log
_Auto-logged by Wyndle_

## Shutdown Notes
> _filled by wyndle wrap_
```

Daily Chores are in Task Details only (not in High Level Tasks). They are always the first subsection and get the same time-tracking as any other subtask.

Status tags (`~open`, `~deferred`, `~future`) do NOT appear in daily notes. They live only in task note files.

### Sections

| Section | Read by | Written by |
|---------|---------|------------|
| High Level Tasks | start, status, wrap, morning | morning |
| Task Details | start, switch, status, wrap | morning (carryover), you (in editor) |
| Log | -- | all commands (append-only) |
| Shutdown Notes | morning (yesterday's), reflect | wrap |

### Estimate format

Append `~Xm` to any subtask: `- [ ] Read OAuth docs ~30m`.

### Subtask notes

Indented bullets under a subtask are notes, synced to/from task notes by wrap/morning. Any bullet marker works: `-`, `*`, `+`, numbered. Nested indentation is preserved.

```markdown
- [ ] Read OAuth docs ~30m
  - Found good resource at oauth.net
  * Also check the RFC
    + Specifically section 4.1
  1. First step: register app
  2. Second step: implement flow
```

---

## Task Notes

Persistent per-task files at `<vault>/tasks/<slug>.md`. Track full lifecycle across days.

Created by `wyndle morning` on first add. Updated by `wyndle wrap`. Read during morning carryover.

### v1.3.0 format

```markdown
---
task: Build auth flow
created: 2026-03-28
status: open
total_time_min: 75
days_worked: [2026-03-28, 2026-03-29]
---

# Build auth flow

## Subtasks
- Read OAuth docs ~30m ~done (added: 2026-03-28)
- Set up middleware ~45m ~open (added: 2026-03-28)
- Write integration tests ~60m ~future (added: 2026-03-28)
- Old spike ~20m ~deferred (added: 2026-03-28)

## Read OAuth docs
- started: 2026-03-28
- time_min: 30
- jira_link: PROJ-100
### Notes
- Found good resource at oauth.net ~open
- RFC section 4.1 is key ~open

## Set up middleware
- started: 2026-03-29
- time_min: 45
- jira_link: PROJ-1234
### Notes
- Using express middleware pattern ~open
- Consider error handling later ~future

## Write integration tests
- started:
- time_min: 0
- jira_link:
### Notes

## Old spike
- started:
- time_min: 0
- jira_link:
### Notes
- Not urgent, park for later ~deferred
```

The `## Subtasks` section at the top is the summary: one line per subtask with estimate, status, and added date. Detail sections below hold time, jira links, and notes.

### Subtask statuses

| Status | In daily note? | In start/status? | Carries over? | In backlog count? |
|--------|---------------|-------------------|---------------|-------------------|
| `open` | yes | yes | yes | yes |
| `done` | no | no | no | no |
| `deferred` | no | no | yes (stays in task note) | no |
| `future` | no | no | yes (stays in task note) | yes |

### Note status tags

Notes within task note files can be tagged `~open`, `~deferred`, or `~future`:

| Tag | Carried to daily note? | Kept in task note? |
|-----|----------------------|-------------------|
| `~open` | yes | yes |
| `~deferred` | no | yes |
| `~future` | no | yes |

### Managing subtasks in the task note

Add subtasks directly to the task note file before running `wyndle morning`. Add them to BOTH the `## Subtasks` summary line AND create a detail section. All `open` subtasks (with `~open` notes) are pulled into the daily note during carryover.

Deleting a subtask from the daily note does NOT remove it from the task note. Wrap only syncs subtasks it finds in the daily note -- anything missing is left untouched.

### Sync directions

- **morning carryover**: task note -> daily note (open subtasks + open notes only)
- **wrap**: daily note -> task note (strict-match note merge: new/changed notes appended as ~open, existing tagged notes preserved)
- **user edits**: daily note (subtask notes), task note (jira_link, status tags)

### Legacy format support

v1.3.0 reads both the new format (with `## Subtasks` summary) and the v1.2.x format (inline metadata fields under each `## SubtaskName` heading). Files are upgraded to v1.3.0 format on next write.

---

## Status Tags

Status tags control carryover and visibility. They exist ONLY in task note files (`vault/tasks/*.md`), never in daily notes.

### Subtask status

Set on the `## Subtasks` summary line: `- Task name ~30m ~future (added: 2026-04-01)`

To change a subtask status, edit the tag in the task note file. For example, change `~future` to `~open` when you're ready to work on it.

### Note status

Set on individual note lines in the `### Notes` section: `- Some note ~deferred`

Only `~open` notes are carried to the daily note during morning carryover. Wrap never overwrites existing `~deferred` or `~future` tags on notes.

---

## Background Notifications

macOS only. Uses launchd, checks every 60 seconds.

| Type | Trigger | Cooldown |
|------|---------|----------|
| Day not started | Work hours, no wyndle morning | 20-30m |
| Nothing active | Day started, no block or break running | 15m |
| Frozen | 45+ min idle, 0 focused time | 30m |
| Auto-extend | Block ended, subtask still timing | 15m |
| 1 hour left | 60m to hard stop | 30m |
| 30 minutes left | 30m to hard stop | 15m |
| 15 minutes left | 15m to hard stop | 10m |
| Shutdown time | At hard stop | 5m |
| STOP WORKING | Past grace period | 3m |
| SERIOUSLY STOP | Way past grace | 2m |
| Wind down | 30m before sleep, day wrapped | 20m |
| Bedtime | At sleep target | 15m |
| 1h/2h/3h focused | Milestone | once each |
| Scheduled (static) | Config-driven time + message | once/day |
| Scheduled (remaining_work) | Config-driven time, computes remaining estimates | once/day |

The daemon skips all idle/extend checks when `today_block_active` is set.

### Logs

```bash
cat /tmp/wyndle-notifier.log
cat /tmp/wyndle-notifier.err
```

---

## Configuration

Location: `~/.wyndle/config.yaml`. Created on first run.

```yaml
user_name: "friend"
obsidian_vault: "~/Documents/ObsidianVault"

wake_target: "07:00"
work_start: "09:30"
hard_stop: "20:00"
sleep_target: "23:00"

late_thresholds:
  mild: "10:30"
  moderate: "12:00"
  severe: "14:00"

timer:
  micro_block: 5
  short_block: 15
  long_block: 30

hard_stop_settings:
  warn_before_min: 15
  grace_min: 10
  max_extensions: 2
  extension_min: 30

daily_chores:
  - "Plan the day"
  - "Reply to Slack"
  - "Meetings"

chore_estimate_min: 15

features:
  obsidian: true
  notifications: true
  hard_stop: true

scheduled_notifications:
  - time: "10:00"
    message: "Start the work early, dont slack"
  - time: "13:30"
    type: "remaining_work"
  - time: "15:00"
    message: "Go for a walk"
  - time: "17:00"
    message: "End the day early, dont slack"
```

Every field is optional. Missing fields use the defaults shown above.

### scheduled_notifications

| Field | Required | Description |
|-------|----------|-------------|
| `time` | yes | HH:MM when to fire |
| `message` | no | Static notification text |
| `type` | no | Dynamic type. Currently: `remaining_work` |

---

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for full details including the DOM parser model.

```
src/wyndle/
  cli.py                      # Click command router, auto-wrap
  commands/
    morning.py                # Auto-wrap, carryover, chores, new tasks
    start.py                  # wyndle start + wyndle switch
    restart.py                # wyndle restart [minutes]
    next_cmd.py               # wyndle next (close + start)
    break_cmd.py              # wyndle break
    stuck.py                  # wyndle stuck
    status.py                 # wyndle status (remaining time + future counts)
    wrap.py                   # wyndle wrap (work summary, task note sync)
    reflect.py                # wyndle reflect (weekly/monthly)
    daemon.py                 # wyndle daemon (launchd)
  lib/
    markdown_dom.py           # DOM-based markdown parser
    obsidian.py               # Daily note reading/writing via DOM
    task_notes.py             # Per-task note CRUD and sync
    models.py                 # Dataclasses (Task, SubTask, TaskNote, etc.)
    config.py                 # YAML config
    state.py                  # File-based key-value state
    time_utils.py             # Time parsing, formatting
    timer.py                  # Focus block countdown, overflow
    display.py                # Rich terminal UI
    notifier.py               # macOS notifications (launchd)
```

### Key design decisions

**DOM-based parsing.** `markdown_dom.py` parses markdown into a structured block model. Supports all bullet types (-, *, +, numbered) and nested indentation. No Obsidian dependency.

**Status tags in task notes only.** `~open`/`~deferred`/`~future` tags exist only in `vault/tasks/*.md`. Daily notes are clean checkboxes.

**Strict-match note sync.** Wrap compares daily note lines exactly against task note lines. Changed lines are appended as new `~open` entries rather than overwriting.

**File-based state.** One file per key in `~/.wyndle/state/`. Crash-proof.

**Chores in Task Details only.** Daily chores are trackable subtasks that don't clutter the High Level Tasks priority list.

---

## State Management

State lives in `~/.wyndle/state/` as individual files:

| File | Content | Set by |
|------|---------|--------|
| `today_date` | `YYYY-MM-DD` | morning |
| `today_started` | `true` | morning |
| `today_start_time` | `HH:MM` | morning |
| `today_one_thing` | task name | morning |
| `today_current_task` | task name | start |
| `today_focused_min` | integer | timer (accumulated) |
| `today_wrapped` | `true` | wrap |
| `today_block_active` | `true` | timer (during block) |
| `today_block_end` | unix epoch | timer (on Ctrl+C) |
| `today_active_subtask` | hash key | start/switch/break |
| `today_active_subtask_text` | raw text | start/switch/break |
| `today_last_subtask_text` | raw text | start/switch/restart |
| `tomorrow_first_task` | task name | wrap |
| `st_<hash>_elapsed` | seconds (int) | state (accumulated) |
| `st_<hash>_active_since` | unix epoch | state |

All `today_*` and `st_*` files cleared on new day by `state.clear_day()`.

```bash
# Inspect
cat ~/.wyndle/state/today_last_subtask_text

# Reset
rm ~/.wyndle/state/today_* ~/.wyndle/state/st_*
```

---

## Troubleshooting

### "Day not started yet" on wyndle start

Run `wyndle morning` first.

### "No previous subtask found" on wyndle restart

Run `wyndle start` first to pick a subtask.

### Daemon not sending notifications

```bash
wyndle daemon status
wyndle daemon test
cat /tmp/wyndle-notifier.err
```

If you reinstalled wyndle in a different venv, re-run `wyndle daemon install`.

### Subtask time seems wrong

Time is keyed by hash of normalised text. Renaming a subtask creates a new hash, starts at 0.

### Config not taking effect

Config is read fresh on every command. Edits apply immediately.

### Task note still in v1.2.x format

Run `wyndle wrap` or `wyndle morning` -- any write to the task note upgrades it to v1.3.0 format automatically.

---

## Changelog

### v1.3.0

- **DOM-based markdown parser.** New `markdown_dom.py` replaces regex-based line iteration. Supports all bullet types (-, *, +, numbered) and arbitrarily nested indentation. No Obsidian dependency -- works with any markdown editor.
- **Daily chores NOT in High Level Tasks.** Chores are now only in Task Details as the first subsection. They are trackable but don't clutter the priority list. Default chores changed to: Plan the day, Reply to Slack, Meetings.
- **Task note format v1.3.0.** New `## Subtasks` summary section at the top of each task note with one-liner metadata (name, estimate, status, added date). Detail sections below for time, jira, and notes. Reads legacy v1.2.x format and upgrades on write.
- **Status tags (~open, ~deferred, ~future).** Tags live in task note files only, never in daily notes. `~future` subtasks appear in backlog counts (`wyndle status`) but not in the daily note.
- **Note status tags.** Individual note lines in task notes can be tagged `~open`, `~deferred`, or `~future`. Only `~open` notes are carried to the daily note.
- **Strict-match note sync.** Wrap compares daily note lines exactly against task note lines. Changed/new notes are appended with `~open` tag. Existing tagged notes are never overwritten.
- **Work Done section in wrap.** Shows completed/total subtasks with percentage, actual vs estimated time, and on-time stats.
- **wyndle next.** New command: close current subtask (optionally mark done), then start the next one.
- **wyndle status: remaining work time.** Shows estimated work remaining, time to hard stop, and slack/overcommit calculation. Shows active task indicator. Shows backlog counts from task notes including ~future.
- **wyndle reflect: subtask + day summary.** Shows per-day start/end times and focused minutes. Shows completed subtasks with allotted vs spent time, then incomplete subtasks. Supports both weekly and monthly (`wyndle reflect monthly`).
- **Focused time fix.** `wyndle wrap` now flushes all subtask timer state to `today_focused_min` so mid-block Ctrl+C time is not lost.
- **Multi-bullet support.** The DOM parser handles -, *, +, and numbered list markers at any nesting depth.
- **Legacy format support.** Task notes and reflect both read v1.2.x formats and upgrade on write.

### v1.2.3

- Bug fix: daily chores appearing 3 times.
- Bug fix: carryover not writing tasks/subtasks.
- Bug fix: Ctrl+C during timer causes multiple overflows.
- Bug fix: switch says "no subtask found".
- Switch marks subtask done.
- Auto-wrap on every command.
- Daily wrap on-time stats.
- Weekly reflect on-time stats.
- Config-driven scheduled notifications.
- Deferred subtasks.
- Subtask `added` date.
- Task note as subtask source of truth.

### v1.2.2

- Bug fix: auto-wrap reads from yesterday's daily note.
- Daily chores as high-level task.
- `wyndle restart [minutes]`.
- Removed: `hardstop.py`, `display.banner()`, `display.big_stop()`.

### v1.2.1

- Task notes: persistent per-task markdown files.
- Daily note as editing surface with wrap-time sync.
- Auto-wrap on forgotten wraps.
- Subtask carryover with notes.
- Jira links per subtask.
- Notification fix: `today_block_active` flag.
- Overflow loop.

### v1.0.0

Initial release.

---

## License

MIT.
