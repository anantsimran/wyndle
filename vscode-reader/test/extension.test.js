"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const Module = require("node:module");
const path = require("node:path");

class Uri {
  constructor(scheme, authority, uriPath) { this.scheme = scheme; this.authority = authority; this.path = uriPath; }
  toString() { return `${this.scheme}://${this.authority}${this.path}`; }
  with(changes) { return new Uri(this.scheme, this.authority, changes.path || this.path); }
  static parse(value) {
    const url = new URL(value);
    const uri = new Uri(url.protocol.slice(0, -1), url.host, url.pathname);
    uri.query = url.search.slice(1);
    return uri;
  }
  static joinPath(uri, ...parts) { return new Uri(uri.scheme, uri.authority, path.posix.resolve(uri.path, ...parts)); }
}

function harness() {
  const commands = new Map();
  const files = new Map();
  let nativeCommentsCreated = 0;
  let tree;
  let hoverProvider;
  let selectionHandler;
  const root = new Uri("vscode-remote", "ssh-remote+example", "/project");
  const calls = [];
  const disposable = { dispose() {} };
  let panel;
  const workspace = {
    workspaceFolders: [{ uri: root }],
    textDocuments: [],
    async openTextDocument(uri) { return this.textDocuments.find(document => document.uri.toString() === uri.toString()) || { uri, getText: () => "# Guide" }; },
    getConfiguration() { return { get(key, fallback) { return key === "styles" ? [".vscode/custom.css"] : fallback; } }; },
    getWorkspaceFolder(uri) { return uri.path.startsWith(root.path + "/") ? { uri: root } : undefined; },
    createFileSystemWatcher() { return { ...disposable, onDidChange: () => disposable, onDidCreate: () => disposable, onDidDelete: () => disposable }; },
    onDidChangeTextDocument: () => disposable,
    onDidOpenTextDocument: () => disposable,
    onDidCloseTextDocument: () => disposable,
    fs: {
      async readFile(uri) {
        if (!files.has(uri.toString())) { const error = new Error("missing"); error.code = "FileNotFound"; throw error; }
        return files.get(uri.toString());
      },
      async createDirectory() {},
      async writeFile(uri, data) { files.set(uri.toString(), data); },
      async rename(from, to) { files.set(to.toString(), files.get(from.toString())); files.delete(from.toString()); },
    },
  };
  const api = {
    Uri, workspace,
    Range: class { constructor(...args) { this.args = args; } contains(point) {
      const [start, end] = this.args;
      return typeof start === "object" && start.character <= point.character && point.character < end.character;
    } },
    MarkdownString: class { constructor(value) { this.value = value; } },
    Hover: class { constructor(contents, range) { this.contents = contents; this.range = range; } },
    languages: { registerHoverProvider(_selectors, provider) { hoverProvider = provider; return disposable; } },
    TextEditorSelectionChangeKind: { Mouse: 2 },
    comments: { createCommentController() { nativeCommentsCreated++; return disposable; } },
    CommentMode: { Preview: 1 }, CommentThreadState: { Unresolved: 0, Resolved: 1 }, CommentThreadCollapsibleState: { Collapsed: 0 },
    env: { uriScheme: "vscode" },
    extensions: { getExtension(id) { return { extensionUri: new Uri("file", "", `/builtin/${id}`), packageJSON: { contributes: id.includes("mermaid") ?
      { "markdown.previewScripts": [{ path: "./markdown-preview-out/index.js", type: "module" }] } :
      { "markdown.previewStyles": ["./media/markdown.css", "./media/highlight.css"] } } }; } },
    ViewColumn: { Beside: 2 },
    commands: { registerCommand(id, handler) { commands.set(id, handler); return disposable; }, async executeCommand(id, ...args) {
      calls.push([id, ...args]);
      if (id === "markdown.api.render") return '<h1>Guide</h1><pre class="mermaid">graph TD</pre>';
    } },
    window: {
      visibleTextEditors: [], activeTextEditor: null,
      createTextEditorDecorationType: () => disposable,
      registerTreeDataProvider(id, provider) { tree = provider; return disposable; },
      createWebviewPanel() {
        const messages = [];
        let handleMessage;
        const webview = { options: {}, html: "", asWebviewUri: uri => uri,
          postMessage(message) { messages.push(message); return Promise.resolve(true); },
          onDidReceiveMessage(handler) { handleMessage = handler; return disposable; } };
        panel = { webview, messages, reveal() {}, onDidDispose: () => disposable,
          message(data) { return handleMessage(data); } };
        return panel;
      },
      async showInputBox() { return "Check this later"; },
      async showQuickPick() { return undefined; },
      onDidChangeVisibleTextEditors: () => disposable,
      onDidChangeTextEditorSelection(handler) { selectionHandler = handler; return disposable; },
      onDidChangeActiveTextEditor: () => disposable,
      showErrorMessage(message) { throw Error(message); },
    },
    EventEmitter: class { event = () => disposable; fire() {} },
    ThemeColor: class {},
    OverviewRulerLane: { Right: 1 },
  };
  const original = Module._load;
  Module._load = function (request, parent, isMain) { return request === "vscode" ? api : original.call(this, request, parent, isMain); };
  let extension;
  try {
    delete require.cache[require.resolve("../extension")];
    extension = require("../extension");
  } finally { Module._load = original; }
  return { commands, files, root, calls, extension, workspace, window: api.window,
    get nativeCommentsCreated() { return nativeCommentsCreated; },
    get tree() { return tree; }, get panel() { return panel; },
    get hoverProvider() { return hoverProvider; }, get selectionHandler() { return selectionHandler; } };
}

