export function connectDialogs(act) {
  const $ = id => document.getElementById(id);
  let noteTask;
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
  return { note(task) { noteTask = task; $('note-dialog').showModal(); } };
}
