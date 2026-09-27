export function connectHelp() {
  const dialog = document.getElementById('help-dialog');
  const content = document.getElementById('help-content');
  let loaded = false;
  let pending = false;
  document.getElementById('help-close').addEventListener('click', () => dialog.close());
  document.getElementById('help-open').addEventListener('click', async () => {
    dialog.showModal();
    if (loaded || pending) return;
    pending = true;
    content.textContent = 'Opening your guide…';
    try {
      const response = await fetch('/api/help', { signal: AbortSignal.timeout(10000) });
      if (!response.ok) throw new Error('Could not load the guide. Close and reopen to try again.');
      const help = await response.json();
      // HTML comes only from our packaged Markdown, rendered server-side with raw HTML disabled.
      content.innerHTML = help.guideHtml;
      document.getElementById('help-cli').textContent = help.cliHelp;
      loaded = true;
    } catch (error) { content.textContent = error.message; }
    finally { pending = false; }
  });
}
