"use strict";

const vscode = require("vscode");
const { Countdown, MINUTE, validMinutes, formatTime } = require("./countdown");

function activate(context) {
  const saved = context.workspaceState.get("fullFocus.timers.v1", {});
  const minutes = saved.main?.durationMs / MINUTE;
  const timers = {
    main: new Countdown((validMinutes(minutes) ? minutes : 25) * MINUTE, saved.main),
    focus: new Countdown(5 * MINUTE, saved.focus),
  };
  const labels = { main: "Timer", focus: "Full focus" };
  const changes = new vscode.EventEmitter();
  const statusItems = {};
  const command = (name, handler) => context.subscriptions.push(
    vscode.commands.registerCommand(`fullFocus.${name}`, handler),
  );

  function persist() {
    void context.workspaceState.update("fullFocus.timers.v1", {
      main: timers.main.snapshot(), focus: timers.focus.snapshot(),
    });
  }

  function render() {
    changes.fire(undefined);
    for (const id of ["main", "focus"]) {
      const timer = timers[id];
      const remaining = timer.remaining(Date.now());
      const item = statusItems[id];
      const state = { idle: "ready", running: "running", paused: "paused", finished: "time is up" }[timer.status];
      const action = { idle: "start", running: "pause", paused: "resume", finished: "start again" }[timer.status];
      const icon = timer.status === "finished" ? "bell"
        : timer.status === "paused" ? "debug-pause" : id === "main" ? "watch" : "target";
      const suffix = timer.status === "paused" ? " · Paused"
        : timer.status === "finished" ? " · Time is up" : "";
      const time = formatTime(remaining);
      item.text = `$(${icon}) ${labels[id]} ${time}${suffix}`;
      item.tooltip = `${labels[id]}: ${time} remaining (${state}). Click to ${action}.`;
      item.accessibilityInformation = { label: `${labels[id]}, ${time} remaining, ${state}. Click to ${action}.` };
      item.backgroundColor = timer.status === "finished" || (timer.status === "running" && remaining <= MINUTE)
        ? new vscode.ThemeColor("statusBarItem.warningBackground") : undefined;
      item.show();
    }
    void vscode.commands.executeCommand("setContext", "fullFocus.timerRunning", timers.main.status === "running");
    void vscode.commands.executeCommand("setContext", "fullFocus.focusRunning", timers.focus.status === "running");
  }

  function tick() {
    let completed = false;
    for (const id of ["main", "focus"]) {
      if (!timers[id].tick(Date.now())) continue;
      completed = true;
      const message = id === "focus"
        ? "Full focus complete — five minutes done. Take a breath."
        : "Timer complete — time is up.";
      void vscode.window.showInformationMessage(message, "Restart").then((choice) => {
        if (choice !== "Restart") return;
        timers[id].reset();
        timers[id].start(Date.now());
        persist();
        render();
      });
    }
    if (completed) persist();
    render();
  }

  async function selectMinutes() {
    const presets = [5, 15, 25, 45, 60].map((value) => ({
      label: `${value} minutes`, minutes: value,
      description: value * MINUTE === timers.main.durationMs ? "current" : undefined,
    }));
    const choice = await vscode.window.showQuickPick(
      [...presets, { label: "Custom duration…" }],
      { title: "Timer duration", placeHolder: "Choose how long to focus" },
    );
    if (!choice) return undefined;
    if (choice.minutes) return choice.minutes;
    const input = await vscode.window.showInputBox({
      title: "Timer duration", prompt: "Minutes (1–1440)",
      value: String(timers.main.durationMs / MINUTE),
      validateInput: (value) => validMinutes(Number(value))
        ? undefined : "Enter a whole number of minutes from 1 to 1440.",
    });
    return input !== undefined && validMinutes(Number(input)) ? Number(input) : undefined;
  }

  async function toggle(id) {
    tick();
    const timer = timers[id];
    if (timer.status === "running") {
      timer.pause(Date.now());
    } else if (id === "main" && timer.status !== "paused") {
      const duration = await selectMinutes();
      if (duration === undefined) return;
      // A second click while the picker is open must not replace an active timer.
      if (timers.main !== timer || timer.status === "running") return;
      timers.main = new Countdown(duration * MINUTE);
      timers.main.start(Date.now());
    } else {
      timer.start(Date.now());
    }
    persist();
    render();
  }

  function pause(id) {
    tick();
    timers[id].pause(Date.now());
    persist();
    render();
  }

  function reset(id) {
    timers[id].reset();
    persist();
    render();
  }

  const provider = {
    onDidChangeCodeLenses: changes.event,
    provideCodeLenses() {
      const range = new vscode.Range(0, 0, 0, 0);
      return ["main", "focus"].flatMap((id) => {
        const timer = timers[id];
        const action = { idle: "Start", running: "Pause", paused: "Resume", finished: "Start again" }[timer.status];
        const time = formatTime(timer.remaining(Date.now()));
        const complete = timer.status === "finished" ? " · Time is up" : "";
        return [
          new vscode.CodeLens(range, {
            command: id === "main" ? "fullFocus.toggleTimer" : "fullFocus.toggleFocus",
            title: `${labels[id]} ${time}${complete} · ${action}`,
            tooltip: `${action} ${labels[id]}${id === "focus" ? " (5 minutes)" : ""}`,
          }),
          new vscode.CodeLens(range, {
            command: id === "main" ? "fullFocus.resetTimer" : "fullFocus.resetFocus",
            title: id === "main" ? "Reset timer" : "Reset focus",
            tooltip: `Reset ${labels[id]} to its full duration`,
          }),
        ];
      });
    },
  };
  context.subscriptions.push(
    changes,
    vscode.languages.registerCodeLensProvider("*", provider),
  );
  for (const id of ["main", "focus"]) {
    const item = vscode.window.createStatusBarItem(
      `fullFocus.${id}`, vscode.StatusBarAlignment.Left, id === "main" ? 1000 : 999,
    );
    item.name = labels[id];
    item.command = id === "main" ? "fullFocus.toggleTimer" : "fullFocus.toggleFocus";
    statusItems[id] = item;
    context.subscriptions.push(item);
  }

  command("toggleTimer", () => toggle("main"));
  command("pauseTimer", () => pause("main"));
  command("toggleFocus", () => toggle("focus"));
  command("pauseFocus", () => pause("focus"));
  command("resetTimer", () => reset("main"));
  command("resetFocus", () => reset("focus"));
  command("showTimers", async () => {
    const editor = vscode.window.activeTextEditor ?? await vscode.window.showTextDocument(
      await vscode.workspace.openTextDocument({ language: "plaintext" }),
    );
    editor.revealRange(new vscode.Range(0, 0, 0, 0), vscode.TextEditorRevealType.AtTop);
  });
  command("chooseDuration", async () => {
    const duration = await selectMinutes();
    if (duration === undefined) return;
    // Choosing a new duration deliberately starts a fresh timer.
    timers.main = new Countdown(duration * MINUTE);
    timers.main.start(Date.now());
    persist();
    render();
  });

  tick();
  const interval = setInterval(tick, 1000);
  context.subscriptions.push({ dispose: () => clearInterval(interval) });
}

module.exports = { activate };
