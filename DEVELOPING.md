# Modifying Wyndle

Start with [How to run](README.md#how-to-run) for installation, the web dashboard,
and VS Code. This guide explains where changes belong. [ARCHITECTURE.md](ARCHITECTURE.md)
has deeper details about the Markdown model and persistent note format.

## The whole system

Wyndle has three interfaces over the same local files:

```text
Terminal → cli.py → commands → library functions ──────────┐
                                                         │
Browser → web/ → HTTP server → dashboard workflow ─────────┼→ Markdown + state files
                                                         │
VS Code → local server manager → same browser dashboard ──┘
```

The browser owns presentation, not the task database. Python parses and changes
Markdown, tracks elapsed time, and synchronizes daily work to persistent task
notes. VS Code embeds that same web app rather than maintaining another UI.

## Repository map

| Path | What it does |
|---|---|
| `pyproject.toml` | Python dependencies, CLI entry point, packaged assets, lint/test configuration |
| `src/wyndle/__init__.py` | Package version; packaging reads this value |
| `src/wyndle/cli.py` | Click command registration and shared CLI setup |
| `src/wyndle/default_config.yaml` | Default settings copied into a new user’s configuration |
| `src/wyndle/commands/` | Terminal workflows plus the local web server |
| `src/wyndle/lib/` | Models, persistence, parsing, timers, configuration, and dashboard workflow |
| `src/wyndle/web/` | Browser app shipped inside the Python package |
| `vscode/` | VS Code integration; no task persistence or copied browser assets |
| `.vscode/launch.json` | F5 extension development host configuration |
| `tests/` | Isolated Python regression tests and optional browser smoke script |
| `.pre-commit-config.yaml` | Formatting hygiene, Ruff, and pytest hooks |
| `README.md` | User instructions and command reference |
| `ARCHITECTURE.md` | Detailed file-format and library architecture reference |

## Commands

`cli.py` registers commands and imports their implementation lazily. Most terminal
commands call `_setup()`, which initializes configuration/directories and runs
forgotten-day synchronization. The web command has its own startup: simply
opening the dashboard must not start or reset a day.

| Module in `commands/` | Responsibility |
|---|---|
| `morning.py` | Initialize the day, carry unfinished work forward, seed chores, add tasks |
| `start.py` | Pick a task/subtask and start or switch terminal focus |
| `restart.py` | Resume the last subtask with an optional duration |
| `next_cmd.py` | Complete/pause the current subtask and choose another |
| `break_cmd.py` | Separate break timer and offer to resume focus |
| `stuck.py` | Interactive prompts for getting unstuck |
| `status.py` | Terminal progress, estimates, and backlog summary |
| `wrap.py` | Shutdown notes, totals, synchronization, and forgotten-day auto-wrap |
| `reflect.py` | Weekly/monthly review of daily notes |
| `daemon.py` | Install/manage the macOS launchd notification service |
| `ui.py` | Serve packaged assets and the local dashboard API |

Keep interactive prompts in terminal command code. Dashboard actions must return
data without asking a terminal question. Today, `lib/dashboard.py` reuses several
morning/wrap helpers. If more clients need those helpers, extract common behavior
into a library module and leave presentation in commands.

## Core libraries

| Module in `lib/` | Responsibility and change guidance |
|---|---|
| `models.py` | Dataclasses such as `Task`, `SubTask`, `TaskNote`, and `WorkSummary`. Put shared data structures here. |
| `config.py` | Hydrate YAML into dataclasses and derive data paths. Add defaults here and in `default_config.yaml`. |
| `state.py` | File-backed keys, day boundaries, per-subtask elapsed seconds, active timer flags. Changes affect every interface. |
| `time_utils.py` | Clock, date/time formatting, and duration math. Use this clock so tests can control time. |
| `markdown_dom.py` | Parse heading blocks, frontmatter, checkboxes, notes, and metadata. Preserve unrelated content when writing. |
| `daily_notes.py` | Read/write daily Markdown notes. |
| `task_notes.py` | Persistent task history, note merging, status tags, and carryover generation. |
| `timer.py` | Blocking terminal countdown and overflow. The browser does not run this blocking loop. |
| `display.py` | Rich terminal rendering and prompts; keep browser markup elsewhere. |
| `notifier.py` | macOS notifications and scheduling checks. Browser check-ins are separate. |
| `dashboard.py` | Non-interactive snapshot/actions for start-day, add, focus, pause, complete, notes, breaks, wrap. |

## Data and lifecycle

Configuration is at `~/.wyndle/config.yaml`. Individual state keys live under
`~/.wyndle/state/`. The configured notes folder contains:

```text
daily/YYYY-MM-DD.md    today's checkboxes, notes, log, and shutdown summary
tasks/<slug>.md       per-task history across days
weekly/              review output
```

Important rules:

- Daily Markdown is the editing surface. Do not add a browser-only copy of tasks.
- Store seconds in timers; round to minutes only when reporting totals. Sum
  seconds before rounding so short blocks across tasks are not lost.
- Break time must never flow into subtask elapsed time.
- `today_ui_*` keys persist the graphical timer’s kind, start, deadline, duration,
  and active task. Pausing through the CLI invalidates those graphical keys.
- A focus deadline signals a check-in, not completion. Elapsed time continues
  until pause/completion; reloading a page must not reset it.
- `snapshot()` is read-only. Crossing midnight makes it show a fresh-day state;
  explicit start-day performs carryover and state reset.
- Wrap sync adds daily minutes into task history. Repeated wrap must be a no-op.
- Chores live in Task Details, outside the High Level Tasks list. Enumerate
  Task Details when an operation promises to include all subtasks.
- Task and project text is untrusted content. Use DOM `textContent`, never raw
  HTML interpolation, and reject newlines in single-line API fields.

Current limitations: subtask timers are keyed by normalized text, not project.
The dashboard therefore rejects duplicate names across today’s tasks. Renames,
reordering, and advanced backlog editing still happen in Markdown. Terminal
commands and the dashboard should not be used to mutate the same task at the
same instant: HTTP actions serialize within one server, but the CLI does not
participate in a cross-process transaction. Changes to notes-folder configuration
require restarting the server.

## Changing the visual design

All assets are plain HTML, CSS, and native JavaScript modules. No build step,
remote fonts, CDN, or framework is required.

| Asset under `web/` | Owns |
|---|---|
| `theme.css` | Semantic colors, fonts, corner radii, shadow, and dark-mode palette |
| `components.css` | Buttons, fields, cards, task rows, dialogs, notices |
| `style.css` | Page/grid layout, responsive sizing, focus ring, header/footer |
| `index.html` | Semantic page structure and static copy |
| `api.js` | Fetch/JSON transport and shared duration formatting |
| `app.js` | Application state, polling, action orchestration, component composition |
| `components/tasks.js` | Task grouping, completion/focus controls, saved notes |
| `components/focus.js` | Duration choice, live countdown, focus/break controls, check-ins |
| `components/dialogs.js` | Wrap and add-note forms |
| `assets/` | Locally bundled character illustrations and their generation prompts |

For a different aesthetic, change semantic tokens first; avoid hardcoding a new
palette in each component. For a different theme or lore, edit presentation copy
without changing action names or file formats. Dalinar’s resolve informs the
next-step language; Kaladin’s care informs rest and encouragement. Neither is
used to shame missed work or force a streak.

Preserve visible keyboard focus, reduced-motion support, readable contrast, and
the 340px-wide layout. Keep core actions one click; keep optional fields behind
progressive disclosure. Quick-add submits on Enter and `N` focuses it.

## Adding a feature

1. Define its persistence behavior: existing Markdown, task history, or transient
   day state. Add a model/helper if multiple interfaces need it.
2. Add a validated action to `dashboard.dispatch()` and expose any resulting data
   in `snapshot()`. Validate everything before the first write.
3. Add or extend a component and wire it from `app.js`. Submit via `api.request()`.
   Treat Python’s response as authoritative; avoid another client-side task store.
4. If you add a static file, register its URL in `commands/ui.py`’s `ASSETS` and
   ensure `pyproject.toml` includes its file pattern in package data.
5. Add behavior tests for persistence, invalid inputs, and repeated requests.
   Test a full lifecycle when the feature affects timers or day boundaries.
6. Update the user instructions and run the checks below.

The HTTP contract is `GET /api/status` and `POST /api/action` with
`{"action": "focus", "data": {"id": "...", "minutes": 15}}`. POST requires
`Content-Type: application/json` and `X-Wyndle-Client: dashboard`. Successful
actions return a complete snapshot; failures return an `error` string.
The server binds only to loopback, checks Host/Origin, and serves an explicit
asset allowlist. Do not turn this local server into an internet-facing deployment
without designing authentication, hosting, and concurrent storage first.

## Changing VS Code integration

- `vscode/package.json`: commands, view registration, settings, metadata.
- `vscode/server.js`: probe a compatible local server or spawn the Python CLI
  without a shell; manage only the process this extension started.
- `vscode/extension.js`: webview container, reconnect/open-browser commands,
  status bar, and disposal. The iframe loads the same local app.
- `vscode/media/wyndle.svg`: activity-bar icon.
- `vscode/test/server.test.js`: server detection and startup safety checks.

Use F5 from the repository root to test in an Extension Development Host. Set
`wyndle.executable` to the full executable path if VS Code cannot resolve PATH.
The extension currently targets local desktop VS Code. Keep secrets and runtime
state out of extension settings and the source checkout.

## Verification and packaging

```bash
uv sync --extra dev
uv run pytest -q
uv run ruff check src tests
uv run pre-commit run --all-files
cd vscode
npm test
npm run package
```

`tests/conftest.py` supplies an isolated home/notes folder, controllable clock, and
scripted prompt answers. HTTP tests use temporary notes and ephemeral loopback
ports. They need permission to bind a local socket.

The optional `tests/browser/smoke.py` needs Playwright and installed Google Chrome.
It checks start-day → quick-add → focus → reload → pause → break → note → complete
→ wrap, using temporary files, and saves desktop/sidebar screenshots in `/tmp`.

To check Python distribution assets:

```bash
uv build
```

Install the built wheel into a clean environment and check `wyndle ui`, especially
after adding asset directories. Build the VSIX with `npm run package` in `vscode/`;
the Python backend is installed separately. Do not commit generated wheels,
VSIX files, virtual environments, or real user notes.
