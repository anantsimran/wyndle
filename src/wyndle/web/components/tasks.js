import { duration } from '../api.js';

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

export function createTaskList({ focus, complete, note }) {
  let previous = '';
  return {
    render(tasks, busy) {
      // Keep focused controls in the DOM when polling hasn't changed the list.
      const signature = JSON.stringify([tasks.map(t => ({ ...t, elapsed: Math.floor(t.elapsed / 60) })), busy]);
      if (signature === previous) return;
      previous = signature;
      const open = document.getElementById('tasks');
      const done = document.getElementById('completed-tasks');
      open.replaceChildren();
      done.replaceChildren();
      const groups = new Map();
      for (const task of tasks.filter(t => !t.done)) {
        if (!groups.has(task.parent)) groups.set(task.parent, []);
        groups.get(task.parent).push(task);
      }
      const row = task => {
        const item = element('div', `task-row${task.active ? ' active' : ''}${task.done ? ' done' : ''}`);
        const check = element('button', 'task-check', task.done ? '✓' : '');
        check.setAttribute('aria-label', task.done ? `${task.title}, completed` : `Complete ${task.title}`);
        check.disabled = task.done || busy;
        check.addEventListener('click', () => complete(task));
        const body = element('div', 'task-body');
        body.append(element('span', 'task-title', task.title));
        body.append(element('span', 'task-meta', [task.estimate ? `${task.estimate} min planned` : 'No estimate',
          task.elapsed ? `${duration(task.elapsed)} given` : '', task.active ? 'In focus' : ''].filter(Boolean).join(' · ')));
        if (task.notes?.length) {
          const notes = element('details', 'task-notes');
          notes.append(element('summary', '', `${task.notes.length} ${task.notes.length === 1 ? 'note' : 'notes'}`));
          task.notes.forEach(text => notes.append(element('p', 'small muted', text)));
          body.append(notes);
        }
        item.append(check, body);
        if (!task.done) {
          const noteButton = element('button', 'quiet', '+');
          noteButton.setAttribute('aria-label', `Add note to ${task.title}`);
          noteButton.title = 'Add a note';
          noteButton.disabled = busy;
          noteButton.addEventListener('click', () => note(task));
          const play = element('button', 'task-action', task.active ? 'Ⅱ' : '▶');
          play.setAttribute('aria-label', `${task.active ? 'Pause' : 'Focus on'} ${task.title}`);
          play.title = task.active ? 'Pause' : 'Start focus';
          play.disabled = busy;
          play.addEventListener('click', () => focus(task));
          item.append(noteButton, play);
        }
        return item;
      };
      for (const [parent, children] of groups) {
        open.append(element('h3', 'task-group', parent));
        children.forEach(task => open.append(row(task)));
      }
      const completed = tasks.filter(t => t.done);
      completed.forEach(task => done.append(row(task)));
      document.getElementById('completed').hidden = completed.length === 0;
      document.getElementById('completed-label').textContent = `Completed · ${completed.length}`;
      document.getElementById('task-count').textContent = tasks.filter(t => !t.done).length;
      document.getElementById('empty').hidden = tasks.some(t => !t.done);
    },
  };
}
