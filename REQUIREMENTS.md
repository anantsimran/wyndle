# Wyndle requirements

## Purpose and scope

Wyndle is a local daily-work system for choosing tasks, tracking focus and breaks, and reviewing progress. This specification covers the existing Python package, browser dashboard, and Wyndle VS Code sidebar. The separate [Full Focus Timers](vscode-timers/REQUIREMENTS.md) and in-progress [Reading Desk](vscode-reader/REQUIREMENTS.md) have their own requirements.

Markdown notes are the durable work record. The dashboard and CLI must operate on the same notes and timer state. The VS Code sidebar must show the same dashboard through a local Wyndle server.

## Installation and configuration

- **W-01** The Python package shall expose a `wyndle` command and support Python 3.10 or newer. Users shall be able to install it with `uv tool install` from GitHub or run it from a checkout with `uv run`.
- **W-02** First use shall create a readable config at `~/.wyndle/config.yaml`. `notes_dir` shall select the note root and default to `~/Documents/Wyndle`; CLI and dashboard shall use the same value.
- **W-03** The core CLI and dashboard shall work locally without an account, cloud service, frontend build, or VS Code extension. The optional MCP server and macOS notification daemon shall be separately enabled.

## Daily work and notes

- **W-04** A user shall be able to start a day, carry selected unfinished high-level tasks forward in the dashboard, add new high-level tasks and subtasks, and include configured daily chores. CLI `morning` shall provide its interactive start workflow.
- **W-05** Tasks shall support planned minutes, P0/regular/optional type, completion, notes, reordering within a high-level task, and deletion from today's plan. A completed parent shall complete its subtasks. Deletion shall preserve previously saved focus history.
- **W-06** The daily note shall remain plain Markdown at `<notes_dir>/daily/YYYY-MM-DD.md`, with high-level tasks, task details, log, and shutdown notes. Persistent task notes shall live under `tasks/`; review notes shall live under `weekly/`. Existing note formats and unrelated Markdown content shall survive normal Wyndle edits.
- **W-07** Note parsing, formatting, carryover, and sync rules shall work in `src/wyndle/lib/` without importing the HTTP server or browser UI. CLI and dashboard actions shall share those rules. The browser shall receive API data and shall not parse or write Markdown files itself.
- **W-08** Wrapping a day shall stop active focus, save a work summary and tomorrow's first step, and sync notes and times to task notes. The next day's CLI setup shall sync an unwrapped previous day once, without erasing its work. Daily state shall reset for a new day.

## Focus, plans, and review

- **W-09** Starting focus on a task shall pause any previous active task. Pause and resume shall preserve accumulated elapsed time. The browser shall show remaining focus-block time and overtime until the user pauses, switches, completes, takes a break, or wraps.
- **W-10** Breaks shall have a separate timer and shall never add to focused task time. Browser focus and break state shall survive refreshes and server restarts because server-side state records the relevant times.
- **W-11** The Daily Alarm page shall let a user order unfinished tasks and save a same-day sequence of work, buffer, and break blocks that fits before the configured hard stop. Saving a plan shall not start, pause, or shift focus sessions automatically. The plan shall reset on a new day.
- **W-12** Users shall be able to view saved daily, project, and review notes in the dashboard and see 7- or 30-day progress statistics. The terminal shall offer `status`, `wrap`, and weekly or monthly `reflect` workflows.
- **W-13** Browser timer and Daily Alarm alerts shall be opt-in and shall state that an open page is needed for in-page reminders and browser permission is needed for notification banners. The optional macOS daemon shall send native reminders when installed and enabled.

## Interfaces and boundaries

- **W-14** `wyndle ui` shall serve the dashboard on loopback by default, with configurable port and browser launch. Opening the dashboard or saved notes shall not start or reset a day.
- **W-15** The Wyndle VS Code extension shall start or attach to the local server, show the shared dashboard in a sidebar, offer browser opening and reconnect controls, and display current focus or break status. It shall require the Python command and target local desktop VS Code.
- **W-16** Local MCP tools, when the optional extra is installed, shall use the running dashboard API for supported task and note actions. They shall not maintain a second task database.
- **W-17** A task's text identifies its CLI timer state within the day. User instructions shall call for distinct names; advanced renaming shall remain possible by editing the Markdown note.

## Acceptance checks

1. From a fresh config, start a day in the dashboard, add and focus a task, refresh, pause, wrap, and confirm the daily and task Markdown notes contain the same work with no break time counted as focus.
2. Read the same day through `wyndle status` and the VS Code sidebar; both shall reflect the dashboard's current tasks and timing.
3. Open saved notes and stats before starting a day; this shall not create a new daily session.
4. Save and reopen a Daily Alarm plan; reminders shall not change the active focus session without a user action.
