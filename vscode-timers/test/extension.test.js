"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { MINUTE } = require("../countdown");

function harness(saved = {}) {
  const commands = new Map();
  const contexts = new Map();
  const statusItems = new Map();
  const notifications = [];
  const reveals = [];
  const disposable = { dispose() {} };
  let clock = 0;
  let interval;
  let provider;
  let selector;
  let snapshot = saved;
  let pick = { minutes: 25 };
  let input;
  const editor = { revealRange: (range, type) => reveals.push({ range, type }) };
  class Range {
    constructor(startLine, startCharacter, endLine, endCharacter) {
      this.start = { line: startLine, character: startCharacter };
      this.end = { line: endLine, character: endCharacter };
    }
  }
  const api = {
    EventEmitter: class {
      event = () => disposable;
      fire() {}
      dispose() {}
    },
    Range,
    ThemeColor: class { constructor(id) { this.id = id; } },
    StatusBarAlignment: { Left: 1 },
    CodeLens: class { constructor(range, command) { this.range = range; this.command = command; } },
    TextEditorRevealType: { AtTop: 1 },
    languages: {
      registerCodeLensProvider(filter, value) { selector = filter; provider = value; return disposable; },
    },
    commands: {
      registerCommand(id, handler) { commands.set(id, handler); return disposable; },
      async executeCommand(id, key, value) { if (id === "setContext") contexts.set(key, value); },
    },
    window: {
      activeTextEditor: editor,
      createStatusBarItem(id, alignment, priority) {
        const item = { alignment, priority, visible: false, show() { this.visible = true; }, dispose() {} };
        statusItems.set(id, item);
        return item;
      },
      async showTextDocument() { return editor; },
      async showQuickPick() { return pick; },
      async showInputBox() { return input; },
      async showInformationMessage(message) { notifications.push(message); },
    },
    workspace: { async openTextDocument() { return {}; } },
  };
  const context = {
    subscriptions: [],
    workspaceState: {
      get() { return saved; },
      async update(key, value) { snapshot = value; },
    },
  };
  const sandbox = {
    module: { exports: {} },
    require: (id) => id === "vscode" ? api : require("../countdown"),
    Date: { now: () => clock },
    setInterval(fn) { interval = fn; return 1; },
    clearInterval() {},
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../extension.js"), "utf8"), sandbox);
  sandbox.module.exports.activate(context);
  return {
    commands, contexts, notifications, reveals,
    run: (id) => commands.get(`fullFocus.${id}`)(),
    tick(now) { clock = now; interval(); },
    pick(value) { pick = value; },
    input(value) { input = value; },
    closeEditor() { api.window.activeTextEditor = undefined; },
    get snapshot() { return snapshot; },
    get provider() { return provider; },
    get selector() { return selector; },
    lens(id) { return provider.provideCodeLenses().find((lens) => lens.command.command === `fullFocus.${id}`); },
    status(id) { return statusItems.get(`fullFocus.${id}`); },
  };
}

test("live controls appear at the first line in every language", () => {
  const app = harness();
  assert.equal(app.selector, "*");
  const lenses = app.provider.provideCodeLenses();
  assert.equal(lenses.length, 4);
  for (const lens of lenses) {
    assert.equal(lens.range.start.line, 0);
    assert.equal(lens.range.end.line, 0);
  }
  assert.equal(app.lens("toggleTimer").command.title, "Timer 25:00 · Start");
});

test("bottom bar shows live seconds without an editor, paused time, and final-minute highlighting", async () => {
  const app = harness();
  assert.equal(app.status("main").text, "$(watch) Timer 25:00");
  assert.equal(app.status("focus").text, "$(target) Full focus 05:00");
  assert.equal(app.status("focus").visible, true);
  assert.equal(app.status("focus").command, "fullFocus.toggleFocus");
  app.closeEditor();
  await app.run("toggleFocus");
  app.tick(1000);
  assert.equal(app.status("focus").text, "$(target) Full focus 04:59");
  assert.match(app.status("focus").tooltip, /Click to pause/);
  await app.run("pauseFocus");
  app.tick(25_000);
  assert.equal(app.status("focus").text, "$(debug-pause) Full focus 04:59 · Paused");
  await app.run("toggleFocus");
  app.tick(264_000);
  assert.equal(app.status("focus").text, "$(target) Full focus 01:00");
  assert.equal(app.status("focus").backgroundColor.id, "statusBarItem.warningBackground");
  app.tick(324_000);
  assert.equal(app.status("focus").text, "$(bell) Full focus 00:00 · Time is up");
  await app.run("resetFocus");
  assert.equal(app.status("focus").text, "$(target) Full focus 05:00");
  assert.equal(app.status("focus").backgroundColor, undefined);
});

test("top Full focus button starts, pauses, resumes, resets and completes", async () => {
  const app = harness();
  assert.equal(app.lens("toggleFocus").command.title, "Full focus 05:00 · Start");
  await app.run("toggleFocus");
  app.tick(MINUTE);
  assert.equal(app.lens("toggleFocus").command.title, "Full focus 04:00 · Pause");
  assert.equal(app.contexts.get("fullFocus.focusRunning"), true);
  await app.run("pauseFocus");
  app.tick(10 * MINUTE);
  assert.equal(app.lens("toggleFocus").command.title, "Full focus 04:00 · Resume");
  await app.run("toggleFocus");
  app.tick(14 * MINUTE);
  app.tick(15 * MINUTE);
  assert.equal(app.notifications.length, 1);
  assert.equal(app.snapshot.focus.status, "finished");
  await app.run("resetFocus");
  assert.equal(app.lens("toggleFocus").command.title, "Full focus 05:00 · Start");
});

test("duration picker cancellation does not start a timer; a custom timer runs beside Full focus", async () => {
  const app = harness();
  app.pick(undefined);
  await app.run("toggleTimer");
  assert.equal(app.contexts.get("fullFocus.timerRunning"), false);
  app.pick({ label: "Custom duration…" });
  app.input("7");
  await app.run("toggleTimer");
  await app.run("toggleFocus");
  app.tick(5 * MINUTE);
  assert.equal(app.lens("toggleTimer").command.title, "Timer 02:00 · Pause");
  assert.equal(app.lens("toggleFocus").command.title, "Full focus 00:00 · Time is up · Start again");
  assert.equal(app.status("main").text, "$(watch) Timer 02:00");
  assert.equal(app.status("focus").text, "$(bell) Full focus 00:00 · Time is up");
  await app.run("pauseTimer");
  app.tick(20 * MINUTE);
  await app.run("toggleTimer");
  app.tick(22 * MINUTE);
  assert.equal(app.notifications.length, 2);
});

test("reload restores deadlines and does not repeat an acknowledged completion", async () => {
  const initial = harness();
  await initial.run("toggleFocus");
  const reloaded = harness(initial.snapshot);
  reloaded.tick(5 * MINUTE);
  assert.equal(reloaded.notifications.length, 1);
  const finished = harness(reloaded.snapshot);
  finished.tick(10 * MINUTE);
  assert.equal(finished.notifications.length, 0);
});

test("every command contributed to VS Code has a registered handler", () => {
  const app = harness();
  const manifest = require("../package.json");
  for (const command of manifest.contributes.commands) {
    assert.equal(app.commands.has(command.command), true, command.command);
  }
  assert.equal(manifest.contributes.views, undefined);
  assert.equal(manifest.contributes.viewsContainers, undefined);
  assert.deepEqual(Object.keys(manifest.contributes.menus), ["editor/title"]);
});

test("toolbar can reveal the timers at the top, including without an open file", async () => {
  const app = harness();
  await app.run("showTimers");
  assert.equal(app.reveals[0].range.start.line, 0);
  assert.equal(app.reveals[0].type, 1);
  app.closeEditor();
  await app.run("showTimers");
  assert.equal(app.reveals.length, 2);
});
