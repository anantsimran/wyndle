import { createDurationPicker } from './durations.js';

export function createFocus({ act, toast }) {
  let minutes = 15;
  let state;
  let received = 0;
  let timerKey = '';
  let lastBoundaryIndex = -1;
  let alertsOn = false;
  try { alertsOn = localStorage.getItem('wyndle.focusAlerts') === 'on'; } catch { /* storage may be blocked */ }
  const $ = id => document.getElementById(id);
  const nextTask = () => state?.tasks.find(t => t.active)
    || state?.tasks.find(t => t.id === state.lastTaskId && !t.done)
    || state?.tasks.find(t => !t.done && t.priority)
    || state?.tasks.find(t => !t.done && !t.optional)
    || state?.tasks.find(t => !t.done);
  createDurationPicker($('focus-durations'), {
    value: minutes, onChange(value) { minutes = value; tick(); },
  });
  $('focus').addEventListener('click', () => {
    if (state?.timer.kind === 'focus') { act('pause'); return; }
    const task = nextTask();
    if (task) act('focus', { id: task.id, minutes });
  });
  $('pause').addEventListener('click', () => act('pause'));
  $('break').addEventListener('click', () => act('break', { minutes: 5 }));
  function renderAlertButton() {
    $('focus-alerts').textContent = alertsOn ? 'Disable timer alerts' : 'Enable timer alerts';
    $('focus-alerts').setAttribute('aria-pressed', String(alertsOn));
  }
  $('focus-alerts').addEventListener('click', async () => {
    alertsOn = !alertsOn;
    try { localStorage.setItem('wyndle.focusAlerts', alertsOn ? 'on' : 'off'); } catch { /* in-memory preference */ }
    renderAlertButton();
    if (!alertsOn) { toast('Timer alerts off.'); return; }
    if ('Notification' in window && Notification.permission === 'default') {
      try { await Notification.requestPermission(); }
      catch { /* in-page alerts remain available */ }
    }
    toast('Timer alerts on. Browser banners appear when permission is allowed.');
  });
  renderAlertButton();

  function alertBoundary(timer, index) {
    if (!alertsOn) return;
    const elapsed = index === 0 ? Math.round(timer.duration / 60) : 5;
    const title = timer.kind === 'break' ? 'Break finished' : `${elapsed}m block finished`;
    const body = timer.kind === 'break' ? 'Ready for the next step?' :
      `${timer.title || 'Focus'} · ${index === 0 ? '5m overflow started' : 'another 5m overflow started'}`;
    const key = `${timerKey}:${index}`;
    try {
      if (localStorage.getItem('wyndle.lastTimerAlert') === key) return;
      localStorage.setItem('wyndle.lastTimerAlert', key);
    } catch { /* this tab still deduplicates with lastBoundaryIndex */ }
    toast(`${title}. ${body}`);
    if ('Notification' in window && Notification.permission === 'granted') {
      try { new Notification(`Wyndle · ${title}`, { body, silent: true, tag: 'wyndle-focus-timer' }); }
      catch { /* the in-page notice is still visible */ }
    }
  }

  function tick() {
    if (!state) return;
    const timer = state.timer;
    const now = state.now + (Date.now() - received) / 1000;
    const running = Boolean(timer.kind);
    const remaining = running ? Math.ceil(timer.end - now) : minutes * 60;
    const seconds = Math.abs(remaining);
    const clock = `${remaining < 0 ? '+' : ''}${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
    $('countdown').textContent = clock;
    const overtime = running && remaining < 0;
    document.querySelector('.timer-ring').classList.toggle('overtime', overtime);
    $('live-dot').classList.toggle('overtime', overtime);
    $('timer-caption').textContent = remaining < 0 ? 'A MOMENT TO CHECK IN' : timer.kind === 'break' ? 'ROOM TO BREATHE' : 'MINUTES, JUST FOR THIS';
    document.title = running ? `${clock} · Wyndle` : 'Wyndle · Journey before destination';
    const key = running ? `${state.date}:${timer.kind}:${timer.end}:${timer.title}` : '';
    const index = !running || now < timer.end ? -1 :
      timer.kind === 'focus' ? Math.floor((now - timer.end) / 300) : 0;
    if (key !== timerKey) {
      timerKey = key;
      lastBoundaryIndex = index; // A newly opened page does not replay old alarms.
    } else if (index > lastBoundaryIndex) {
      lastBoundaryIndex = index;
      const boundaryTime = timer.end + (timer.kind === 'focus' ? index * 300 : 0);
      if (now - boundaryTime <= 60) alertBoundary(timer, index);
    }
  }
  setInterval(tick, 1000);
  return {
    focus(task) { return act(task.active ? 'pause' : 'focus', { id: task.id, minutes }); },
    render(value, busy) {
      state = value;
      received = Date.now();
      const task = nextTask();
      const running = Boolean(state.timer.kind);
      const onBreak = state.timer.kind === 'break';
      $('focus-title').textContent = onBreak ? 'Even a journey needs rest.' : task?.title || 'What’s your next small step?';
      $('focus-parent').textContent = onBreak ? 'Stand up. Look away. Breathe.' : task?.parent || 'Add something small to your list.';
      $('focus-label').textContent = onBreak ? 'A LITTLE BREATHING ROOM' : 'YOUR NEXT STEP';
      $('focus').textContent = running ? onBreak ? 'Back to the journey ▶' : 'Pause focus Ⅱ' : 'Take the next step ▶';
      $('focus').disabled = busy || !task;
      $('pause').disabled = busy || (!running && !state.tasks.some(t => t.active));
      $('break').disabled = busy || onBreak;
      $('live-dot').hidden = !running;
      $('timer-hint').textContent = running && !onBreak
        ? 'Time keeps counting until you pause, even if you close this tab.'
        : 'A small start counts. You can pause whenever you need.';
      tick();
    },
  };
}
