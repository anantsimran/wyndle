export function connectDialogs(act) {
  const $ = id => document.getElementById(id);
  let noteTask;
  let deletion;
  $('group-toggle').addEventListener('click', () => $('group-dialog').showModal());
  $('group-cancel').addEventListener('click', () => $('group-dialog').close());
  $('group-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (await act('add_group', { title: $('group-title').value })) {
      $('task-parent').value = $('group-title').value.trim();
      $('group-title').value = '';
      $('group-dialog').close();
      $('task-title').focus();
    }
  });
  $('delete-cancel').addEventListener('click', () => $('delete-dialog').close());
  $('delete-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (!await act(deletion.action, deletion.data)) return;
    // Otherwise the next quick-add would silently recreate the deleted group.
    if (deletion.action === 'delete_group' && $('task-parent').value === deletion.data.parent) {
      $('task-parent').value = 'Today';
    }
    $('delete-dialog').close();
  });
  function remove(title, action, data, description) {
    deletion = { action, data };
    $('delete-title').textContent = `Delete “${title}”?`;
    $('delete-description').textContent = description;
    $('delete-dialog').showModal();
  }
  $('wrap-toggle').addEventListener('click', () => $('wrap-dialog').showModal());
  $('wrap-cancel').addEventListener('click', () => $('wrap-dialog').close());
  $('note-cancel').addEventListener('click', () => $('note-dialog').close());
  $('wrap-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (await act('wrap', { tomorrow: $('tomorrow').value, reflection: $('reflection').value })) {
      $('wrap-dialog').close();
    }
  });
  $('note-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (await act('note', { id: noteTask.id, note: $('note-input').value })) {
      $('note-dialog').close();
      $('note-input').value = '';
    }
  });
  return {
    note(task) { noteTask = task; $('note-dialog').showModal(); },
    remove(task) { remove(task.title, 'delete', { id: task.id },
      'This removes the subtask and its notes from today’s plan. Saved history and focused time stay. It will not carry into tomorrow.'); },
    removeGroup(parent) { remove(parent, 'delete_group', { parent },
      'This removes the high-level task and all its subtasks from today’s plan. Saved history and focused time stay.'); },
  };
}
