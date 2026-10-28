"use strict";

const $ = (id) => document.getElementById(id);
const LABEL = { idle: "Ready", running: "Running", paused: "Paused", finished: "Time is up" };
let state;
let busy = false;

function format(milliseconds) {
  const seconds = Math.ceil(Math.max(0, milliseconds) / 1000);
  const parts = [Math.floor(seconds / 60) % 60, seconds % 60];
  if (seconds >= 3600) parts.unshift(Math.floor(seconds / 3600));
  return parts.map((part) => String(part).padStart(2, "0")).join(":");
}

function minutesSelected() {
  const value = $("duration").value === "custom" ? $("custom-duration").value : $("duration").value;
  const minutes = Number(value);
  if (!Number.isInteger(minutes) || minutes < 1 || minutes > 1440) {
    throw new Error("Enter a whole number from 1 to 1440 minutes.");
  }
  return minutes;
}

function render() {
  if (!state) {
    for (const button of document.querySelectorAll("button")) button.disabled = busy;
    return;
  }
  for (const id of ["main", "focus"]) {
    const timer = state[id];
    const remaining = timer.status === "running"
      ? Math.max(0, timer.deadline - Date.now()) : timer.remainingMs;
    $(id + "-clock").textContent = format(remaining);
    $(id + "-clock").classList.toggle("finished", timer.status === "finished");
    $(id + "-status").textContent = LABEL[timer.status];
    $(id + "-status").classList.toggle("finished", timer.status === "finished");
    $(id + "-toggle").textContent = {
      idle: "Start", running: "Pause", paused: "Resume", finished: "Start again",
    }[timer.status];
  }
  $("apply-duration").hidden = state.main.status === "idle" || state.main.status === "finished";
  for (const button of document.querySelectorAll("button")) button.disabled = busy;
}

async function send(message) {
  const response = await chrome.runtime.sendMessage(message);
  if (response?.error) throw new Error(response.error);
  if (!response?.state) throw new Error("Could not reach the timer. Reopen the popup and try again.");
  state = response.state;
  render();
}

async function act(message) {
  if (busy) return;
  busy = true;
  $("error").hidden = true;
  render();
  try {
    await send(message);
  } catch (error) {
    $("error").textContent = error.message;
    $("error").hidden = false;
  } finally {
    busy = false;
    render();
  }
}

$("duration").addEventListener("change", () => {
  $("custom-duration").hidden = $("duration").value !== "custom";
});
$("main-toggle").addEventListener("click", () => {
  try {
    const minutes = state.main.status === "idle" || state.main.status === "finished"
      ? minutesSelected() : undefined;
    void act({ type: "toggle", id: "main", minutes, expectedStatus: state.main.status });
  } catch (error) {
    $("error").textContent = error.message;
    $("error").hidden = false;
  }
});
$("focus-toggle").addEventListener("click", () => void act({
  type: "toggle", id: "focus", expectedStatus: state.focus.status,
}));
$("main-reset").addEventListener("click", () => void act({ type: "reset", id: "main" }));
$("focus-reset").addEventListener("click", () => void act({ type: "reset", id: "focus" }));
$("apply-duration").addEventListener("click", () => {
  try { void act({ type: "setDuration", id: "main", minutes: minutesSelected() }); }
  catch (error) { $("error").textContent = error.message; $("error").hidden = false; }
});

void act({ type: "get" }).then(() => {
  if (!state) return;
  const minutes = state.main.durationMs / 60_000;
  const preset = [...$("duration").options].find((option) => Number(option.value) === minutes);
  $("duration").value = preset ? preset.value : "custom";
  $("custom-duration").value = String(minutes);
  $("custom-duration").hidden = Boolean(preset);
});
setInterval(render, 1000);
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && changes["fullFocus.browserTimers.v1"] && !busy) void act({ type: "get" });
});
