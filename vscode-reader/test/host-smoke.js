"use strict";

// Invoked by VS Code's extension test host, not by node --test.
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const vscode = require("vscode");

async function run() {
  const extension = vscode.extensions.getExtension("anantsimran.reading-desk");
  assert.ok(extension, "Reading Desk development extension is registered");
  await extension.activate();
  const folder = await fs.mkdtemp(path.join(os.tmpdir(), "reading-desk-host-"));
  const markdownPath = path.join(folder, "sample.md");
  try {
    await fs.writeFile(markdownPath, "# Reader smoke\n\nA **marked** sentence.\n\n```mermaid\ngraph TD\nA-->B\n```\n");
    const document = await vscode.workspace.openTextDocument(vscode.Uri.file(markdownPath));
    const html = await vscode.commands.executeCommand("markdown.api.render", document);
    assert.match(html, /reader smoke/i);
    assert.match(html, /mermaid/, "VS Code's Markdown renderer includes Mermaid content");
    await vscode.commands.executeCommand("readingDesk.open", document.uri);
    const tab = vscode.window.tabGroups.all.flatMap(group => group.tabs).find(item => item.label === "Reading Desk: sample.md");
    assert.ok(tab, "Reading Desk opened its dedicated reading pane");
    console.log("Reading Desk Markdown reading pane integration passed.");
  } finally {
    await fs.rm(folder, { recursive: true, force: true });
  }
}

module.exports = { run };
