import { request } from './api.js';

const $ = id => document.getElementById(id);
const make = (tag, className, value) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (value !== undefined) node.textContent = value;
  return node;
};

let state;
let receivedAt = 0;
let busy = false;
let refreshing = false;
let revision = 0;
let draftPlanId;
let selectedIds = [];
let pickerSignature = '';
let timelineSignature = '';
let viewedPlanId;
let lastTickAt;
const alertStorageKey = 'wyndle-daily-alerts';
const lastEventStorageKey = 'wyndle-daily-last-event';
let alertsEnabled = readAlertsEnabled();
let toastTimeout;
let currentWorkBlock;
let currentBufferBlock;
let currentBreakBlock;

function readAlertsEnabled() {
  try { return localStorage.getItem(alertStorageKey) === 'true'; }
  catch { return false; }
}

function saveAlertsEnabled(value) {
  try { localStorage.setItem(alertStorageKey, String(value)); }
  catch { /* The toggle still works for this page. */ }
}

function claimEvent(planId, timestamp) {
  const key = `${planId}:${timestamp}`;
  try {
    if (localStorage.getItem(lastEventStorageKey) === key) return false;
    localStorage.setItem(lastEventStorageKey, key);
  } catch { /* Alerts still work when storage is unavailable. */ }
  return true;
}

function serverNow() {
  return state ? state.now + (Date.now() - receivedAt) / 1000 : Date.now() / 1000;
}

function setError(message) {
  $('error').textContent = message;
  $('error').hidden = !message;
}

function toast(message) {
  clearTimeout(toastTimeout);
  $('toast').textContent = message;
  $('toast').hidden = false;
  toastTimeout = setTimeout(() => { $('toast').hidden = true; }, 6000);
}

async function act(action, data = {}) {
  if (busy) return false;
  busy = true;
  revision++;
  render();
  try {
    state = await request(action, data);
    receivedAt = Date.now();
    setError('');
    render();
    return true;
  } catch (error) {
    setError(error.message);
    return false;
  } finally {
    busy = false;
    render();
  }
}

function nextStartTime() {
  const local = new Date();
  const clock = /^\d{2}:\d{2}$/.test(state?.serverTime || '')
    ? state.serverTime : `${String(local.getHours()).padStart(2, '0')}:${String(local.getMinutes()).padStart(2, '0')}`;
  const [hours, minutes] = clock.split(':').map(Number);
  const next = Math.min(23 * 60 + 59, Math.ceil((hours * 60 + minutes + 1) / 15) * 15);
  return `${String(Math.floor(next / 60)).padStart(2, '0')}:${String(next % 60).padStart(2, '0')}`;
}

function renderWorkMode() {
  const estimated = $('plan-work-mode').value === 'estimate';
  $('work-minutes-label').textContent = estimated ? 'Fallback work time' : 'Work minutes';
  $('work-mode-hint').textContent = estimated
    ? 'One work block per task uses its remaining estimate. Work minutes are the fallback when no usable estimate remains.'
    : 'Work minutes split each task’s remaining estimate into shorter blocks.';
}

function syncDraft() {
  const alarm = state.dailyAlarm;
  const planId = alarm?.id ?? null;
  const available = state.tasks.filter(task => !task.done);
  const availableIds = new Set(available.map(task => task.id));
  if (draftPlanId !== planId) {
    draftPlanId = planId;
    selectedIds = alarm ? alarm.selectedTaskIds.filter(id => availableIds.has(id))
      : available.slice(0, 60).map(task => task.id);
    $('plan-start').value = alarm?.start || nextStartTime();
    $('plan-work-mode').value = alarm?.workMode === 'estimate' ? 'estimate' : 'fixed';
    $('plan-work').value = alarm?.workMinutes || 25;
    $('plan-buffer').value = alarm?.bufferMinutes || 5;
    $('plan-break').value = alarm?.breakMinutes || 5;
    renderWorkMode();
    pickerSignature = '';
  }
  selectedIds = selectedIds.filter(id => availableIds.has(id));
  renderTaskPicker(available);
}

