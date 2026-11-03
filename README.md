# Wyndle

Wyndle helps you choose one small task, focus on it, take a break, and leave tomorrow an easy start. The dashboard, terminal commands, and VS Code companion share local Markdown notes and timer state. No account or cloud service is needed.

For a full walkthrough, see the [how-to guide](src/wyndle/web/HOW_TO_USE.md).

## Install and run

You need Python 3.10 or newer and [uv](https://docs.astral.sh/uv/). Wyndle is not published on PyPI. Install the command from GitHub:

```sh
uv tool install git+https://github.com/anantsimran/wyndle.git
wyndle ui
```

To run from a checkout instead:

```sh
git clone https://github.com/anantsimran/wyndle.git
cd wyndle
uv sync
uv run wyndle ui
```

The dashboard opens at `http://127.0.0.1:8765`. If it does not open automatically, visit that address. Use `wyndle ui --no-browser` to serve without opening a tab or `wyndle ui --port 8766` to change ports. Prefix commands with `uv run` when working from a checkout. Stop the server with Ctrl+C.

On first use, Wyndle creates `~/.wyndle/config.yaml`. Its `notes_dir` defaults to `~/Documents/Wyndle`; change that key if you keep notes elsewhere. Daily, project, and review notes are plain Markdown in `daily/`, `tasks/`, and `weekly/` under that folder. Active timer state lives in `~/.wyndle/state/`.

## Use the dashboard

1. Choose any unfinished high-level tasks to carry forward, then click **Start my day**. Your configured daily chores are added automatically.
2. Add a concrete next step, optionally choosing a high-level task, estimate, and priority. Use a distinct task name within the day.
3. Choose a focus duration and click **▶** on a task. Pause, switch tasks, or take a break as needed. Focus time survives a page refresh or server restart; pause it when you stop working.
4. Use **Daily alarm** to arrange work, buffer, and break blocks. Its schedule reminds you when blocks change; it does not start or pause tracking for you.
5. Click **Wrap up** to save today's summary and tomorrow's first step. Use **Notes** and **Stats** to review saved work, including before starting a day.

The dashboard can show Markdown notes; edit the files in your preferred Markdown editor. Use **How to use** in the top bar for the complete guide, including task notes, browser alerts, phone access, and shortcuts.

## Use the terminal

The CLI works with the same notes and state:

```sh
wyndle morning          # start a day and carry work forward
wyndle start            # choose a task and start a focus block
wyndle status           # see progress and remaining work
wyndle break            # pause focus and take a break
wyndle wrap             # finish the day and sync task notes
```

Run `wyndle --help` for every command, or `wyndle help --guide` for the shared how-to guide. On macOS, `wyndle daemon install` enables native background reminders; check delivery with `wyndle daemon test`.

## Use Wyndle in VS Code

The Wyndle sidebar uses the same local dashboard and requires the Python package above. With Node.js 20 or newer and npm, build its VSIX from a checkout:

```sh
cd vscode
npm run package
code --install-extension wyndle-0.1.0.vsix --force
```

If `code` is unavailable, choose **Extensions: Install from VSIX…** in VS Code. Set **Wyndle: Executable** to the installed `wyndle` command (for a checkout, the full path to `.venv/bin/wyndle`, or `.venv\Scripts\wyndle.exe` on Windows). Open the **Wyndle** activity-bar view. It starts or reuses the local server; **Wyndle: Open in Browser** opens the full dashboard. If the view cannot connect, check the executable and port settings, then use **Reconnect Dashboard**. This extension targets local desktop VS Code.

## Install the standalone timers

**Full Focus Timers** is a separate VS Code extension. It does not need Wyndle or its server. Build and install it from the repository root:

```sh
python3 vscode-timers/package.py
code --install-extension vscode-timers/dist/full-focus-timers-0.1.2.vsix --force
```

In VS Code, click **Timer** or **Full focus** in the status bar. Timer offers 5, 15, 25, 45, and 60 minute presets and a custom duration. Full focus starts at five minutes. Both have controls above the first line of a text editor when **Editor: Code Lens** is enabled. The timers save state per workspace and continue across window reloads. See the [timer instructions](vscode-timers/README.md) for all controls. Building needs Python 3; running the VSIX needs VS Code 1.85+.

There is also a separate [Chrome and Vivaldi toolbar timer](vivaldi-timers/README.md). Load `vivaldi-timers/` as an unpacked extension in either browser. Its saved countdowns are independent of VS Code and Wyndle.

## Try Reading Desk (in progress)

Reading Desk is another separate VS Code extension under development. It adds
highlights, comments, and revisit marks to Markdown and Python files without
editing those files. Build its VSIX from the repository root:

```sh
python3 vscode-reader/package.py
code --install-extension vscode-reader/dist/reading-desk-0.1.2.vsix --force
```

Open an `.md` or `.py` file and run **Reading Desk: Open Reading Desk**. Use
the reading-pane toolbar or editor context menu to mark a passage; the Reading Desk
sidebar lists and saves marks in `.reading-desk/reviews.json`. See the
[Reading Desk instructions](vscode-reader/README.md) and its
[draft requirements](vscode-reader/REQUIREMENTS.md). It is not needed to use
Wyndle or the timers.

## More information

- [How-to guide](src/wyndle/web/HOW_TO_USE.md): complete dashboard, CLI, and extension walkthrough.
- [Wyndle requirements](REQUIREMENTS.md), [VS Code timer requirements](vscode-timers/REQUIREMENTS.md), and [Reading Desk draft requirements](vscode-reader/REQUIREMENTS.md).
- [Development guide](DEVELOPING.md) and [architecture reference](ARCHITECTURE.md).

Wyndle's Stormlight inspiration is unofficial; it is not affiliated with Brandon Sanderson.
