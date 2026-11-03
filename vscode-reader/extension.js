"use strict";

const vscode = require("vscode");
const path = require("node:path");
const crypto = require("node:crypto");
const { bestMatch, makeAnchor } = require("./anchors");
const { ReviewStore } = require("./store");

const KINDS = new Set(["highlight", "later", "review", "done"]);
const COLORS = new Set(["red", "green", "yellow"]);
const LABELS = { highlight: "Highlight", later: "Return later", review: "For review", done: "Done" };
const ICONS = { highlight: "symbol-color", later: "bookmark", review: "checklist", done: "pass" };
let context;
let tree;
let store;
const decorations = new Map();
const panels = new Map();
const renderTimers = new Map();

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}

function supported(uri) {
  return uri && (uri.scheme === "file" || uri.scheme === "vscode-remote") && /\.(md|py)$/i.test(uri.path);
}

function marksFor(uri) {
  return store.forFile(uri);
}

async function saveChange(uri, change) {
  try {
    const changed = await store.change(uri, change);
    if (!changed) return false;
    tree.refresh();
    refreshEditors(uri);
    sendPanelState(uri);
    return true;
  } catch (error) {
    vscode.window.showErrorMessage(`Could not save review mark: ${error.message}`);
    return false;
  }
}

function sendPanelState(uri) {
  panels.get(uri.toString())?.webview.postMessage({ type: "state", marks: marksFor(uri) });
}

function validatedAnchor(raw) {
  if (!raw || typeof raw !== "object") return null;
  const quote = typeof raw.quote === "string" ? raw.quote.slice(0, 4000) : "";
  return {
    quote,
    prefix: typeof raw.prefix === "string" ? raw.prefix.slice(0, 48) : "",
    suffix: typeof raw.suffix === "string" ? raw.suffix.slice(0, 48) : "",
    position: Number.isInteger(raw.position) && raw.position >= 0 ? raw.position : 0,
    line: Number.isInteger(raw.line) && raw.line >= 0 ? raw.line : 0,
  };
}

async function createMark(uri, kind, anchor, surface, note = "", id, color = "green", important = false) {
  if (!supported(uri) || !KINDS.has(kind)) return;
  anchor = validatedAnchor(anchor);
  if (!anchor || (!anchor.quote && (kind === "highlight" || kind === "done" || surface === "preview"))) return;
  return saveChange(uri, (marks, file) => {
    if (id && marks.some(mark => mark.id === id)) return false;
    marks.unshift({ id: typeof id === "string" && /^[0-9a-f-]{36}$/i.test(id) ? id : crypto.randomUUID(), file, kind,
      color: COLORS.has(color) ? color : "green", important: kind === "highlight" && important === true,
      anchor, surface: surface === "preview" ? "preview" : "source",
      note: String(note).slice(0, 5000), resolved: false, resolutionComment: "", resolutionHistory: [], resolvedAt: null, created: new Date().toISOString() });
    return true;
  });
}

async function updateMark(uri, id, patch) {
  if (!supported(uri)) return;
  return saveChange(uri, marks => {
    const mark = marks.find(item => item.id === id);
    if (!mark) return false;
    if (typeof patch.note === "string") mark.note = patch.note.slice(0, 5000);
    if (mark.kind === "highlight") {
      if (COLORS.has(patch.color)) mark.color = patch.color;
      if (typeof patch.important === "boolean") mark.important = patch.important;
    }
    if (typeof patch.resolved === "boolean") {
      mark.resolved = patch.resolved;
      mark.resolvedAt = patch.resolved ? new Date().toISOString() : null;
      if (patch.resolved) {
        const comment = typeof patch.resolutionComment === "string" ? patch.resolutionComment.slice(0, 5000) : "";
        if (!Array.isArray(mark.resolutionHistory)) mark.resolutionHistory = [];
        mark.resolutionHistory.push({ at: mark.resolvedAt, comment });
        mark.resolutionComment = comment;
      }
    }
    return true;
  });
}

async function deleteMark(uri, id) {
  if (!supported(uri)) return;
  return saveChange(uri, marks => {
    const index = marks.findIndex(item => item.id === id);
    if (index < 0) return false;
    marks.splice(index, 1);
    return true;
  });
}