function renderTaskPicker(tasks) {
  const signature = JSON.stringify([tasks.map(task => [task.id, task.title, task.parent, task.estimate]), selectedIds, busy]);
  if (pickerSignature === signature) return;
  pickerSignature = signature;
  const taskById = new Map(tasks.map(task => [task.id, task]));
  const ordered = [...selectedIds.map(id => taskById.get(id)), ...tasks.filter(task => !selectedIds.includes(task.id))];
  const picker = $('task-picker');
  picker.replaceChildren();
  $('task-count').textContent = `${selectedIds.length} selected`;
  $('save-plan').disabled = busy || selectedIds.length === 0;
  if (!ordered.length) {
    picker.append(make('p', 'task-empty', 'No unfinished tasks yet. Add a task in the dashboard first.'));
    return;
  }
  for (const task of ordered) {
    const position = selectedIds.indexOf(task.id);
    const row = make('div', 'pick-row');
    const label = make('label');
    const checkbox = make('input');
    checkbox.type = 'checkbox';
    checkbox.checked = position !== -1;
    checkbox.disabled = busy || (position === -1 && selectedIds.length >= 60);
    checkbox.addEventListener('change', () => {
      selectedIds = checkbox.checked ? [...selectedIds, task.id] : selectedIds.filter(id => id !== task.id);
      pickerSignature = '';
      renderTaskPicker(tasks);
    });
    const copy = make('span', 'pick-copy');
    copy.append(make('span', 'pick-title', task.title),
      make('span', 'pick-meta', `${task.parent} · ${task.estimate} min estimated`));
    label.append(checkbox, copy);
    row.append(label);
    if (position !== -1) {
      const moves = make('span', 'pick-move');
      for (const [symbol, offset, word] of [['↑', -1, 'up'], ['↓', 1, 'down']]) {
        const button = make('button', 'quiet', symbol);
        button.type = 'button';
        button.title = `Move ${task.title} ${word}`;
        button.setAttribute('aria-label', button.title);
        button.disabled = busy || position + offset < 0 || position + offset >= selectedIds.length;
        button.addEventListener('click', () => {
          [selectedIds[position], selectedIds[position + offset]] = [selectedIds[position + offset], selectedIds[position]];
          pickerSignature = '';
          renderTaskPicker(tasks);
        });
        moves.append(button);
      }
      row.append(moves);
    }
    picker.append(row);
  }
}

function timeOf(epoch) {
  return new Date(epoch * 1000).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}

function countdown(seconds) {
  const left = Math.max(0, Math.ceil(seconds));
  const hours = Math.floor(left / 3600);
  const minutes = Math.floor((left % 3600) / 60);
  const remainder = left % 60;
  return hours ? `${hours}:${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`
    : `${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`;
}

function blockName(block) {
  if (block.kind === 'buffer') return 'Wrap up this block';
  return block.kind === 'break' ? 'Take a break' : block.title || 'Task unavailable';
}

function renderTimeline(alarm) {
  const signature = JSON.stringify([alarm.id, alarm.blocks]);
  if (timelineSignature === signature) return;
  timelineSignature = signature;
  const timeline = $('timeline');
  timeline.replaceChildren();
  for (const block of alarm.blocks) {
    const row = make('li', `block ${block.kind}${block.missing ? ' missing' : ''}`);
    row.dataset.start = block.start;
    row.dataset.end = block.end;
    const time = make('span', 'block-time');
    time.append(make('span', '', timeOf(block.start)), make('br'), make('span', '', timeOf(block.end)));
    const body = make('div', 'block-body');
    const head = make('div', 'block-head');
    const kindLabel = { work: 'Work', buffer: 'Buffer', break: 'Break' }[block.kind] || 'Block';
    head.append(make('span', 'block-kind', kindLabel),
      make('span', 'block-minutes', `${block.minutes} min`));
    body.append(head, make('h3', '', blockName(block)));
    if (block.kind === 'work') {
      const detail = block.missing ? 'Task changed or was removed. Replan this block.'
        : block.done ? 'Task completed' : block.parent || '';
      body.append(make('p', '', detail));
    }
    row.append(time, body);
    timeline.append(row);
  }
}

async function startFocus(block) {
  if (!state?.started || state.wrapped || block.missing || block.done) return;
  if (state.timer?.kind === 'focus' && state.tasks.some(task => task.id === block.taskId && task.active)) return;
  const now = serverNow();
  if (block.end <= now) return;
  const minutes = Math.max(1, Math.ceil((block.end - Math.max(now, block.start)) / 60));
  if (await act('focus', { id: block.taskId, minutes })) toast(`Focus started: ${blockName(block)}`);
}

async function startBreak(block) {
  if (!state?.started || state.wrapped || block.kind !== 'break' || state.timer?.kind === 'break') return;
  const now = serverNow();
  if (block.end <= now) return;
  const minutes = Math.max(1, Math.ceil((block.end - now) / 60));
  if (await act('break', { minutes })) toast('Break started.');
}

