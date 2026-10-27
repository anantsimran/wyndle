# Full Focus Timers

A small, standalone VS Code extension. It works with any file and workspace.

Maintained in Wyndle's `vscode-timers/` directory. It is installed separately from
the Wyndle dashboard extension in `vscode/` and the `wyndle` Python package.
Neither is required to run these timers. See the
[architecture decision](../docs/adr/0001-standalone-vscode-timers.md).

- **Bottom status bar:** both countdowns stay visible on the left as **Timer 24:59**
  and **Full focus 04:59**, updating every second while you work or scroll. Click to
  start, pause, or resume. Paused timers show **Paused**; the last minute and
  completed timers get a highlighted background.
- **Above the first line of every text file:** both live countdowns appear as
  clickable controls: **Timer 25:00 · Start** and **Full focus 05:00 · Start**, each
  with its own Reset button. Click a countdown to start, pause, or resume it.
- **Timer:** choose 5, 15, 25, 45, 60 minutes, or a custom duration when starting.
  **Full focus** starts five minutes immediately.
- **Editor toolbar:** the watch and target buttons control Timer and Full focus
  while you scroll. Click the up arrow to reveal the countdowns at the top. The
  toolbar's **…** menu also offers duration and reset controls.
- **Time is up:** a notification offers Restart. Reset returns a timer to its full
  duration, ready to start again.

The timers run independently. Changing files or scrolling keeps them running.
State is saved per workspace and survives a window reload. Running timers count real
elapsed time, including time when VS Code is closed or the computer is asleep; pause
first if you want to stop the clock. Commands are also available under **Full Focus**
in the Command Palette.

## Install

From the repository root:

```sh
python3 vscode-timers/package.py
code --install-extension vscode-timers/dist/full-focus-timers-0.1.2.vsix --force
```

If `code` is not on your PATH, run **Extensions: Install from VSIX…** in VS Code and
select the generated file. If the buttons do not appear immediately, run
**Developer: Reload Window**. Keep **Editor: Code Lens** enabled in Settings for the
countdown controls above the first line. Narrow editor toolbars may put the buttons
in **…**.

Building the VSIX needs Python 3 and its standard library. Running the installed
extension needs only VS Code 1.85 or newer. Installing or updating Wyndle does not
install or update Full Focus Timers; build and install this VSIX separately.

If you installed Full Focus Timers from `interview-prep`, the command above updates
that same extension. Its ID (`anantsimran.full-focus-timers`), commands, and saved
workspace state are unchanged. Reopen the same workspace to resume its timers.

## Develop

There are no npm dependencies or build steps. Run the clock and extension tests with
Node.js 20 or newer:

```sh
cd vscode-timers
node --test test/*.test.js
```

To try the source without installing, use
`code --extensionDevelopmentPath="$PWD/vscode-timers"` from the repo root.
After changing the source, rebuild the VSIX and reinstall it with `--force`.
