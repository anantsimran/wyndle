export function createFocus({ act, toast }) {
  let minutes = 15;
  let state;
  let received = 0;
  let lastBoundary = '';
  const $ = id => document.getElementById(id);
  const nextTask = () => state?.tasks.find(t => t.active)
    || state?.tasks.find(t => t.id === state.lastTaskId && !t.done)
    || state?.tasks.find(t => !t.done);
  const buttons = [...document.querySelectorAll('[data-minutes]')];
  buttons.forEach(button => button.addEventListener('click', () => {
    minutes = Number(button.dataset.minutes);
    buttons.forEach(b => {
      b.classList.toggle('selected', b === button);
      b.setAttribute('aria-pressed', String(b === button));
    });
    tick();
  }));
  $('focus').addEventListener('click', () => {
    if (state?.timer.kind === 'focus') { act('pause'); return; }
    const task = nextTask();
    if (task) act('focus', { id: task.id, minutes });
  });
  $('pause').addEventListener('click', () => act('pause'));
  $('break').addEventListener('click', () => act('break', { minutes: 5 }));

  function tick() {
    if (!state) return;
    const timer = state.timer;
    const now = state.now + (Date.now() - received) / 1000;
    const running = Boolean(timer.kind);
    const remaining = running ? Math.ceil(timer.end - now) : minutes * 60;
    const seconds = Math.abs(remaining);
    const clock = `${remaining < 0 ? '+' : ''}${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
    $('countdown').textContent = clock;
    $('timer-caption').textContent = remaining < 0 ? 'A MOMENT TO CHECK IN' : timer.kind === 'break' ? 'ROOM TO BREATHE' : 'MINUTES, JUST FOR THIS';
    document.title = running ? `${clock} · Wyndle` : 'Wyndle · Journey before destination';
    const boundary = `${state.date}:${timer.kind}:${timer.end}`;
    if (running && remaining <= 0 && boundary !== lastBoundary) {
      lastBoundary = boundary;
      toast(timer.kind === 'break' ? 'A little restored. Ready for the next step?' : 'A small promise kept. Keep going, or take a breath.');
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