function renderClock() {
  const alarm = state?.dailyAlarm;
  if (!alarm?.blocks?.length) {
    currentWorkBlock = null;
    currentBufferBlock = null;
    currentBreakBlock = null;
    document.title = 'Daily alarm · Wyndle';
    return;
  }
  const now = serverNow();
  const blocks = alarm.blocks;
  const current = blocks.find(block => block.start <= now && now < block.end);
  const next = blocks.find(block => block.start > now);
  const activeTaskId = state.timer?.kind === 'focus' ? state.tasks.find(task => task.active)?.id : null;
  currentWorkBlock = current?.kind === 'work' && !current.done && !current.missing
    && current.taskId !== activeTaskId ? current : null;
  currentBufferBlock = current?.kind === 'buffer' && state.timer?.kind === 'focus' ? current : null;
  currentBreakBlock = current?.kind === 'break' && state.timer?.kind !== 'break' ? current : null;
  const chosen = current || next;
  if (current) {
    $('now-label').textContent = { work: 'WORK BLOCK', buffer: 'BUFFER TIME', break: 'BREAK TIME' }[current.kind] || 'CURRENT BLOCK';
    $('now-title').textContent = blockName(current);
    const detail = current.missing ? ' · Task changed. Replan this block.'
      : current.done ? ' · Task complete. Replan this block.' : '';
    $('now-detail').textContent = `${timeOf(current.start)} – ${timeOf(current.end)}${detail}`;
    $('now-countdown').textContent = countdown(current.end - now);
    $('now-caption').textContent = current.kind === 'buffer' ? 'Until your break begins'
      : current.kind === 'break' ? 'Until the next block' : 'Until this block ends';
  } else if (next) {
    $('now-label').textContent = 'UP NEXT';
    $('now-title').textContent = blockName(next);
    $('now-detail').textContent = `Starts at ${timeOf(next.start)}`;
    $('now-countdown').textContent = countdown(next.start - now);
    $('now-caption').textContent = 'Until this block begins';
  } else {
    $('now-label').textContent = 'DAY PLAN COMPLETE';
    $('now-title').textContent = 'You made room for the work.';
    $('now-detail').textContent = 'All scheduled blocks have ended.';
    $('now-countdown').textContent = '00:00';
    $('now-caption').textContent = 'Take a breath.';
  }
  $('now-card').classList.toggle('buffer', current?.kind === 'buffer');
  $('now-guidance').hidden = current?.kind !== 'buffer';
  $('now-guidance').textContent = currentBufferBlock
    ? 'Wrap up this block, then pause focus when you’re ready.'
    : 'Use this buffer to wrap up before your break.';
  $('now-focus').hidden = !currentWorkBlock || state.wrapped;
  $('now-focus').disabled = busy;
  $('now-pause').hidden = !currentBufferBlock || state.wrapped;
  $('now-pause').disabled = busy;
  $('now-break').hidden = !currentBreakBlock || state.wrapped;
  $('now-break').disabled = busy;
  [...$('timeline').children].forEach((row, index) => {
    row.classList.toggle('current', chosen === blocks[index] && Boolean(current));
    row.classList.toggle('past', Number(row.dataset.end) <= now);
  });
  document.title = current ? `${$('now-countdown').textContent} · Daily alarm · Wyndle` : 'Daily alarm · Wyndle';
}

function alertAtBoundary(previous, now, alarm) {
  if (!alertsEnabled || !state.started || state.wrapped || previous === undefined || now <= previous) return;
  const blocks = alarm.blocks;
  const events = blocks.filter(block => block.kind !== 'work' || (!block.done && !block.missing))
    .map(block => ({ at: block.start,
      message: block.kind === 'buffer' ? 'Buffer time. Wrap up this block; pause focus.'
        : block.kind === 'break' ? 'Break time.' : `Time for ${blockName(block)}.` }));
  if (blocks.length) events.push({ at: blocks[blocks.length - 1].end, message: "Today's planned blocks are complete." });
  const crossed = events.filter(item => previous < item.at && item.at <= now);
  const event = crossed[crossed.length - 1];
  if (document.hidden && (!('Notification' in window) || Notification.permission !== 'granted')) return;
  if (!event || now - event.at > 60 || !claimEvent(alarm.id, event.at)) return;
  toast(event.message);
  if ('Notification' in window && Notification.permission === 'granted') {
    try { new Notification('Wyndle · Daily alarm', { body: event.message, tag: 'wyndle-daily-alarm', silent: true }); }
    catch { /* The in-page notice is still available. */ }
  }
}

