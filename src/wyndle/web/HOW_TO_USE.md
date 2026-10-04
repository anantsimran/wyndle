# How to use Wyndle

One small task. One focus block. Then the next step.

## Open your space

Run `wyndle ui` to open the dashboard in your browser. From a source checkout,
use `uv run wyndle ui`. In VS Code, open the Wyndle activity-bar icon.
Both interfaces share your tasks, notes, and timers.

Use **How to use** in the top bar whenever you need this guide. The terminal
version is `wyndle help --guide`. For command options, use `wyndle --help`
or a command’s own help, such as `wyndle ui --help`.

Use **Notes** or **Stats** in the top bar at any time, including before you
start your day. **Notes** lets you read saved daily, task, and review Markdown
files. Choose a file from the list; use **Refresh** after changing files in an
editor. **Stats** shows the last 7 or 30 days of tracked time and completed
steps, with a day-by-day breakdown.

## Start your day

If you have unfinished work from a previous day, open **Bring unfinished work
forward** and choose which high-level tasks to carry into today. All are selected
at first; clear any you want to leave out. Then click **Start my day**. Your
configured daily chores appear automatically.

## Add one small task

Type a concrete next step in **What’s one small step?**, then press **Enter**
or click **Add to today**. For example: “Read the A2 ticket and write three notes.”

Open **Group & planned minutes** to choose where the step belongs and its
planned minutes:

- **High-level task** groups related subtasks. The initial one is **Today**.
  The list includes every high-level task from the last 30 days; picking an
  older one adds it back to today.
- **Minutes** estimates the whole task, rather than one focus block.
- Choose **5, 10, 15, 30, 45, or 60 minutes** with one click.
- The initial estimate is **15 minutes**. You can still type a custom whole
  number from **0 to 480**; **0** means no estimate.
- Your last estimate stays selected while you add more tasks in the same page.

Choose a **Task type** beneath the form: **P0** for non-negotiable work,
**Regular** for the usual list, or **Optional** for work you can leave for
later. A task has one type at a time. The count card beside the timer shows
how many unfinished tasks remain in each type.

Use a distinct name for each task today. To rename a task, edit its daily
Markdown note in your preferred editor.

## High-level tasks and subtasks

Work is organized in two levels: a **high-level task** (such as “Ship the A2
ticket”) holds the **subtasks** you actually focus on.

- Click **+ High-level task** to create one. It appears in your list right away,
  even before it has any subtasks.
- Click **+** beside a high-level task’s name to add a subtask to it.
- Click **✓** beside its name to complete it and all of its subtasks at once.
- Use **↑** and **↓** under a task to move it within its high-level task. Its
  notes move with it, and the order is kept when the project carries forward.
  Use **P0** or **Opt** on a task card to change its type.

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

When a block ends, the timer shows overtime. Time continues until
you pause, complete the task, switch tasks, take a break, or wrap the day.
The timer and live indicator turn red in overtime. Tasks also turn red when
their tracked time exceeds their estimate, including after completion.
Refreshing or closing the page does not pause focus. Pause before stepping away.

Click **Enable timer alerts** if you want quiet browser notifications and
in-page reminders at the end of a focus block, every five minutes of overtime,
and when a break ends. Browser notifications need permission and may be
unavailable on some phones. Keep the dashboard open to receive page alerts.

## Take a breath

Click **Take a 5 min break**. This pauses focus and starts a separate break timer;
break time never counts toward focused time.

Click **Back to the journey** to resume your last unfinished task with the
selected focus duration, or **Pause** to end the break without starting work.

## Plan today's blocks

Open **Daily alarm** in the top bar, or visit `/daily`. Start your day and add
tasks in the dashboard first. On the Daily Alarm page:

1. Set a start time, work mode, work-block length, buffer length, and break
   length. The buffer defaults to five minutes and can be set from 1 to 60
   minutes.
2. Select unfinished tasks and use the arrows to put them in order.
3. Click **Save daily plan** to see today's work, buffer, and break blocks.
   Change the choices and save again, or clear the plan.

Choose one block per task's remaining estimate or fixed work chunks. Tasks
without an estimate use the work-block length. Every block has
its own buffer and break, including the final block; all three phases must fit
before your configured hard stop. The plan resets with the next day.
Scheduled blocks and reminders do not pause or start tracked sessions. Choose
**Start this focus block** to track work or **Start break** to track rest. During
the buffer, click **Pause focus** when you finish working.
Starting late does not move the saved times.
The start time uses the computer running Wyndle; the timeline uses this device's
time zone. If a task changes or disappears, save the plan again.

Click **Enable page alerts** for quiet reminders at block changes while the
Daily Alarm page is open. Turn them on separately on each device. Notification
banners need browser permission; in-page reminders remain available when banners
are blocked. Closing the tab or locking a phone can stop these alerts.

To use the page on a phone, run Wyndle on your computer and open its private
Tailscale Serve HTTPS address on the phone. Add the Tailscale hostname to
`WYNDLE_ALLOWED_HOSTS` before starting `wyndle ui`. Keep the Daily Alarm page
open for page alerts. Wyndle does not set a phone system alarm or deliver
background phone alerts. On the computer, run
`tailscale serve --bg http://127.0.0.1:8765` after starting Wyndle.

## Pomodoro timer

Click **Pomodoro** in the top bar for a classic 25-minute focus timer with
5-minute breaks and a 15-minute break after every fourth round. **Skip** moves
to the next phase; **Reset** returns to round 1. A chime and a message mark
each phase’s end; the next phase waits for you to click **Start**.

The Pomodoro is only a timer. It does not start, pause, or track any task, and
nothing is saved. Closing or refreshing the page resets it. Hide it with **×**;
the top-bar button keeps showing the time while it runs.

## Keep notes and finish tasks

- Click the **+** beside a task, including a completed task, to save a short
  note. Expand its note count to read it.
- Click the circle beside a task to mark it complete. An active task pauses first.
  Click the **✓** of a completed task to mark it not done again.
- Click **✎** to edit planned and tracked minutes or task type. Completed tasks show their
  total tracked time, first focus start, and completion time beneath the title.
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
notes are in `tasks/`, and saved reviews are in `weekly/`. Any Markdown editor
can open them. The **Notes** viewer displays their Markdown as plain text.

The browser and VS Code use the same local server. Keep the server running
while using them. If VS Code started it, closing the extension stops that
server. A server started separately with `wyndle ui` keeps running until Ctrl+C.
Stopping the server does not erase the active timer; pause focus first.

## If something feels stuck

- **Cannot reach Wyndle:** restart `wyndle ui`, then refresh. In VS Code, use the
  reconnect button and check **Settings → Wyndle → Executable**.
- **Port already in use:** open the existing dashboard at `http://127.0.0.1:8765`
  or run `wyndle ui --port 8766`. Match the extension’s port setting if using VS Code.
- **A new page says “Not found”:** restart the running `wyndle ui` process after
  an update. A browser refresh does not reload Python routes, and VS Code may
  reconnect to the older server.
- **Task changed:** refresh to load the latest Markdown before trying again.
- **Too much to start:** choose a 5-minute block and one smaller step. Rest counts, too.

## Terminal companion

Use `wyndle --help` for the current command list. Use `wyndle help` for the
longer terminal workflow reference, or `wyndle help --guide` for this guide.
Examples include `wyndle status`, `wyndle morning`, and `wyndle wrap`.
The command reference below in the dashboard is generated from the same CLI.