test("Reading Desk uses VS Code Markdown rendering, Mermaid, and custom CSS in its own pane", async () => {
  const app = harness();
  await app.extension.activate({ subscriptions: [], extensionUri: new Uri("file", "", "/reading-desk") });
  const source = Uri.joinPath(app.root, "guide.md");
  await app.commands.get("readingDesk.open")(source);
  await app.panel.message({ type: "ready" });
  assert.equal(app.calls.at(-1)[0], "markdown.api.render");
  const html = app.panel.webview.html;
  assert.match(html, /<pre class="mermaid">graph TD<\/pre>/);
  assert.match(html, /markdown-preview-out\/index.js/);
  assert.match(html, /media\/markdown.css/);
  assert.match(html, /media\/reader.css/);
  assert.match(html, /project\/\.vscode\/custom.css/);
  assert.match(html, /reading-desk-toc-list/);
  assert.match(html, /reading-desk-toc-list[^]*reading-desk-comments[^]*<\/aside><main/);
  assert.match(html, /reading-desk-data/);
  assert.doesNotMatch(html, /vscode:\/\/anantsimran/);
  assert.equal(require("../package.json").contributes["markdown.previewScripts"], undefined,
    "Native Markdown preview stays untouched");
});

test("reading pane messages save typed comments without navigation or another window", async () => {
  const app = harness();
  await app.extension.activate({ subscriptions: [], extensionUri: new Uri("file", "", "/reading-desk") });
  const source = Uri.joinPath(app.root, "guide.md");
  const content = "The key sentence matters";
  app.workspace.textDocuments.push({ uri: source, lineCount: 1, getText: () => content,
    positionAt: offset => ({ line: 0, character: offset }) });
  await app.commands.get("readingDesk.open")(source);
  await app.panel.message({ type: "ready" });
  const id = "f6ef80c3-9409-49b0-840d-b71558a317dd";
  await app.panel.message({ type: "create", id, kind: "review", anchor: { quote: "", line: 0 } });
  assert.equal(app.files.size, 0, "Preview never creates an implicit whole-file comment");
  await app.panel.message({ type: "create", id, kind: "highlight", color: "red", important: true,
    anchor: { quote: "key sentence", prefix: "The ", suffix: " matters", position: 4, line: 2 }, note: "Check this" });
  await app.panel.message({ type: "update", id, resolved: true, resolutionComment: "Verified" });
  await app.panel.message({ type: "update", id, resolved: false });
  const file = Uri.joinPath(app.root, ".reading-desk", "reviews.json");
  const saved = JSON.parse(app.files.get(file.toString()).toString()).marks;
  assert.equal(saved.length, 1);
  assert.equal(saved[0].file, "guide.md");
  assert.equal(saved[0].color, "red");
  assert.equal(saved[0].important, true);
  assert.equal(saved[0].note, "Check this");
  assert.equal(saved[0].resolutionComment, "Verified");
  assert.equal(saved[0].resolutionHistory.length, 1);
  assert.equal(saved[0].resolutionHistory[0].comment, "Verified");
  assert.equal(saved[0].resolved, false);
  assert.equal(app.tree.getChildren()[0].mark.id, id);
  assert.equal(app.nativeCommentsCreated, 0);
  await app.panel.message({ type: "create", id: "b6ef80c3-9409-49b0-840d-b71558a317dd",
    kind: "later", anchor: { quote: "key sentence", line: 0 }, note: "Return next week" });
  await app.panel.message({ type: "create", id: "c6ef80c3-9409-49b0-840d-b71558a317dd",
    kind: "review", anchor: { quote: "matters", line: 0 }, note: "Check claim" });
  const newest = app.tree.getChildren();
  assert.deepEqual(newest.map(node => node.mark.kind), ["review", "later", "highlight"]);
  app.window.showQuickPick = async choices => choices.find(choice => choice.kind === "review");
  await app.commands.get("readingDesk.filter")();
  assert.deepEqual(app.tree.getChildren().map(node => node.mark.kind), ["review"]);
  app.window.showInputBox = async () => "claim";
  await app.commands.get("readingDesk.search")();
  assert.equal(app.tree.getChildren().length, 1);
  app.window.showInputBox = async () => "missing";
  await app.commands.get("readingDesk.search")();
  assert.equal(app.tree.getChildren().length, 0);
  assert.ok(app.panel.messages.some(message => message.type === "saveResult" && message.success));
  assert.ok(app.panel.messages.some(message => message.type === "state"));
  await app.panel.message({ type: "openLink", href: "guide.md#second-topic" });
  assert.ok(app.panel.messages.some(message => message.type === "fragment" && message.fragment === "second-topic"));
  assert.ok(!app.calls.some(([command]) => command === "vscode.open" || command === "markdown.showPreviewToSide"));
});

