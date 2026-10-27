'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { Alerts } = require('../alerts');

test('sidebar boundaries deliver once, including after the view is hidden', () => {
  const sent = [];
  const alerts = new Alerts(message => sent.push(message), { timer: true });
  const event = { id: 'one', channel: 'timer', at: 100, title: 'Break finished', body: 'Ready?' };
  const data = { date: '2026-10-16', now: 99, timer: { kind: 'break', end: 100 }, reminders: [event] };
  alerts.update(data);
  assert.equal(sent.length, 0);
  alerts.deliver(event); // Foreground iframe and host poll must not duplicate.
  alerts.update({ ...data, now: 101 });
  alerts.update({ ...data, now: 110 });
  assert.equal(sent.length, 1);
  alerts.enabled.timer = false;
  alerts.update({ ...data, now: 120, reminders: [{ ...event, id: 'two', at: 115 }] });
  assert.equal(sent.length, 1);
});

test('newly opened sidebar does not replay old reminders', () => {
  const alerts = new Alerts(() => assert.fail('old alert delivered'), { daily: true });
  const data = { now: 110, timer: {}, dailyAlarm: { id: 'plan' },
    reminders: [{ id: 'old', channel: 'daily', at: 100, title: 'Old', body: 'Old' }] };
  alerts.update(data);
  alerts.update({ ...data, now: 120 });
  alerts.deliver({ id: 'bad', title: 42 });
});
