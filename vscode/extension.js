'use strict';
const vscode = require('vscode');
const { DashboardServer, status } = require('./server');

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}

function activate(context) {
  const output = vscode.window.createOutputChannel('Wyndle');
  const server = new DashboardServer(output);
  const badge = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 10);
  badge.command = 'wyndle.open';
  badge.text = '$(sparkle) Wyndle';
  badge.tooltip = 'Take the next step — open Wyndle';
  badge.show();
  let view;
  let url;
  let polling = false;
  const config = () => vscode.workspace.getConfiguration('wyndle');
  const connect = async () => {
    if (!vscode.workspace.isTrusted) throw new Error('Trust this workspace to run Wyndle.');
    url = await server.connect(config().get('executable'), config().get('port'));
    return url;
  };
  const render = async () => {
    if (!view) return;
    const currentView = view;
    currentView.webview.html = '<!doctype html><html><body><p>Finding your next step…</p></body></html>';
    try {
      const address = await connect();
      if (view !== currentView) return;
      currentView.webview.options = { enableScripts: true, localResourceRoots: [] };
      // The exact same app runs in the browser and the sidebar: no duplicated UI.
      currentView.webview.html = `<!doctype html><html lang="en"><head>
        <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
        <meta http-equiv="Content-Security-Policy" content="default-src 'none'; frame-src ${address}; style-src 'unsafe-inline';">
        <style>html,body,iframe{margin:0;width:100%;height:100%;border:0;overflow:hidden}body{background:var(--vscode-sideBar-background)}</style>
        </head><body><iframe title="Wyndle focus dashboard" src="${address}" allow="clipboard-write"></iframe></body></html>`;
    } catch (error) {
      if (view !== currentView) return;
      currentView.webview.html = `<!doctype html><html><body><h3>Let’s get Wyndle ready.</h3>
        <p>${escapeHtml(error.message)}</p><p>Open Settings → Wyndle → Executable, then use the reconnect button above.</p></body></html>`;
      output.appendLine(error.message);
    }
  };
  context.subscriptions.push(output, badge, { dispose: () => server.dispose() },
    vscode.window.registerWebviewViewProvider('wyndle.dashboard', {
      resolveWebviewView(nextView) {
        view = nextView;
        nextView.onDidDispose(() => { if (view === nextView) view = undefined; });
        render();
      },
    }),
    vscode.commands.registerCommand('wyndle.open', () => vscode.commands.executeCommand('wyndle.dashboard.focus')),
    vscode.commands.registerCommand('wyndle.retry', render),
    vscode.commands.registerCommand('wyndle.browser', async () => {
      try { await vscode.env.openExternal(vscode.Uri.parse(await connect())); }
      catch (error) { vscode.window.showErrorMessage(error.message); }
    }),
    vscode.workspace.onDidChangeConfiguration(event => { if (event.affectsConfiguration('wyndle')) render(); }),
  );
  const interval = setInterval(async () => {
    if (!url || polling) return;
    polling = true;
    try {
      const data = await status(Number(new URL(url).port));
      const remaining = Math.ceil((data.timer.end - Date.now() / 1000) / 60);
      badge.text = data.timer.kind ? `$(watch) ${remaining > 0 ? `${remaining}m` : 'Check in'} · ${data.timer.kind === 'break' ? 'Rest' : 'Focus'}` : '$(sparkle) Wyndle';
    } catch { badge.text = '$(debug-disconnect) Wyndle'; }
    finally { polling = false; }
  }, 5000);
  context.subscriptions.push({ dispose: () => clearInterval(interval) });
}
module.exports = { activate };
