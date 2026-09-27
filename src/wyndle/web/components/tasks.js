import { duration } from '../api.js';

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function iconButton(text, label, busy, onClick) {
  const button = element('button', 'quiet', text);
  button.setAttribute('aria-label', label);
  button.title = label;
  button.disabled = busy;
  button.addEventListener('click', onClick);
  return button;
}

export function createTaskList({ focus, complete, reopen, note, remove, removeGroup, completeGroup, addSubtask }) {
  let previous = '';
  return {
    render(tasks, busy, highLevelTasks = []) {
      // Keep focused controls in the DOM when polling hasn't changed the list.
      const signature = JSON.stringify([tasks.map(t => ({ ...t, elapsed: Math.floor(t.elapsed / 60) })),
        highLevelTasks, busy]);
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
      // A new high-level task has no subtasks yet but must still be visible.
      highLevelTasks.filter(g => !g.done && !groups.has(g.title)).forEach(g => groups.set(g.title, []));
      const row = task => {
        const item = element('div', `task-row${task.active ? ' active' : ''}${task.done ? ' done' : ''}`);
        const check = element('button', 'task-check', task.done ? '✓' : '');
        check.setAttribute('aria-label', task.done ? `Mark ${task.title} not done` : `Complete ${task.title}`);
        check.title = task.done ? 'Mark not done' : 'Complete';
        check.disabled = busy;
        check.addEventListener('click', () => (task.done ? reopen : complete)(task));
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
        item.append(iconButton('×', `Delete ${task.title}`, busy, () => remove(task)));
        return item;
      };
      for (const [parent, children] of groups) {
        const header = element('div', 'task-group-head');
        const actions = element('div', 'task-group-actions');
        actions.append(
          iconButton('+', `Add a subtask to ${parent}`, busy, () => addSubtask(parent)),
          iconButton('✓', `Complete ${parent} and all its subtasks`, busy, () => completeGroup(parent)),
          iconButton('×', `Delete ${parent}`, busy, () => removeGroup(parent)),
        );
        header.append(element('h3', 'task-group', parent), actions);
        open.append(header);
        if (!children.length) open.append(element('p', 'small muted task-group-empty', 'No subtasks yet. Add one small step.'));
        children.forEach(task => open.append(row(task)));
      }
      const completed = tasks.filter(t => t.done);
      completed.forEach(task => done.append(row(task)));
      document.getElementById('completed').hidden = completed.length === 0;
      document.getElementById('completed-label').textContent = `Completed · ${completed.length}`;
      document.getElementById('task-count').textContent = tasks.filter(t => !t.done).length;
      document.getElementById('empty').hidden = groups.size > 0;
    },
  };
}
