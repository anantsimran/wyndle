# Full Focus Timers for Chrome and Vivaldi

Two independent countdowns in a Chrome or Vivaldi toolbar popup: a configurable **Timer**
and a five-minute **Full focus** timer. Each has Start, Pause, Resume, and Reset.
Timer offers 5, 15, 25, 45, and 60 minute presets, plus a custom whole number
from 1 to 1440. Select a duration before starting, or use **Start with selected
duration** to replace a running or paused Timer.

The toolbar badge shows the nearest running deadline in minutes, or `!` when
either timer finishes. The popup shows both countdowns to the second. Completion
shows a browser notification with a **Restart** button. Timers count real elapsed
time while the popup is closed or the computer sleeps. Pause to stop the clock.
Saved state survives browser restarts. A notification may arrive late if the browser
is closed or background alarms are delayed; the saved deadline still
determines the correct remaining time.

## Install in Chrome

1. Open `chrome://extensions` in Chrome.
2. Turn on **Developer mode** and click **Load unpacked**.
3. Select this `vivaldi-timers/` folder. Use Chrome's Extensions button to pin
   **Full Focus Timers** if you want the badge visible.

## Install in Vivaldi

1. In Vivaldi, open **Vivaldi menu → Tools → Extensions**.
2. Turn on **Developer mode** and click **Load unpacked**.
3. Select this `vivaldi-timers/` folder, then pin **Full Focus Timers** to the
   toolbar if you want the badge visible.

Both browsers load the same folder, despite its Vivaldi name. For a portable
copy, zip the contents of this folder, including `manifest.json` at the archive
root, and extract it before using **Load unpacked**. Reload the extension on the
Extensions page after editing its source.

This is a standalone browser extension. It requires no Wyndle server, Python,
VS Code, account, or access to web pages. Its only permissions are local storage,
alarms, and notifications. Browser timer state is separate from the VS Code
extension and Wyndle task tracking. Chrome and Vivaldi save their timer states
separately.