function sourceAnchor(editor) {
  const document = editor.document;
  const selection = editor.selection;
  const start = document.offsetAt(selection.start);
  const end = document.offsetAt(selection.end);
  return { ...makeAnchor(document.getText(), start, end), line: selection.start.line };
}

async function markSelection(kind, preset) {
  const editor = vscode.window.activeTextEditor;
  if (!editor || !supported(editor.document.uri)) {
    vscode.window.showInformationMessage("Open a Markdown or Python source file, or select text in the Reading Desk pane.");
    return;
  }
  const anchor = sourceAnchor(editor);
  if (anchor.quote.length > 4000) {
    vscode.window.showInformationMessage("Select at most 4,000 characters for a mark.");
    return;
  }
  const textOnly = kind === "highlight" || kind === "done";
  if (textOnly && !anchor.quote) {
    vscode.window.showInformationMessage(`Select text to ${kind === "done" ? "mark as done" : "highlight"}.`);
    return;
  }
  if (!textOnly && !anchor.quote) {
    const choice = await vscode.window.showQuickPick(["Mark whole file", "Cancel"],
      { placeHolder: "Select a passage first, or explicitly mark the whole file" });
    if (choice !== "Mark whole file") return;
  }
  let color = preset?.color || "green";
  let important = preset?.important || false;
  if (kind === "highlight" && !preset) {
    const choice = await vscode.window.showQuickPick([
      { label: "Green highlight (default)", color: "green" }, { label: "Yellow highlight", color: "yellow" },
      { label: "Red highlight", color: "red" }, { label: "Important · yellow", color: "yellow", important: true },
      { label: "Important · green", color: "green", important: true }, { label: "Important · red", color: "red", important: true },
    ], { placeHolder: "Choose highlight color and importance" });
    if (!choice) return;
    color = choice.color; important = !!choice.important;
  }
  const note = textOnly ? "" : await vscode.window.showInputBox({
    prompt: `${LABELS[kind]} comment`, placeHolder: "Add a comment (optional)",
  });
  if (note === undefined && !textOnly) return;
  await createMark(editor.document.uri, kind, anchor, "source", note || "", undefined, color, important);
}

