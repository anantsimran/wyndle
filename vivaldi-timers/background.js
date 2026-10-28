"use strict";

importScripts("countdown.js");
const { Countdown, MINUTE, validMinutes, formatTime } = globalThis.FullFocusCountdown;
const KEY = "fullFocus.browserTimers.v1";
const IDS = ["main", "focus"];
const LABELS = { main: "Timer", focus: "Full focus" };
const HEARTBEAT = "badge-refresh";
let timers;
let queue = Promise.resolve();

// Serialize messages and alarms so a pause cannot race with a completion alarm.
function enqueue(task) {
  const result = queue.then(task);
  queue = result.catch((error) => console.error("Full Focus Timers:", error));
  return result;
}

async function load() {
  if (timers) return;
  const saved = (await chrome.storage.local.get(KEY))[KEY] || {};
  const minutes = saved.main?.durationMs / MINUTE;
  timers = {
    main: new Countdown((validMinutes(minutes) ? minutes : 25) * MINUTE, saved.main),
    focus: new Countdown(5 * MINUTE, saved.focus),
  };
}

function snapshot() {
  return { main: timers.main.snapshot(), focus: timers.focus.snapshot() };
}

async function save() {
  await chrome.storage.local.set({ [KEY]: snapshot() });
}

function notificationId(id) {
  return `full-focus-${id}`;
}

async function updateBadge() {
  const now = Date.now();
  const running = IDS.filter((id) => timers[id].status === "running");
  const finished = IDS.some((id) => timers[id].status === "finished");
  const next = running.length
    ? Math.min(...running.map((id) => timers[id].remaining(now))) : 0;
  const minutes = Math.ceil(next / MINUTE);
  const badge = finished ? "!" : running.length
    ? minutes > 99 ? `${Math.ceil(minutes / 60)}h` : `${minutes}m` : "";
  await chrome.action.setBadgeText({ text: badge });
  await chrome.action.setBadgeBackgroundColor({ color: finished ? "#aa4a3d" : "#415e55" });
  const details = IDS.map((id) => {
    const timer = timers[id];
    return `${LABELS[id]} ${formatTime(timer.remaining(now))} · ${timer.status}`;
  });
  await chrome.action.setTitle({ title: details.join("\n") });
}

async function schedule() {
  for (const id of IDS) {
    await chrome.alarms.clear(id);
    if (timers[id].status === "running") {
      await chrome.alarms.create(id, { when: timers[id].deadline });
    }
  }
  await chrome.alarms.clear(HEARTBEAT);
  if (IDS.some((id) => timers[id].status === "running")) {
    await chrome.alarms.create(HEARTBEAT, { periodInMinutes: 0.5 });
  }
  await updateBadge();
}

async function finishExpired() {
  const finished = IDS.filter((id) => timers[id].tick(Date.now()));
  if (!finished.length) return false;
  await save();
  await schedule();
  for (const id of finished) {
    try {
      await chrome.notifications.create(notificationId(id), {
        type: "basic",
        iconUrl: "icon.png",
        title: id === "focus" ? "Full focus complete" : "Timer complete",
        message: id === "focus" ? "Five minutes done. Take a breath." : "Time is up.",
        buttons: [{ title: "Restart" }],
      });
    } catch (error) {
      console.warn("Full Focus Timers notification:", error);
    }
  }
  return true;
}

async function handle(message) {
  await load();
  if (!await finishExpired()) await updateBadge();
  const id = message?.id;
  if (message?.type === "get") return snapshot();
  if (!IDS.includes(id)) throw new Error("Unknown timer.");
  const timer = timers[id];
  if (message.type === "toggle" && message.expectedStatus !== undefined
      && message.expectedStatus !== timer.status) return snapshot();
  if (message.type === "toggle") {
    if (timer.status === "running") timer.pause(Date.now());
    else if (id === "main" && timer.status !== "paused" && message.minutes !== undefined) {
      if (!validMinutes(message.minutes)) throw new Error("Enter 1–1440 whole minutes.");
      timers.main = new Countdown(message.minutes * MINUTE);
      timers.main.start(Date.now());
    } else timer.start(Date.now());
  } else if (message.type === "setDuration" && id === "main") {
    if (!validMinutes(message.minutes)) throw new Error("Enter 1–1440 whole minutes.");
    timers.main = new Countdown(message.minutes * MINUTE);
    timers.main.start(Date.now());
  } else if (message.type === "reset") {
    timer.reset();
  } else {
    throw new Error("Unknown timer action.");
  }
  await chrome.notifications.clear(notificationId(id));
  await save();
  await schedule();
  return snapshot();
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  enqueue(() => handle(message)).then(
    (state) => sendResponse({ state }),
    (error) => sendResponse({ error: error.message }),
  );
  return true;
});

chrome.alarms.onAlarm.addListener((alarm) => {
  void enqueue(async () => {
    await load();
    if (!await finishExpired()) await updateBadge();
  });
});

chrome.runtime.onStartup.addListener(() => {
  void enqueue(async () => {
    await load();
    if (!await finishExpired()) await schedule();
  });
});

chrome.runtime.onInstalled.addListener(() => {
  void enqueue(async () => {
    await load();
    if (!await finishExpired()) await schedule();
  });
});

chrome.notifications.onButtonClicked.addListener((notification, button) => {
  if (button !== 0) return;
  const id = IDS.find((candidate) => notification === notificationId(candidate));
  if (!id) return;
  void enqueue(async () => {
    await load();
    if (timers[id].status !== "finished") return;
    timers[id].start(Date.now());
    await chrome.notifications.clear(notification);
    await save();
    await schedule();
  });
});
