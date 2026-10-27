"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { Countdown, MINUTE, formatTime, validMinutes } = require("../countdown");

test("pause and resume preserve the remaining time without counting paused time", () => {
  const timer = new Countdown(5 * MINUTE);
  timer.start(1000);
  timer.pause(61_000);
  assert.equal(timer.remaining(600_000), 4 * MINUTE);
  timer.start(600_000);
  assert.equal(timer.remaining(630_000), 210_000);
  assert.equal(timer.tick(840_000), true);
  assert.equal(timer.remaining(900_000), 0);
  assert.equal(timer.tick(900_000), false);
});

test("reloading a running timer includes time spent outside VS Code", () => {
  const timer = new Countdown(5 * MINUTE);
  timer.start(1000);
  const restored = new Countdown(5 * MINUTE, timer.snapshot());
  assert.equal(restored.remaining(121_000), 3 * MINUTE);
  assert.equal(restored.tick(301_000), true);
  const finished = new Countdown(5 * MINUTE, restored.snapshot());
  assert.equal(finished.tick(900_000), false);
  assert.equal(finished.status, "finished");
});

test("reset clears the deadline and expired timers can restart", () => {
  const timer = new Countdown(MINUTE);
  timer.start(0);
  timer.tick(MINUTE);
  timer.start(120_000);
  assert.equal(timer.remaining(120_000), MINUTE);
  timer.pause(130_000);
  timer.reset();
  assert.deepEqual(timer.snapshot(), {
    durationMs: MINUTE, remainingMs: MINUTE, deadline: null, status: "idle",
  });
});

test("pause at the deadline finishes instead of creating a paused zero timer", () => {
  const timer = new Countdown(MINUTE);
  timer.start(0);
  timer.pause(MINUTE);
  assert.equal(timer.status, "finished");
});

test("main and Full focus countdowns are independent", () => {
  const main = new Countdown(25 * MINUTE);
  const focus = new Countdown(5 * MINUTE);
  main.start(0);
  focus.start(MINUTE);
  focus.pause(2 * MINUTE);
  assert.equal(main.remaining(3 * MINUTE), 22 * MINUTE);
  assert.equal(focus.remaining(3 * MINUTE), 4 * MINUTE);
});

test("invalid saved state is ignored and paused timers survive reload", () => {
  const paused = new Countdown(MINUTE);
  paused.start(0);
  paused.pause(30_000);
  const restored = new Countdown(MINUTE, paused.snapshot());
  assert.equal(restored.remaining(200_000), 30_000);
  for (const saved of [
    { ...paused.snapshot(), status: "unexpected" },
    { ...paused.snapshot(), remainingMs: -1 },
    { ...paused.snapshot(), remainingMs: Infinity },
    { ...paused.snapshot(), durationMs: 5 * MINUTE },
    { ...paused.snapshot(), status: "running", deadline: null },
  ]) {
    assert.equal(new Countdown(MINUTE, saved).status, "idle");
  }
});

test("format countdowns without showing zero early, including hour-long sessions", () => {
  assert.equal(formatTime(5 * MINUTE), "05:00");
  assert.equal(formatTime(1001), "00:02");
  assert.equal(formatTime(1), "00:01");
  assert.equal(formatTime(0), "00:00");
  assert.equal(formatTime(-10), "00:00");
  assert.equal(formatTime(60 * MINUTE), "01:00:00");
  assert.equal(formatTime(1440 * MINUTE), "24:00:00");
});

test("custom durations accept whole minutes within a day", () => {
  for (const value of [1, 25, 1440]) assert.equal(validMinutes(value), true);
  for (const value of [0, -1, 0.5, 1441, NaN, Infinity]) assert.equal(validMinutes(value), false);
  assert.throws(() => new Countdown(NaN), RangeError);
  assert.throws(() => new Countdown(0), RangeError);
});
