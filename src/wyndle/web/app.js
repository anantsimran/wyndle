// Composition and state only. Components own their controls; theme.css owns aesthetics.
import { request, duration } from './api.js';
import { createFocus } from './components/focus.js';
import { createTaskList } from './components/tasks.js';
import { connectDialogs } from './components/dialogs.js';

const $ = id => document.getElementById(id);
let state;
let busy = false;
let refreshing = false;
let revision = 0;
let toastTimeout;

function toast(message) {
  clearTimeout(toastTimeout);
  $('toast').textContent = message;
  $('toast').hidden = false;
  toastTimeout = setTimeout(() => { $('toast').hidden = true; }, 6000);
}
function error(message) { $('error').textContent = message; $('error').hidden = !message; }

async function act(action, data) {
  if (busy) return false;
  busy = true;
  revision++;
  render();
  try {
    state = await request(action, data);
    error('');
    if (action === 'complete') toast('Another step forward. That counts.');
    if (action === 'note') toast('Saved for future you.');
    return true;
  } catch (err) { error(err.message); return false; }
  finally { busy = false; render(); }
}

const focus = createFocus({ act, toast });
const dialogs = connectDialogs(act);
const tasks = createTaskList({ focus: task => focus.focus(task),
  complete: task => act('complete', { id: task.id }), note: dialogs.note });

function render() {
  if (!state) return;
  $('date').textContent = new Date(`${state.date}T12:00:00`).toLocaleDateString(undefined, {
    weekday: 'long', month: 'long', day: 'numeric',
  }).toUpperCase();
  $('welcome').hidden = state.started;
  $('workspace').hidden = !state.started || state.wrapped;
  $('finished').hidden = !state.wrapped;
  $('stats').hidden = !state.started;
  $('tomorrow-text').textContent = state.tomorrow ? `Tomorrow’s first step: ${state.tomorrow}` : 'You showed up. That matters.';
  $('carry-label').hidden = state.carryover.length === 0;
  $('morning').disabled = busy;
  $('subtitle').textContent = state.wrapped ? 'Rest is part of the journey, too.'
    : 'You don’t need to see the whole path. Just the next step.';
  $('notes-path').textContent = state.notesPath;
  $('stat-focus').textContent = duration(state.focusedSeconds);
  $('stat-done').textContent = `${state.tasks.filter(t => t.done).length} / ${state.tasks.length}`;
  $('stat-left').textContent = duration(state.tasks.filter(t => !t.done)
    .reduce((sum, t) => sum + Math.max(0, t.estimate * 60 - t.elapsed), 0));
  $('groups').replaceChildren(...state.groups.map(group => {
    const option = document.createElement('option'); option.value = group; return option;
  }));
  document.querySelectorAll('form button[type="submit"]').forEach(button => { button.disabled = busy; });
  focus.render(state, busy);
  tasks.render(state.tasks, busy);
}

function addFocus() { $('task-title').focus(); $('task-title').scrollIntoView({ block: 'center' }); }
$('morning').addEventListener('click', () => act('morning', { carryover: $('carry').checked }));
$('add-toggle').addEventListener('click', addFocus);
$('empty-add').addEventListener('click', addFocus);
$('add-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (await act('add', { title: $('task-title').value, parent: $('task-parent').value,
    estimate: Number($('task-estimate').value) })) {
    $('task-title').value = '';
    $('task-title').focus();
  }
});
document.addEventListener('keydown', event => {
  if (event.key.toLowerCase() === 'n' && !event.metaKey && !event.ctrlKey && !event.altKey
      && !['INPUT', 'TEXTAREA', 'BUTTON'].includes(document.activeElement.tagName)
      && !document.querySelector('dialog[open]') && state?.started && !state.wrapped) {
    event.preventDefault(); addFocus();
  }
});

async function refresh() {
  if (busy || refreshing) return;
  refreshing = true;
  const requestRevision = revision;
  try {
    const result = await request();
    if (revision !== requestRevision) return;
    state = result; error(''); render();
  } catch (err) { if (revision === requestRevision) error(`Cannot reach Wyndle. ${err.message}`); }
  finally { refreshing = false; }
}
refresh();
setInterval(() => { if (!document.hidden) refresh(); }, 5000);
document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
