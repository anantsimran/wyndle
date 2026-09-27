# How to use Wyndle

One small task. One focus block. Then the next step.

## Open your space

Run `wyndle ui` to open the dashboard in your browser. From a source checkout,
use `uv run wyndle ui`. In VS Code, open the Wyndle activity-bar icon.
Both interfaces share your tasks, notes, and timers.

Use **How to use** in the top bar whenever you need this guide. The terminal
version is `wyndle help --guide`. For command options, use `wyndle --help`
or a command’s own help, such as `wyndle ui --help`.

## Start your day

Click **Start my day**. If you have unfinished work from a previous day,
leave **Bring unfinished work forward** checked to carry it over.
Your configured daily chores appear automatically.

## Add one small task

Type a concrete next step in **What’s one small step?**, then press **Enter**
or click **Add to today**. For example: “Read the A2 ticket and write three notes.”

Open **High-level task & estimate** to choose where the step belongs and its
planned minutes:

- **High-level task** groups related subtasks. The initial one is **Today**.
- **Minutes** estimates the whole task, rather than one focus block.
- Choose **5, 10, 15, 30, 45, or 60 minutes** with one click.
- The initial estimate is **15 minutes**. You can still type a custom whole
  number from **0 to 480**; **0** means no estimate.
- Your last estimate stays selected while you add more tasks in the same page.

Use a distinct name for each task today. To rename or reorder an existing task,
edit its daily Markdown note in your preferred editor.

## High-level tasks and subtasks

Work is organized in two levels: a **high-level task** (such as “Ship the A2
ticket”) holds the **subtasks** you actually focus on.

- Click **+ High-level task** to create one. It appears in your list right away,
  even before it has any subtasks.
- Click **+** beside a high-level task’s name to add a subtask to it.
- Click **✓** beside its name to complete it and all of its subtasks at once.

## Delete a task

Click **×** on a subtask, or **×** beside a high-level task’s name, then confirm
with **Delete**. **Keep it** cancels. Deleting removes the task and its notes
from today’s plan, so it will not carry into tomorrow. Focused time and saved
history are kept. An active task pauses first.

## Give one thing your attention

Choose **5, 10, 15, 30, 45, or 60 minutes** on the focus card. Then click a task’s
**▶** button, or **Take the next step** to focus on the suggested task.

The focus block and task estimate are independent. A 60-minute task can start
with a 5-minute block. Choosing a new duration during a block applies to your
next block; it does not reset the running timer.

Click **Pause focus** or the active task’s **Ⅱ** button to stop counting time.
Starting another task pauses the previous one automatically. To resume, click
its **▶** button again; accumulated time is preserved.

When a block ends, Wyndle shows a check-in. Time continues into overtime until
you pause, complete the task, switch tasks, take a break, or wrap the day.
Refreshing or closing the page does not pause focus. Pause before stepping away.

## Take a breath

Click **Take a 5 min break**. This pauses focus and starts a separate break timer;
break time never counts toward focused time.

Click **Back to the journey** to resume your last unfinished task with the
selected focus duration, or **Pause** to end the break without starting work.

## Keep notes and finish tasks

- Click the **+** beside a task to save a short note. Expand its note count to read it.
- Click the circle beside a task to mark it complete. An active task pauses first.
- Open **Completed** to review what you finished.

At the bottom, **time given to focus** shows today’s tracked time,
**small steps finished** shows completed versus total tasks, and
**estimated work left** subtracts tracked time from unfinished task estimates.

## Leave tomorrow an easy start

Click **Wrap up**. Add tomorrow’s first small step and an optional reflection,
then choose **Finish my day**.

Wyndle stops the active timer, saves a shutdown summary, and syncs your work
to persistent task notes. Today is then closed. On the next day, start a fresh
day and carry unfinished work forward if you want to.

## Keyboard shortcuts

- **Enter** in the quick-add field adds a task.
- **N**, while outside a form or button, focuses quick-add.
- **Tab** moves between controls; **Enter** or **Space** activates a focused button.
- **Escape** closes a dialog, including this guide.

## Your files and privacy

Your work stays on this computer. Expand **Your notes** in the footer to find
the notes folder. Daily notes are in `daily/YYYY-MM-DD.md`; persistent project
notes are in `tasks/`. Any Markdown editor can open them.

The browser and VS Code use the same local server. Keep the server running
while using them. If VS Code started it, closing the extension stops that
server. A server started separately with `wyndle ui` keeps running until Ctrl+C.
Stopping the server does not erase the active timer; pause focus first.

## If something feels stuck

- **Cannot reach Wyndle:** restart `wyndle ui`, then refresh. In VS Code, use the
  reconnect button and check **Settings → Wyndle → Executable**.
- **Port already in use:** open the existing dashboard at `http://127.0.0.1:8765`
  or run `wyndle ui --port 8766`. Match the extension’s port setting if using VS Code.
- **Task changed:** refresh to load the latest Markdown before trying again.
- **Too much to start:** choose a 5-minute block and one smaller step. Rest counts, too.

## Terminal companion

Use `wyndle --help` for the current command list. Use `wyndle help` for the
longer terminal workflow reference, or `wyndle help --guide` for this guide.
Examples include `wyndle status`, `wyndle morning`, and `wyndle wrap`.
The command reference below in the dashboard is generated from the same CLI.
