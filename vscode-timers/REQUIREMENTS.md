# Full Focus Timers requirements

## Purpose and scope

Full Focus Timers is a standalone VS Code extension for two independent countdowns. It is installed separately from the Wyndle dashboard and does not record time against Wyndle tasks. Its existing extension identity and saved workspace state must survive updates from this repository.

## Countdown behavior

- **T-01** Timer shall offer 5, 15, 25, 45, and 60 minute presets and a custom whole number of minutes from 1 to 1440. Full focus shall start at five minutes.
- **T-02** Each countdown shall independently support start, pause, resume, reset, and restart after completion. Reset shall restore the full selected duration and leave the countdown ready to start.
- **T-03** A running countdown shall use a saved absolute deadline so elapsed time includes VS Code being closed, a window reload, and computer sleep. A paused countdown shall hold its remaining time.
- **T-04** Reaching zero shall mark only that countdown finished and offer a Restart notification. A completion shall not interrupt the other timer.

## Controls and state

- **T-05** Both live countdowns shall remain visible in the left status bar while editing or scrolling. Clicking one shall start, pause, or resume it. The final minute and finished state shall have a visible warning treatment.
- **T-06** With Editor: Code Lens enabled, both countdowns and their Reset controls shall appear above the first line of text files. Editor toolbar controls and Command Palette commands shall remain available when the top controls are out of view.
- **T-07** Timer state shall persist in VS Code workspace state and survive reloads when the same workspace is reopened. The two timers shall work across file changes without creating task or Markdown records.
- **T-08** The extension ID `anantsimran.full-focus-timers`, command IDs, and workspace-state key shall remain compatible with existing installations.

## Packaging and compatibility

- **T-09** The installed extension shall run on VS Code 1.85 or newer without Wyndle, Python, a web server, or runtime npm packages. Its VSIX shall be buildable with Python 3 and the standard library from `vscode-timers/`.
- **T-10** Installing or updating the Wyndle Python package or dashboard extension shall not install, replace, or reset Full Focus Timers.

## Acceptance checks

1. Start both countdowns, pause one, change files, and confirm only the other continues to decrease while both remain visible in the status bar.
2. Reload VS Code and reopen the same workspace; confirm a running deadline includes time away and a paused countdown retains its remaining time.
3. Let a countdown finish, use Restart, and confirm the other countdown's state is unchanged.
4. Build the VSIX and confirm its manifest keeps the extension identity and includes the countdown implementation, README, and license.
