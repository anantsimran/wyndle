# ADR 0001: Keep Full Focus Timers as a separately installed extension

Status: Accepted

Date: 2026-10-27

## Context

Full Focus Timers previously lived at `interview-prep/tools/vscode-timers/`.
It provides two independent countdowns in VS Code, including a configurable
timer and an immediate five-minute Full focus timer. Wyndle already owns related
productivity tools, including a Python CLI and a VS Code extension that embeds
its browser dashboard.

The relocation requirements confirmed in the migration conversation are:

- Move the complete timer module into Wyndle and follow its repository guidance.
- Preserve timer behavior, especially the bottom status bar and top controls,
  even where Wyndle has similar functionality.
- Keep Wyndle installation and timer installation separate.
- Record the architectural decision.

This record uses those requirements, the existing timer README and tests, and
the source implementation in `interview-prep` commit `8a1ccda`. Earlier chat
transcripts are not part of this record's evidence.

## Decision

Move the extension to `vscode-timers/` at the Wyndle repository root, alongside
the dashboard extension in `vscode/`. Keep its own manifest, activation code,
countdown model, tests, MIT license, README, and standard-library VSIX packager.
Do not merge it into the dashboard extension or the Python package.

Preserve the runtime JavaScript and manifest byte for byte during relocation.
Documentation paths change, and the packager's XML attributes are wrapped to
meet Wyndle's Python line-length rule without changing manifest semantics.

## Behavior guarantees

- **Bottom bar:** both timers remain visible on the left, update every second,
  and toggle start/pause/resume on click. Paused state, accessibility labels,
  and final-minute/completion highlighting remain available without an editor.
- **Top controls:** CodeLens above the first line of every text file continues
  to show both countdowns, their current actions, and individual Reset commands.
- **Editor toolbar:** watch and target controls keep their running-state actions;
  the up arrow reveals the controls at the top, opening a text document when
  needed. Duration and reset commands remain in the overflow menu.
- **Countdowns:** preset and custom whole-minute durations, cancellation,
  immediate five-minute Full focus, independent timers, pause/resume, reset,
  completion notifications, and Restart keep their existing behavior.
- **Persistence:** keep extension ID `anantsimran.full-focus-timers`, version
  `0.1.2`, `fullFocus.*` commands, and `fullFocus.timers.v1` workspace state.
  Updating the same extension and reopening the same workspace retains saved
  deadlines and paused time. Running timers include elapsed time during sleep
  or while VS Code is closed; acknowledged completions are not repeated.
- **Startup:** keep startup activation, workspace capabilities, and lack of
  backend dependencies. No Wyndle server or task selection is required.

## Installation and ownership

Build and install the timer from the Wyndle repository root:

```sh
python3 vscode-timers/package.py
code --install-extension vscode-timers/dist/full-focus-timers-0.1.2.vsix --force
```

Only building needs Python 3. The installed extension needs VS Code 1.85+ and
has no runtime npm or Python dependencies. Node.js 20+ runs its development tests.
The packager includes only timer assets; generated VSIX files stay ignored.

Wyndle's Python package continues to install separately through `uv`. Its
dashboard extension continues to package and install from `vscode/` as
`anantsimran.wyndle`. Installing, updating, or removing one extension does not
install, update, or remove the other. The standalone timers do not read task
Markdown or contribute to Wyndle's tracked focus totals.

## Alternatives considered

- **Merge into the dashboard extension:** introduces a different installation
  identity and state owner, and couples standalone controls to dashboard
  activation and capabilities. This does not satisfy separate installation.
- **Replace with dashboard timers:** loses the existing editor controls and
  independent countdown behavior. Similar functionality does not justify
  changing the timer's interaction or persistence model.
- **Keep the source in interview-prep:** preserves behavior but does not meet
  the requested ownership change.

## Consequences and verification

Wyndle maintains two VS Code extensions, each with its own manifest, tests,
packaging, and install instructions. The separate boundary preserves the timer
experience and allows either extension to be used on its own.

Run `node --test vscode-timers/test/*.test.js` to cover countdown lifecycle,
reloads, the bottom bar, CodeLens, toolbar actions, and command registration.
Compare runtime and manifest hashes against the source before removing it, and
inspect the built VSIX to confirm it includes every timer runtime asset and no
dashboard backend. See the [timer README](../../vscode-timers/README.md) and
[development guide](../../DEVELOPING.md#changing-full-focus-timers).