function styleUri(source, value) {
  if (typeof value !== "string" || !value.trim()) return null;
  if (/^https?:\/\//i.test(value)) return value;
  if (/^[a-z][a-z0-9+.-]*:/i.test(value)) return vscode.Uri.parse(value, true);
  const root = vscode.workspace.getWorkspaceFolder(source)?.uri || vscode.Uri.joinPath(source, "..");
  const expanded = value.replace(/\$\{workspaceFolder\}/g, root.path);
  if (expanded.startsWith("/")) return source.with({ path: expanded });
  return vscode.Uri.joinPath(root, expanded);
}

function htmlForPanel(panel, source, rendered, reveal, fragment) {
  const markdownExtension = vscode.extensions.getExtension("vscode.markdown-language-features");
  const mermaidExtension = vscode.extensions.getExtension("vscode.mermaid-markdown-features");
  const config = vscode.workspace.getConfiguration("markdown", source);
  const configuredStyles = config.get("styles", []);
  const customStyles = (Array.isArray(configuredStyles) ? configuredStyles : []).map(value => styleUri(source, value)).filter(Boolean);
  const roots = [vscode.workspace.getWorkspaceFolder(source)?.uri, vscode.Uri.joinPath(source, ".."),
    context.extensionUri, markdownExtension?.extensionUri, mermaidExtension?.extensionUri,
    ...customStyles.filter(uri => typeof uri !== "string").map(uri => vscode.Uri.joinPath(uri, ".."))].filter(Boolean);
  panel.webview.options = { enableScripts: true, enableFindWidget: true, localResourceRoots: roots };
  const resource = uri => panel.webview.asWebviewUri(uri).toString();
  const builtInStyles = markdownExtension ? (markdownExtension.packageJSON?.contributes?.["markdown.previewStyles"] ||
    ["./media/markdown.css", "./media/highlight.css"]).map(file => resource(vscode.Uri.joinPath(markdownExtension.extensionUri, file))) : [];
  const userStyles = customStyles.map(uri => typeof uri === "string" ? uri : resource(uri));
  const readingStyle = resource(vscode.Uri.joinPath(context.extensionUri, "media", "reader.css"));
  const readerStyle = resource(vscode.Uri.joinPath(context.extensionUri, "media", "preview.css"));
  const readerScript = resource(vscode.Uri.joinPath(context.extensionUri, "media", "preview.js"));
  const mermaidContribution = mermaidExtension?.packageJSON?.contributes?.["markdown.previewScripts"]?.[0];
  const mermaidFile = typeof mermaidContribution === "string" ? mermaidContribution : mermaidContribution?.path;
  const mermaidScript = mermaidExtension && mermaidFile ? resource(vscode.Uri.joinPath(mermaidExtension.extensionUri, mermaidFile)) : null;
  const mermaidScriptType = typeof mermaidContribution === "object" && mermaidContribution.type === "module" ? "module" : "text/javascript";
  const base = resource(vscode.Uri.joinPath(source, ".."));
  const csp = panel.webview.cspSource;
  const state = { source: source.toString(), marks: marksFor(source), reveal: reveal?.id || null, fragment: fragment || null };
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${csp} 'unsafe-inline' https:; font-src ${csp} data:; img-src ${csp} https: data:; media-src ${csp} https: data:; script-src ${csp}; worker-src ${csp} blob:; connect-src ${csp}; frame-src 'self';"><meta name="viewport" content="width=device-width, initial-scale=1"><base href="${escapeHtml(base.endsWith("/") ? base : base + "/")}">${[...builtInStyles, ...userStyles, readingStyle, readerStyle].map(href => `<link rel="stylesheet" href="${escapeHtml(href)}">`).join("")}</head><body><div id="reading-desk-data" hidden data-state="${escapeHtml(JSON.stringify(state))}"></div><div class="reading-desk-layout"><aside class="reading-desk-sidebar" aria-label="Reading Desk sidebar"><section class="reading-desk-toc" aria-label="Contents"><div class="reading-desk-toc-head"><strong>Contents</strong></div><input class="reading-desk-toc-search" type="search" placeholder="Find heading" aria-label="Find heading"><nav class="reading-desk-toc-list" aria-label="Document headings"></nav></section><section class="reading-desk-comments" aria-label="Saved comments"></section></aside><main class="markdown-body reading-desk-content">${rendered}</main></div><script src="${escapeHtml(readerScript)}"></script>${mermaidScript ? `<script type="${mermaidScriptType}" src="${escapeHtml(mermaidScript)}"></script>` : ""}</body></html>`;
}

async function renderPanel(uri, reveal, fragment) {
  const panel = panels.get(uri.toString());
  if (!panel) return;
  const request = (panel._readingDeskRenderRequest || 0) + 1;
  panel._readingDeskRenderRequest = request;
  const document = await vscode.workspace.openTextDocument(uri);
  const mermaid = vscode.extensions.getExtension("vscode.mermaid-markdown-features");
  if (mermaid?.activate && !mermaid.isActive) await mermaid.activate();
  const rendered = await vscode.commands.executeCommand("markdown.api.render", document);
  if (panels.get(uri.toString()) !== panel || panel._readingDeskRenderRequest !== request) return;
  if (!panel._readingDeskInitialized) {
    panel.webview.html = htmlForPanel(panel, uri, rendered || "", reveal, fragment);
    panel._readingDeskInitialized = true;
  } else if (!panel._readingDeskReady) panel._pendingRendered = rendered || "";
  else panel.webview.postMessage({ type: "render", html: rendered || "", marks: marksFor(uri) });
}

async function handlePanelMessage(uri, message) {
  if (!message || typeof message !== "object") return;
  if (message.type === "ready") {
    const panel = panels.get(uri.toString());
    if (!panel) return;
    panel._readingDeskReady = true;
    if (panel._pendingRendered !== undefined) {
      panel.webview.postMessage({ type: "render", html: panel._pendingRendered, marks: marksFor(uri) });
      delete panel._pendingRendered;
    } else sendPanelState(uri);
    return;
  }
  if (message.type === "openLink" && typeof message.href === "string") {
    const href = message.href;
    if (/^(https?:|mailto:)/i.test(href)) await vscode.env.openExternal(vscode.Uri.parse(href));
    else if (!href.startsWith("#")) {
      const [rawPath, rawFragment] = href.split("#", 2);
      let fragment = rawFragment || "";
      let linkPath = rawPath;
      try { fragment = decodeURIComponent(fragment); linkPath = decodeURIComponent(linkPath); } catch {}
      const target = /^(file|vscode-remote):/i.test(linkPath) ? vscode.Uri.parse(linkPath, true) :
        !/^[a-z][a-z0-9+.-]*:/i.test(linkPath) ? vscode.Uri.joinPath(uri, "..", linkPath) : null;
      if (target && supported(target)) await openFile(target, undefined, fragment);
      else if (target) await vscode.commands.executeCommand("vscode.open", target);
    }
    return;
  }
  let changed = false;
  if (message.type === "create") changed = await createMark(uri, message.kind, message.anchor, "preview", message.note, message.id, message.color, message.important);
  else if (message.type === "update" && typeof message.id === "string") changed = await updateMark(uri, message.id, message);
  else if (message.type === "delete" && typeof message.id === "string") changed = await deleteMark(uri, message.id);
  else return;
  if (!changed) sendPanelState(uri);
  panels.get(uri.toString())?.webview.postMessage({ type: "saveResult", id: message.id, success: !!changed });
}

async function openFile(uri, reveal, fragment) {
  if (!supported(uri)) return;
  await store.loadFor(uri);
  tree.refresh();
  if (!/\.md$/i.test(uri.path)) return vscode.window.showTextDocument(uri, { preview: false });
  const key = uri.toString();
  let panel = panels.get(key);
  if (panel) {
    panel.reveal(vscode.ViewColumn.Beside);
    if (reveal) panel.webview.postMessage({ type: "reveal", id: reveal.id });
    if (fragment) panel.webview.postMessage({ type: "fragment", fragment });
    return;
  }
  panel = vscode.window.createWebviewPanel("readingDesk.reader", `Reading Desk: ${path.basename(uri.path)}`,
    vscode.ViewColumn.Beside, { enableScripts: true, enableFindWidget: true, retainContextWhenHidden: true });
  panels.set(key, panel);
  context.subscriptions.push(panel.webview.onDidReceiveMessage(message => handlePanelMessage(uri, message)));
  context.subscriptions.push(panel.onDidDispose(() => {
    panels.delete(key);
    const timer = renderTimers.get(key); if (timer) clearTimeout(timer);
    renderTimers.delete(key);
  }));
  try { await renderPanel(uri, reveal, fragment); }
  catch (error) {
    panel.dispose();
    vscode.window.showErrorMessage(`Could not render Reading Desk: ${error.message}`);
  }
}

async function openCommand(candidate) {
  let uri = candidate instanceof vscode.Uri ? candidate : vscode.window.activeTextEditor?.document.uri;
  if (!supported(uri)) {
    const chosen = await vscode.window.showOpenDialog({ filters: { "Markdown and Python": ["md", "py"] }, canSelectMany: false });
    uri = chosen?.[0];
  }
  if (uri) await openFile(uri);
}

function anchorRange(document, mark) {
  const anchor = mark.anchor;
  if (!anchor?.quote) {
    const line = Math.min(anchor?.line || 0, Math.max(0, document.lineCount - 1));
    return new vscode.Range(line, 0, line, 0);
  }
  const found = bestMatch(document.getText(), anchor);
  if (!found) return null;
  return new vscode.Range(document.positionAt(found.start), document.positionAt(found.end));
}

function refreshEditors(uri) {
  for (const editor of vscode.window.visibleTextEditors) {
    if (uri && editor.document.uri.toString() !== uri.toString()) continue;
    if (!supported(editor.document.uri)) continue;
    const marks = marksFor(editor.document.uri);
    for (const [key, decoration] of decorations) {
      const options = marks.filter(mark => decorationKey(mark) === key && !mark.resolved)
        .map(mark => {
          const range = anchorRange(editor.document, mark);
          if (!range) return null;
          const hoverMessage = new vscode.MarkdownString(`**${mark.important ? "Important " : ""}${LABELS[mark.kind]}**${mark.note ? `\n\n${mark.note}` : ""}`);
          return { range, hoverMessage, renderOptions: !mark.anchor.quote ? { after: {
            contentText: `  ${mark.kind === "later" ? "↩ Return later" : mark.kind === "review" ? "✓ For review" : "Highlight"}`,
            color: new vscode.ThemeColor("descriptionForeground"),
          } } : undefined };
        }).filter(Boolean);
      editor.setDecorations(decoration, options);
    }
  }
}

function decorationKey(mark) {
  if (mark.kind === "done") return "done";
  return `highlight.${mark.color || "green"}.${mark.important ? "important" : "regular"}`;
}

function decorationFor(key) {
  if (key === "done") return vscode.window.createTextEditorDecorationType({ opacity: "0.4" });
  const colors = {
    "highlight.yellow": ["#e5bb463b", "#e5bb46"], "highlight.green": ["#64b78540", "#64b785"],
    "highlight.red": ["#eb766044", "#eb7660"],
  };
  const color = colors[key.startsWith("highlight.") ? key.split(".").slice(0, 2).join(".") : key];
  return vscode.window.createTextEditorDecorationType({
    backgroundColor: color[0], borderRadius: "3px", overviewRulerColor: color[1],
    border: key.endsWith(".important") ? `1px solid ${color[1]}` : undefined,
    overviewRulerLane: vscode.OverviewRulerLane.Right,
  });
}

function marksAt(document, position) {
  return marksFor(document.uri).flatMap(mark => {
    const range = anchorRange(document, mark);
    return range?.contains(position) ? [{ mark, range }] : [];
  });
}

function commentHover(document, position) {
  if (!supported(document.uri)) return null;
  const matches = marksAt(document, position);
  if (!matches.length) return null;
  const body = matches.map(({ mark }) => {
    const heading = mark.kind === "highlight" ? `${mark.important ? "Important " : ""}${mark.color || "green"} highlight` : LABELS[mark.kind];
    const history = (mark.resolutionHistory || []).map(event => `Resolved: ${event.comment || "without comment"}`).join("\n\n");
    return [`**${heading}**${mark.resolved ? " · resolved" : ""}`, mark.note, history].filter(Boolean).join("\n\n");
  }).join("\n\n---\n\n");
  return new vscode.Hover(new vscode.MarkdownString(body), matches[0].range);
}

function nodeRef(node) {
  return node && node.uri && node.mark ? { uri: vscode.Uri.parse(node.uri), mark: node.mark } : null;
}

class MarksTree {
  constructor() { this.emitter = new vscode.EventEmitter(); this.onDidChangeTreeData = this.emitter.event; this.query = ""; this.kind = "all"; }
  refresh() { this.emitter.fire(); }
  setSearch(query) { this.query = query.trim().toLocaleLowerCase(); this.refresh(); }
  setKind(kind) { this.kind = kind; this.refresh(); }
  getChildren(node) {
    if (node) return [];
    return store.all().filter(({ mark, uri }) =>
      (this.kind === "all" || mark.kind === this.kind) &&
      (!this.query || [mark.file, uri.path, mark.anchor.quote, mark.note, mark.resolutionComment, LABELS[mark.kind]]
        .some(value => String(value || "").toLocaleLowerCase().includes(this.query))))
      .map(({ mark, uri }) => ({ type: "mark", uri: uri.toString(), mark }));
  }
  getTreeItem(node) {
    const { mark } = node;
    const title = (mark.note || mark.anchor.quote)?.replace(/\s+/g, " ").trim().slice(0, 75) || "Whole file";
    const item = new vscode.TreeItem(title, vscode.TreeItemCollapsibleState.None);
    item.description = `${path.basename(vscode.Uri.parse(node.uri).path)} · ${mark.color || "green"} ${mark.important ? "Important " : ""}${LABELS[mark.kind]}${mark.resolved ? " · resolved" : ""}`;
    item.tooltip = [LABELS[mark.kind], mark.anchor.quote, mark.note, ...(mark.resolutionHistory || []).map(event => `Resolved: ${event.comment || "without comment"}`)].filter(Boolean).join("\n\n");
    item.iconPath = new vscode.ThemeIcon(mark.resolved ? "check" : ICONS[mark.kind]);
    item.contextValue = mark.resolved ? "readingDesk.resolved" : mark.kind === "highlight" ? "readingDesk.highlight" : "readingDesk.open";
    item.command = { command: "readingDesk.jump", title: "Open mark", arguments: [node] };
    return item;
  }
}

async function jump(node) {
  const ref = nodeRef(node);
  if (!ref) return;
  await store.loadFor(ref.uri);
  if (/\.md$/i.test(ref.uri.path)) {
    await openFile(ref.uri, ref.mark);
    return;
  }
  const document = await vscode.workspace.openTextDocument(ref.uri);
  const editor = await vscode.window.showTextDocument(document, { preview: false });
  const range = anchorRange(document, ref.mark);
  if (range) {
    editor.selection = new vscode.Selection(range.start, range.end);
    editor.revealRange(range, vscode.TextEditorRevealType.InCenter);
    vscode.commands.executeCommand("editor.action.showHover").then(undefined, () => {});
  }
}

async function activate(extensionContext) {
  context = extensionContext;
  store = new ReviewStore(vscode);
  tree = new MarksTree();
  for (const key of ["done", ...["red", "green", "yellow"].flatMap(color => [`highlight.${color}.regular`, `highlight.${color}.important`])]) {
    decorations.set(key, decorationFor(key));
  }
  extensionContext.subscriptions.push(...decorations.values());
  extensionContext.subscriptions.push(vscode.window.registerTreeDataProvider("readingDesk.marks", tree));
  extensionContext.subscriptions.push(vscode.commands.registerCommand("readingDesk.open", openCommand));
  extensionContext.subscriptions.push(vscode.commands.registerCommand("readingDesk.showMarks", () => vscode.commands.executeCommand("workbench.view.extension.readingDesk")));
  extensionContext.subscriptions.push(vscode.commands.registerCommand("readingDesk.search", async () => {
    const query = await vscode.window.showInputBox({ prompt: "Search Reading Desk comments and passages", value: tree.query });
    if (query !== undefined) tree.setSearch(query);
  }));
  extensionContext.subscriptions.push(vscode.commands.registerCommand("readingDesk.filter", async () => {
    const choice = await vscode.window.showQuickPick([
      { label: "All comments", kind: "all" }, { label: "Return later", kind: "later" },
      { label: "For review", kind: "review" }, { label: "Highlights", kind: "highlight" }, { label: "Done", kind: "done" },
    ], { placeHolder: "Show comment type" });
    if (choice) tree.setKind(choice.kind);
  }));
  for (const kind of KINDS) extensionContext.subscriptions.push(vscode.commands.registerCommand(`readingDesk.${kind}`, () => markSelection(kind)));
  extensionContext.subscriptions.push(vscode.commands.registerCommand("readingDesk.importantHighlight", () => markSelection("highlight", { color: "red", important: true })));
  extensionContext.subscriptions.push(vscode.commands.registerCommand("readingDesk.toggleImportant", async node => {
    const ref = nodeRef(node); if (ref?.mark.kind === "highlight") await updateMark(ref.uri, ref.mark.id, { important: !ref.mark.important });
  }));
  extensionContext.subscriptions.push(vscode.commands.registerCommand("readingDesk.jump", jump));
  extensionContext.subscriptions.push(vscode.commands.registerCommand("readingDesk.editNote", async node => {
    const ref = nodeRef(node); if (!ref) return;
    const note = await vscode.window.showInputBox({ prompt: "Edit comment", value: ref.mark.note || "" });
    if (note !== undefined) await updateMark(ref.uri, ref.mark.id, { note });
  }));
  extensionContext.subscriptions.push(vscode.commands.registerCommand("readingDesk.resolve", async node => {
    const ref = nodeRef(node); if (ref) await updateMark(ref.uri, ref.mark.id, { resolved: true, resolutionComment: "" });
  }));
  extensionContext.subscriptions.push(vscode.commands.registerCommand("readingDesk.resolveWithComment", async node => {
    const ref = nodeRef(node); if (!ref) return;
    const comment = await vscode.window.showInputBox({ prompt: "Resolution comment", placeHolder: "What changed?" });
    if (comment !== undefined) await updateMark(ref.uri, ref.mark.id, { resolved: true, resolutionComment: comment });
  }));
  extensionContext.subscriptions.push(vscode.commands.registerCommand("readingDesk.reopen", async node => {
    const ref = nodeRef(node); if (ref) await updateMark(ref.uri, ref.mark.id, { resolved: false });
  }));
  extensionContext.subscriptions.push(vscode.commands.registerCommand("readingDesk.delete", async node => {
    const ref = nodeRef(node); if (ref) await deleteMark(ref.uri, ref.mark.id);
  }));
  extensionContext.subscriptions.push(vscode.window.onDidChangeVisibleTextEditors(() => refreshEditors()));
  extensionContext.subscriptions.push(vscode.languages.registerHoverProvider([{ language: "markdown" }, { language: "python" }], {
    provideHover: commentHover,
  }));
  extensionContext.subscriptions.push(vscode.window.onDidChangeTextEditorSelection(event => {
    if (event.kind !== vscode.TextEditorSelectionChangeKind.Mouse || !supported(event.textEditor.document.uri)) return;
    const selection = event.selections[0];
    if (!selection?.isEmpty || !marksAt(event.textEditor.document, selection.active).length) return;
    vscode.commands.executeCommand("editor.action.showHover").then(undefined, () => {});
  }));
  extensionContext.subscriptions.push(vscode.window.onDidChangeActiveTextEditor(editor => {
    if (editor && supported(editor.document.uri)) store.loadFor(editor.document.uri).then(() => { tree.refresh(); refreshEditors(editor.document.uri); })
      .catch(error => vscode.window.showErrorMessage(`Could not load review marks: ${error.message}`));
  }));
  extensionContext.subscriptions.push(vscode.workspace.onDidChangeTextDocument(event => {
    if (!supported(event.document.uri)) return;
    refreshEditors(event.document.uri);
    if (/\.md$/i.test(event.document.uri.path) && panels.has(event.document.uri.toString())) {
      const key = event.document.uri.toString();
      clearTimeout(renderTimers.get(key));
      renderTimers.set(key, setTimeout(() => renderPanel(event.document.uri).catch(error =>
        vscode.window.showErrorMessage(`Could not render Reading Desk: ${error.message}`)), 250));
    }
  }));
  extensionContext.subscriptions.push(vscode.workspace.onDidOpenTextDocument(document => {
    if (supported(document.uri)) store.loadFor(document.uri).then(() => {
      tree.refresh(); refreshEditors(document.uri);
      sendPanelState(document.uri);
    }).catch(error => vscode.window.showErrorMessage(`Could not load review marks: ${error.message}`));
  }));
  const watcher = vscode.workspace.createFileSystemWatcher("**/.reading-desk/reviews.json");
  extensionContext.subscriptions.push(watcher);
  const reload = async uri => {
    try {
      await store.loadRoot(vscode.Uri.joinPath(uri, "..", ".."), true);
      tree.refresh(); refreshEditors();
      for (const key of panels.keys()) sendPanelState(vscode.Uri.parse(key));
    } catch (error) { vscode.window.showErrorMessage(`Could not load review marks: ${error.message}`); }
  };
  extensionContext.subscriptions.push(watcher.onDidChange(reload), watcher.onDidCreate(reload), watcher.onDidDelete(reload));
  try {
    await store.loadWorkspace();
    if (vscode.window.activeTextEditor && supported(vscode.window.activeTextEditor.document.uri)) {
      await store.loadFor(vscode.window.activeTextEditor.document.uri);
    }
    tree.refresh(); refreshEditors();
  } catch (error) { vscode.window.showErrorMessage(`Could not load review marks: ${error.message}`); }
  refreshEditors();
}

function deactivate() {}
module.exports = { activate, deactivate, bestMatch, escapeHtml, validatedAnchor };
