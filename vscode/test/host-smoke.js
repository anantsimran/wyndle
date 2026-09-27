'use strict';
// Run by VS Code's extension test host, pointed at an isolated test server.
const assert = require('node:assert/strict');
const vscode = require('vscode');
const { status } = require('../server');

async function run() {
  const extension = vscode.extensions.getExtension('anantsimran.wyndle');
  assert.ok(extension, 'Development extension is registered');
  await extension.activate();
  assert.ok(extension.isActive);
  await vscode.commands.executeCommand('wyndle.open');
  const port = vscode.workspace.getConfiguration('wyndle').get('port');
  const data = await status(port);
  assert.equal(data.app, 'wyndle');
  await new Promise(resolve => setTimeout(resolve, 2000));
  console.log('Wyndle extension activation, view command, and backend connection passed.');
}
module.exports = { run };
