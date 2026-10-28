"use strict";

const MINUTE = 60_000;
const MAX_DURATION = 24 * 60 * MINUTE;

function validMinutes(value) {
  return Number.isInteger(value) && value >= 1 && value <= 1440;
}

function formatTime(milliseconds) {
  const seconds = Math.ceil(Math.max(0, milliseconds) / 1000);
  const parts = [Math.floor(seconds / 60) % 60, seconds % 60];
  if (seconds >= 3600) parts.unshift(Math.floor(seconds / 3600));
  return parts.map((part) => String(part).padStart(2, "0")).join(":");
}

class Countdown {
  constructor(durationMs, saved) {
    if (!Number.isFinite(durationMs) || durationMs < 1000 || durationMs > MAX_DURATION) {
      throw new RangeError("Timer duration must be between one second and 24 hours.");
    }
    this.durationMs = durationMs;
    this.reset();
    if (
      saved?.durationMs === durationMs &&
      ["idle", "running", "paused", "finished"].includes(saved.status) &&
      Number.isFinite(saved.remainingMs) &&
      saved.remainingMs >= 0 && saved.remainingMs <= durationMs &&
      (saved.status !== "running" || Number.isFinite(saved.deadline))
    ) {
      this.status = saved.status;
      this.remainingMs = saved.remainingMs;
      this.deadline = saved.status === "running" ? saved.deadline : null;
    }
  }

  remaining(now) {
    return this.status === "running"
      ? Math.min(this.durationMs, Math.max(0, this.deadline - now))
      : this.remainingMs;
  }

  start(now) {
    if (this.status === "running") return;
    if (this.status === "finished" || this.remainingMs === 0) this.reset();
    this.deadline = now + this.remainingMs;
    this.status = "running";
  }

  pause(now) {
    if (this.status !== "running") return;
    if (this.tick(now)) return;
    this.remainingMs = this.remaining(now);
    this.deadline = null;
    this.status = "paused";
  }

  reset() {
    this.status = "idle";
    this.remainingMs = this.durationMs;
    this.deadline = null;
  }

  // Returns true exactly once when a running countdown reaches its deadline.
  tick(now) {
    if (this.status !== "running" || this.remaining(now) > 0) return false;
    this.status = "finished";
    this.remainingMs = 0;
    this.deadline = null;
    return true;
  }

  snapshot() {
    return {
      durationMs: this.durationMs,
      remainingMs: this.remainingMs,
      deadline: this.deadline,
      status: this.status,
    };
  }
}

globalThis.FullFocusCountdown = { Countdown, MINUTE, validMinutes, formatTime };
if (typeof module !== "undefined") module.exports = globalThis.FullFocusCountdown;
