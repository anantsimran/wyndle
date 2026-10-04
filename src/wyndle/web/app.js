// Composition and state only. Components own their controls; theme.css owns aesthetics.
import { request, duration } from './api.js';
import { createFocus } from './components/focus.js';
import { createTaskList } from './components/tasks.js';
import { connectDialogs } from './components/dialogs.js';
import { createDurationPicker } from './components/durations.js';
import { connectHelp } from './components/help.js';
import { createPomodoro } from './components/pomodoro.js';
import { connectHistory } from './components/history.js';

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
    if (action === 'delete' || action === 'delete_group') toast('Removed from today. Past history is kept.');
    return true;
  } catch (err) { error(err.message); return false; }
  finally { busy = false; render(); }
}

const focus = createFocus({ act, toast });
const dialogs = connectDialogs(act);
connectHelp();
connectHistory();
createPomodoro({ toast });
const estimateInput = $('task-estimate');
const estimatePicker = createDurationPicker($('estimate-presets'), {
  value: estimateInput.valueAsNumber,
  onChange(minutes) { estimateInput.value = minutes; },
});
estimateInput.addEventListener('input', () => estimatePicker.setValue(estimateInput.valueAsNumber));
const tasks = createTaskList({ focus: task => focus.focus(task),
  complete: task => act('complete', { id: task.id }), reopen: task => act('reopen', { id: task.id }),
  note: dialogs.note,
  edit: dialogs.edit,
  priority: task => act('priority', { id: task.id, priority: !task.priority }),
  optional: task => act('optional', { id: task.id, optional: !task.optional }),
  move: async (task, direction) => {
    if (!await act('move_task', { id: task.id, direction })) return;
    const row = [...document.querySelectorAll('.task-row')]
      .find(item => item.dataset.taskId === task.id);
    const control = row?.querySelector(`[data-direction="${direction}"]:not(:disabled)`)
      || row?.querySelector('.task-order-controls button:not(:disabled)');
    control?.focus();
  },
  remove: task => dialogs.remove(task), removeGroup: group => dialogs.removeGroup(group),
  completeGroup: group => act('complete_group', { parent: group }),
  addSubtask: parent => {
    $('task-parent').value = parent;
    document.querySelector('#add-form details').open = true;
    addFocus();
  },
});

function updateCarryCount() {
  const count = $('carry-options').querySelectorAll('input:checked').length;
  $('carry-count').textContent = `${count} selected`;
}

function renderCarryover(names, date) {
  const picker = $('carry-picker');
  picker.hidden = names.length === 0;
  const key = JSON.stringify([date, names]);
  if (picker.dataset.items === key) return;
  const previous = new Map((picker.dataset.date === date
    ? [...$('carry-options').querySelectorAll('input')] : [])
    .map(input => [input.value, input.checked]));
  const choices = names.map(name => {
    const label = document.createElement('label');
    label.className = 'check-label';
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.value = name;
    input.checked = previous.get(name) ?? true;
    const title = document.createElement('span');
    title.textContent = name;
    label.append(input, title);
    return label;
  });
  $('carry-options').replaceChildren(...choices);
  picker.dataset.items = key;
  picker.dataset.date = date;
  updateCarryCount();
}

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
  renderCarryover(state.carryover, state.date);
  $('morning').disabled = busy;
  $('subtitle').textContent = state.wrapped ? 'Rest is part of the journey, too.'
    : 'You don’t need to see the whole path. Just the next step.';
  $('notes-path').textContent = state.notesPath;
  $('stat-focus').textContent = duration(state.focusedSeconds);
  $('stat-done').textContent = `${state.tasks.filter(t => t.done).length} / ${state.tasks.length}`;
  $('stat-left').textContent = duration(state.tasks.filter(t => !t.done)
    .reduce((sum, t) => sum + Math.max(0, t.estimate * 60 - t.elapsed), 0));
  // Case-insensitive, like the server's high-level task matching.
  const parentNames = new Map();
  for (const name of ['Today', ...state.groups, ...state.recentGroups]) {
    if (!parentNames.has(name.toLowerCase())) parentNames.set(name.toLowerCase(), name);
  }
  // Daily Chores is not a high-level task, but its + button still needs to select it.
  const unlisted = [...new Set(state.tasks.map(t => t.parent))]
    .filter(name => !parentNames.has(name.toLowerCase()));
  const parents = [...parentNames.values(), ...unlisted];
  const parentSelect = $('task-parent');
  // Rebuilding on every poll would reset the selection and close an open dropdown.
  if (parents.join('\n') !== [...parentSelect.options].map(o => o.value).join('\n')) {
    const current = parentSelect.value;
    parentSelect.replaceChildren(...parents.map(name => {
      const option = new Option(name);
      option.hidden = unlisted.includes(name);
      return option;
    }));
    parentSelect.value = parents.includes(current) ? current : 'Today';
  }
  document.querySelectorAll('form button[type="submit"]').forEach(button => { button.disabled = busy; });
  focus.render(state, busy);
  tasks.render(state.tasks, busy, state.highLevelTasks);
}

function addFocus() { $('task-title').focus(); $('task-title').scrollIntoView({ block: 'center' }); }
$('carry-options').addEventListener('change', updateCarryCount);
$('morning').addEventListener('click', () => act('morning', {
  carryover: [...$('carry-options').querySelectorAll('input:checked')].map(input => input.value),
}));
$('add-toggle').addEventListener('click', addFocus);
$('empty-add').addEventListener('click', addFocus);
$('add-form').addEventListener('submit', async event => {
  event.preventDefault();
  const tier = document.querySelector('input[name="task-tier"]:checked').value;
  if (await act('add', { title: $('task-title').value, parent: $('task-parent').value,
    estimate: Number($('task-estimate').value), priority: tier === 'p0',
    optional: tier === 'optional' })) {
    $('task-title').value = '';
    document.querySelector('input[name="task-tier"][value="regular"]').checked = true;
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