test("source Review saves a selected passage and never silently marks the whole file", async () => {
  const app = harness();
  await app.extension.activate({ subscriptions: [], extensionUri: new Uri("file", "", "/reading-desk") });
  const uri = Uri.joinPath(app.root, "module.py");
  const content = "def calculate():\n    return 42\n";
  const document = { uri, getText: () => content, offsetAt: point => point.offset,
    positionAt: offset => ({ line: 0, character: offset }), lineCount: 2 };
  app.window.activeTextEditor = { document, selection: { start: { offset: 4, line: 0 }, end: { offset: 13, line: 0 } } };
  const decorations = [];
  app.window.visibleTextEditors.push({ document, setDecorations(_type, options) { decorations.push(options); } });
  await app.commands.get("readingDesk.review")();
  const file = Uri.joinPath(app.root, ".reading-desk", "reviews.json");
  let marks = JSON.parse(app.files.get(file.toString()).toString()).marks;
  assert.equal(marks[0].anchor.quote, "calculate");
  assert.equal(marks[0].kind, "review");
  assert.equal(marks[0].note, "Check this later");
  assert.equal(marks[0].color, "green");
  assert.ok(decorations.some(options => options.some(option => option.hoverMessage.value.includes("Check this later"))));
  const hover = app.hoverProvider.provideHover(document, { line: 0, character: 7 });
  assert.match(hover.contents.value, /Check this later/);
  app.selectionHandler({ kind: 2, textEditor: { document }, selections: [{ isEmpty: true, active: { line: 0, character: 7 } }] });
  assert.equal(app.calls.at(-1)[0], "editor.action.showHover");
  app.window.activeTextEditor.selection.end = app.window.activeTextEditor.selection.start;
  await app.commands.get("readingDesk.later")();
  marks = JSON.parse(app.files.get(file.toString()).toString()).marks;
  assert.equal(marks.length, 1);
  app.window.showQuickPick = async choices => choices[0];
  await app.commands.get("readingDesk.later")();
  marks = JSON.parse(app.files.get(file.toString()).toString()).marks;
  assert.equal(marks.length, 2);
  assert.equal(marks[0].anchor.quote, "");
});
