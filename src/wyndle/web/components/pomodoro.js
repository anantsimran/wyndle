// A standalone timer: it never calls the API, and nothing survives a reload.
const PHASES = {
  focus: { label: 'FOCUS', minutes: 25 },
  short: { label: 'SHORT BREAK', minutes: 5 },
  long: { label: 'LONG BREAK', minutes: 15 },
};
const ROUNDS = 4;

function chime() {
  const audio = new AudioContext();
  const tone = audio.createOscillator();
  const gain = audio.createGain();
  tone.frequency.value = 660;
  gain.gain.setValueAtTime(0.15, audio.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + 1.2);
  tone.connect(gain).connect(audio.destination);
  tone.onended = () => audio.close();
  tone.start();
  tone.stop(audio.currentTime + 1.2);
}

export function createPomodoro({ toast }) {
  const $ = id => document.getElementById(id);
  let phase = 'focus';
  let round = 1;
  let remaining = PHASES.focus.minutes * 60;
  // Counting down from a deadline keeps time right when a background tab throttles timers.
  let end = 0;
  const left = () => (end ? Math.max(0, Math.ceil((end - Date.now()) / 1000)) : remaining);
  const clock = s => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

  function setPhase(next) { phase = next; remaining = PHASES[next].minutes * 60; end = 0; }
  function advance() {
    if (phase === 'focus') setPhase(round === ROUNDS ? 'long' : 'short');
    else { round = phase === 'long' ? 1 : round + 1; setPhase('focus'); }
  }
  function render() {
    const seconds = left();
    $('pomodoro-clock').textContent = clock(seconds);
    $('pomodoro-phase').textContent = `POMODORO · ${PHASES[phase].label}`;
    $('pomodoro-round').textContent = `Round ${round} of ${ROUNDS}`;
    $('pomodoro-toggle').textContent = end ? 'Pause' : seconds < PHASES[phase].minutes * 60 ? 'Resume' : 'Start';
    $('pomodoro-open').textContent = end ? `Pomodoro · ${clock(seconds)}` : 'Pomodoro';
  }
  function tick() {
    if (end && Date.now() >= end) {
      const finished = phase;
      advance();
      chime();
      toast(finished === 'focus' ? 'Pomodoro done. Take a breath.' : 'Break over. Ready for another round?');
    }
    render();
  }
  function show(open) {
    $('pomodoro').hidden = !open;
    $('pomodoro-open').setAttribute('aria-expanded', String(open));
  }

  $('pomodoro-open').addEventListener('click', () => show($('pomodoro').hidden));
  $('pomodoro-close').addEventListener('click', () => show(false));
  $('pomodoro-toggle').addEventListener('click', () => {
    if (end) { remaining = left(); end = 0; } else end = Date.now() + remaining * 1000;
    render();
  });
  $('pomodoro-skip').addEventListener('click', () => { advance(); render(); });
  $('pomodoro-reset').addEventListener('click', () => { round = 1; setPhase('focus'); render(); });
  render();
  setInterval(tick, 1000);
}
