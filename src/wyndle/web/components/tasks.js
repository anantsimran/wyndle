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

export function createTaskList({ focus, complete, reopen, note, edit, priority, optional, move,
                                 remove, removeGroup, completeGroup, addSubtask }) {
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
      const expandedNotes = new Set([...open.querySelectorAll('.task-row'), ...done.querySelectorAll('.task-row')]
        .filter(item => item.querySelector('.task-notes[open]'))
        .map(item => item.dataset.taskId));
      open.replaceChildren();
      done.replaceChildren();
      const groups = new Map();
      for (const task of tasks.filter(t => !t.done)) {
        if (!groups.has(task.parent)) groups.set(task.parent, []);
        groups.get(task.parent).push(task);
      }
      // A new high-level task has no subtasks yet but must still be visible.
      highLevelTasks.filter(g => !g.done && !groups.has(g.title)).forEach(g => groups.set(g.title, []));
      const row = (task, position = 0, siblingCount = 0) => {
        const overdue = task.estimate > 0 && task.elapsed > task.estimate * 60;
        const item = element('div', `task-row${task.active ? ' active' : ''}${task.done ? ' done' : ''}${overdue ? ' overdue' : ''}`);
        item.dataset.taskId = task.id;
        const check = element('button', 'task-check', task.done ? '✓' : '');
        check.setAttribute('aria-label', task.done ? `Mark ${task.title} not done` : `Complete ${task.title}`);
        check.title = task.done ? 'Mark not done' : 'Complete';
        check.disabled = busy;
        check.addEventListener('click', () => (task.done ? reopen : complete)(task));
        const body = element('div', 'task-body');
        const title = element('span', 'task-title');
        title.append(element('span', 'task-name', task.title));
        if (task.priority) title.append(element('span', 'priority-badge', 'P0'));
        if (task.optional) title.append(element('span', 'optional-badge', 'Optional'));
        body.append(title);
        const meta = task.done
          ? [`Total ${duration(task.elapsed)}`, `Started ${task.startedAt ? new Date(task.startedAt * 1000).toLocaleString() : 'not tracked'}`,
            `Ended ${task.endedAt ? new Date(task.endedAt * 1000).toLocaleString() : 'not recorded'}`]
          : [task.estimate ? `${task.estimate} min planned` : 'No estimate',
            task.elapsed ? `${duration(task.elapsed)} given` : '', task.active ? 'In focus' : ''];
        body.append(element('span', 'task-meta', meta.filter(Boolean).join(' · ')));
        if (!task.done && siblingCount > 1) {
          const order = element('div', 'task-order-controls');
          order.setAttribute('role', 'group');
          order.setAttribute('aria-label', `Order of ${task.title}`);
          const up = iconButton('↑', `Move ${task.title} up in ${task.parent}`, busy,
            () => move(task, 'up'));
          const down = iconButton('↓', `Move ${task.title} down in ${task.parent}`, busy,
            () => move(task, 'down'));
          up.dataset.direction = 'up';
          down.dataset.direction = 'down';
          up.disabled = busy || position === 0;
          down.disabled = busy || position === siblingCount - 1;
          order.append(up, down);
          body.append(order);
        }
        if (task.notes?.length) {
          const notes = element('details', 'task-notes');
          notes.open = expandedNotes.has(task.id);
          notes.append(element('summary', '', `${task.notes.length} ${task.notes.length === 1 ? 'note' : 'notes'}`));
          task.notes.forEach(text => notes.append(element('p', 'small muted', text)));
          body.append(notes);
        }
        item.append(check, body);
        const priorityButton = iconButton('P0',
          `${task.priority ? 'Remove P0 from' : 'Mark P0'} ${task.title}`,
          busy, () => priority(task));
        priorityButton.classList.add('tier-toggle');
        priorityButton.classList.toggle('is-priority', task.priority);
        priorityButton.setAttribute('aria-pressed', String(task.priority));
        item.append(priorityButton);
        const optionalButton = iconButton('Opt',
          `${task.optional ? 'Remove optional from' : 'Mark optional'} ${task.title}`,
          busy, () => optional(task));
        optionalButton.classList.add('tier-toggle');
        optionalButton.classList.toggle('is-optional', task.optional);
        optionalButton.setAttribute('aria-pressed', String(task.optional));
        item.append(optionalButton);
        item.append(iconButton('✎', `Edit ${task.title}`, busy, () => edit(task)));
        const noteButton = element('button', 'quiet', '+');
        noteButton.setAttribute('aria-label', `Add note to ${task.title}`);
        noteButton.title = 'Add a note';
        noteButton.disabled = busy;
        noteButton.addEventListener('click', () => note(task));
        item.append(noteButton);
        if (!task.done) {
          const play = element('button', 'task-action', task.active ? 'Ⅱ' : '▶');
          play.setAttribute('aria-label', `${task.active ? 'Pause' : 'Focus on'} ${task.title}`);
          play.title = task.active ? 'Pause' : 'Start focus';
          play.disabled = busy;
          play.addEventListener('click', () => focus(task));
          item.append(play);
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
        children.forEach((task, index) => open.append(row(task, index, children.length)));
      }
      const completed = tasks.filter(t => t.done);
      completed.forEach(task => done.append(row(task)));
      document.getElementById('completed').hidden = completed.length === 0;
      document.getElementById('completed-label').textContent = `Completed · ${completed.length}`;
      const remaining = tasks.filter(t => !t.done);
      const p0 = remaining.filter(t => t.priority).length;
      const optionalCount = remaining.filter(t => t.optional).length;
      document.getElementById('task-count').textContent = remaining.length;
      document.getElementById('remaining-total').textContent = `${remaining.length} left`;
      document.getElementById('remaining-p0').textContent = p0;
      document.getElementById('remaining-regular').textContent = remaining.length - p0 - optionalCount;
      document.getElementById('remaining-optional').textContent = optionalCount;
      document.getElementById('empty').hidden = groups.size > 0;
    },
  };
}