function tick() {
  const alarm = state?.dailyAlarm;
  if (!alarm || !state.started || state.wrapped) {
    lastTickAt = undefined;
    viewedPlanId = alarm?.id;
    renderClock();
    return;
  }
  const now = serverNow();
  if (viewedPlanId !== alarm.id) {
    viewedPlanId = alarm.id;
    lastTickAt = now;
  } else {
    alertAtBoundary(lastTickAt, now, alarm);
    lastTickAt = now;
  }
  renderClock();
}

function renderAlerts() {
  $('enable-alerts').textContent = alertsEnabled ? 'Disable page alerts' : 'Enable page alerts';
  $('enable-alerts').setAttribute('aria-pressed', String(alertsEnabled));
  if (!alertsEnabled) $('alert-status').textContent = 'Page alerts are off.';
  else if ('Notification' in window && Notification.permission === 'granted')
    $('alert-status').textContent = 'Browser notifications and in-page reminders are on while this page is open.';
  else $('alert-status').textContent = 'In-page reminders are on. Browser notifications are unavailable or blocked here.';
}

function render() {
  if (!state) return;
  $('loading').hidden = true;
  const alarm = state.dailyAlarm;
  const planning = state.started && !state.wrapped;
  $('day-message').hidden = planning;
  if (!planning) {
    $('day-message-title').textContent = state.wrapped ? 'Today is wrapped.' : 'Start your day first.';
    $('day-message-copy').textContent = state.wrapped
      ? 'Your saved plan is here to look back on. Begin a fresh day tomorrow to plan again.'
      : 'Open the dashboard and start your day. Then come back to arrange your tasks into blocks.';
  }
  $('alarm-layout').hidden = !planning && !alarm;
  $('alarm-layout').classList.toggle('view-only', !planning);
  $('plan-editor').hidden = !planning;
  $('no-plan').hidden = Boolean(alarm);
  $('saved-plan').hidden = !alarm;
  $('clear-plan').disabled = busy || !planning;
  $('legacy-plan').hidden = !planning || !alarm || alarm.blocks.some(block => block.kind === 'buffer');
  if (planning) syncDraft();
  if (alarm) renderTimeline(alarm);
  else timelineSignature = '';
  tick();
  renderAlerts();
}

async function refresh() {
  if (busy || refreshing) return;
  refreshing = true;
  const startedAtRevision = revision;
  try {
    const result = await request();
    if (revision !== startedAtRevision) return;
    state = result;
    receivedAt = Date.now();
    setError('');
    render();
  } catch (error) {
    $('loading').hidden = true;
    if (revision === startedAtRevision) setError(`Cannot reach Wyndle. ${error.message}`);
  } finally {
    refreshing = false;
  }
}

$('plan-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (!selectedIds.length) { setError('Choose at least one unfinished task.'); return; }
  const data = {
    start: $('plan-start').value,
    workMode: $('plan-work-mode').value,
    workMinutes: Number($('plan-work').value),
    bufferMinutes: Number($('plan-buffer').value),
    breakMinutes: Number($('plan-break').value),
    taskIds: [...selectedIds],
  };
  if (await act('alarm_plan', data)) toast('Daily plan saved.');
});
$('plan-work-mode').addEventListener('change', renderWorkMode);
$('clear-plan').addEventListener('click', async () => {
  if (await act('alarm_clear')) toast('Daily plan cleared.');
});
$('now-focus').addEventListener('click', () => { if (currentWorkBlock) startFocus(currentWorkBlock); });
$('now-pause').addEventListener('click', async () => {
  if (currentBufferBlock && await act('pause')) toast('Focus paused.');
});
$('now-break').addEventListener('click', () => { if (currentBreakBlock) startBreak(currentBreakBlock); });
$('enable-alerts').addEventListener('click', async () => {
  if (alertsEnabled) { alertsEnabled = false; saveAlertsEnabled(false); renderAlerts(); return; }
  alertsEnabled = true;
  saveAlertsEnabled(true);
  if ('Notification' in window && Notification.permission === 'default') {
    try { await Notification.requestPermission(); }
    catch { /* In-page reminders remain available. */ }
  }
  renderAlerts();
});

refresh();
setInterval(tick, 1000);
setInterval(refresh, 10000);
document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
window.addEventListener('storage', event => {
  if (event.key === alertStorageKey) {
    alertsEnabled = event.newValue === 'true';
    renderAlerts();
  }
});
