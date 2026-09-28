import { duration } from '../api.js';

const $ = id => document.getElementById(id);

async function readJson(url) {
  const response = await fetch(url, { cache: 'no-store', signal: AbortSignal.timeout(10000) });
  let body;
  try { body = await response.json(); }
  catch { throw new Error('The dashboard returned an unreadable response. Refresh the page and try again.'); }
  if (!response.ok) throw new Error(body.error || 'Could not load this information.');
  return body;
}

function status(id, message, failed = false) {
  const node = $(id);
  node.textContent = message;
  node.hidden = !message;
  node.classList.toggle('history-error', failed);
}

export function connectHistory() {
  const notesDialog = $('notes-dialog');
  const notesSelect = $('notes-select');
  let listRequest = 0;
  let noteRequest = 0;

  async function loadNote() {
    const option = notesSelect.options[notesSelect.selectedIndex];
    if (!option) return;
    const request = ++noteRequest;
    $('note-title').hidden = true;
    $('note-markdown').hidden = true;
    status('notes-status', 'Loading note…');
    const query = new URLSearchParams({ kind: option.dataset.kind, name: option.dataset.name });
    try {
      const note = await readJson(`/api/note?${query}`);
      if (request !== noteRequest) return;
      $('note-title').textContent = note.title;
      $('note-title').hidden = false;
      $('note-markdown').textContent = note.markdown;
      $('note-markdown').hidden = !note.markdown;
      status('notes-status', note.markdown ? '' : 'This note is empty.');
    } catch (error) {
      if (request === noteRequest) status('notes-status', `Could not load note: ${error.message}`, true);
    }
  }

  async function loadNotes() {
    const request = ++listRequest;
    ++noteRequest;
    const selected = notesSelect.options[notesSelect.selectedIndex];
    const selectedKey = selected ? `${selected.dataset.kind}\0${selected.dataset.name}` : '';
    notesSelect.disabled = true;
    $('notes-chooser').hidden = true;
    $('note-title').hidden = true;
    $('note-markdown').hidden = true;
    status('notes-status', 'Loading saved notes…');
    try {
      const notes = await readJson('/api/notes');
      if (request !== listRequest) return;
      notesSelect.replaceChildren();
      for (const [kind, label] of [['daily', 'Daily notes'], ['tasks', 'Task notes'], ['weekly', 'Reviews']]) {
        if (!notes[kind]?.length) continue;
        const group = document.createElement('optgroup');
        group.label = label;
        for (const entry of notes[kind]) {
          const label = entry.title && entry.title !== entry.name
            ? `${entry.title} · ${entry.name}` : entry.name;
          const option = new Option(label);
          option.dataset.kind = kind;
          option.dataset.name = entry.name;
          group.append(option);
        }
        notesSelect.append(group);
      }
      if (!notesSelect.options.length) {
        status('notes-status', 'No saved notes yet. Start a day to create your first daily note.');
        return;
      }
      const previous = [...notesSelect.options].findIndex(option =>
        `${option.dataset.kind}\0${option.dataset.name}` === selectedKey);
      notesSelect.selectedIndex = previous >= 0 ? previous : 0;
      notesSelect.disabled = false;
      $('notes-chooser').hidden = false;
      await loadNote();
    } catch (error) {
      if (request === listRequest) status('notes-status', `Could not list notes: ${error.message}`, true);
    }
  }

  $('notes-open').addEventListener('click', () => { notesDialog.showModal(); loadNotes(); });
  $('notes-close').addEventListener('click', () => notesDialog.close());
  $('notes-refresh').addEventListener('click', loadNotes);
  notesSelect.addEventListener('change', loadNote);

  const statsDialog = $('stats-dialog');
  let days = 7;
  let statsRequest = 0;

  async function loadStats() {
    const request = ++statsRequest;
    $('stats-week').setAttribute('aria-pressed', String(days === 7));
    $('stats-month').setAttribute('aria-pressed', String(days === 30));
    $('stats-content').hidden = true;
    status('stats-status', 'Loading recent progress…');
    try {
      const stats = await readJson(`/api/stats?days=${days}`);
      if (request !== statsRequest) return;
      if (!stats.trackedDays) {
        status('stats-status', `No saved days in the last ${days} days.`);
        return;
      }
      $('history-days').textContent = `${stats.trackedDays} / ${stats.days}`;
      $('history-focus').textContent = duration(stats.focusedMinutes * 60);
      $('history-tasks').textContent = `${stats.completedTasks} / ${stats.totalTasks}`;
      const daily = $('history-daily');
      daily.replaceChildren();
      for (const day of stats.daily) {
        if (!day.exists) continue;
        const item = document.createElement('li');
        const date = document.createElement('strong');
        date.textContent = day.date;
        const details = document.createElement('span');
        const time = day.startTime && day.endTime ? ` · ${day.startTime}–${day.endTime}`
          : day.startTime ? ` · started ${day.startTime}` : '';
        details.textContent = `${duration(day.focusedMinutes * 60)} focused · ${day.completedTasks} / ${day.totalTasks} steps${time}`;
        item.append(date, details);
        daily.append(item);
      }
      $('stats-content').hidden = false;
      status('stats-status', '');
    } catch (error) {
      if (request === statsRequest) status('stats-status', `Could not load progress: ${error.message}`, true);
    }
  }

  $('stats-open').addEventListener('click', () => { statsDialog.showModal(); loadStats(); });
  $('stats-close').addEventListener('click', () => statsDialog.close());
  $('stats-refresh').addEventListener('click', loadStats);
  $('stats-week').addEventListener('click', () => { days = 7; loadStats(); });
  $('stats-month').addEventListener('click', () => { days = 30; loadStats(); });
}
