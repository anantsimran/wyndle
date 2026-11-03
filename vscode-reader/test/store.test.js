"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { ReviewStore } = require("../store");

class Uri {
  constructor(scheme, authority, uriPath) { this.scheme = scheme; this.authority = authority; this.path = uriPath; }
  toString() { return `${this.scheme}://${this.authority}${this.path}`; }
  static joinPath(uri, ...parts) { return new Uri(uri.scheme, uri.authority, path.posix.resolve(uri.path, ...parts)); }
}

function harness() {
  const files = new Map();
  const workspaceRoot = new Uri("vscode-remote", "ssh-remote+example", "/work/project");
  const api = { Uri, workspace: {
    workspaceFolders: [{ uri: workspaceRoot }],
    getWorkspaceFolder(uri) { return uri.path.startsWith(workspaceRoot.path + "/") ? { uri: workspaceRoot } : undefined; },
    fs: {
      async readFile(uri) {
        if (!files.has(uri.toString())) { const error = new Error("not found"); error.code = "FileNotFound"; throw error; }
        return files.get(uri.toString());
      },
      async createDirectory() {},
      async writeFile(uri, bytes) { files.set(uri.toString(), bytes); },
      async rename(from, to) { files.set(to.toString(), files.get(from.toString())); files.delete(from.toString()); },
    },
  } };
  return { files, api, root: workspaceRoot, store: new ReviewStore(api) };
}

test("remote workspace saves a separate JSON file with newest marks first", async () => {
  const { files, root, store } = harness();
  const source = Uri.joinPath(root, "notes", "guide.md");
  await store.loadWorkspace();
  await store.change(source, (marks, file) => {
    marks.push({ id: "older", file, kind: "review", anchor: { quote: "" }, note: "Check this", created: "2026-01-01T00:00:00Z" });
    return true;
  });
  await store.change(source, (marks, file) => {
    marks.push({ id: "newer", file, kind: "highlight", anchor: { quote: "one" }, color: "green", created: "2026-02-01T00:00:00Z" });
    return true;
  });
  const saved = JSON.parse(files.get(store.fileForRoot(root).toString()).toString());
  assert.deepEqual(saved.marks.map(mark => mark.id), ["newer", "older"]);
  assert.equal(saved.marks[0].file, "notes/guide.md");
  assert.equal(saved.marks[1].note, "Check this");
  assert.equal(store.all()[0].uri.toString(), source.toString());
  assert.equal(files.has(source.toString()), false);
});

test("resolution comment survives reopening and edits save immediately", async () => {
  const { files, root, store } = harness();
  const source = Uri.joinPath(root, "review.py");
  await store.change(source, (marks, file) => { marks.push({ id: "a", file, kind: "review", anchor: { quote: "" }, note: "Original", created: "2026-02-01" }); return true; });
  await store.change(source, marks => { Object.assign(marks[0], { resolved: true, resolutionComment: "Fixed in the next pass" }); return true; });
  await store.change(source, marks => { marks[0].resolved = false; return true; });
  const saved = JSON.parse(files.get(store.fileForRoot(root).toString()).toString());
  assert.equal(saved.marks[0].resolved, false);
  assert.equal(saved.marks[0].note, "Original");
  assert.equal(saved.marks[0].resolutionComment, "Fixed in the next pass");
});

test("invalid review JSON is never overwritten", async () => {
  const { files, root, store } = harness();
  const target = store.fileForRoot(root).toString();
  files.set(target, Buffer.from("{bad json"));
  await assert.rejects(store.change(Uri.joinPath(root, "readme.md"), () => true), SyntaxError);
  assert.equal(files.get(target).toString(), "{bad json");
});

test("failed autosave restores cached comments instead of showing an unsaved edit", async () => {
  const { files, root, store, api } = harness();
  const source = Uri.joinPath(root, "review.py");
  await store.change(source, (marks, file) => {
    marks.push({ id: "a", file, kind: "later", anchor: { quote: "text" }, note: "Original", created: "2026-02-01" });
    return true;
  });
  const target = store.fileForRoot(root).toString();
  api.workspace.fs.rename = async () => { throw new Error("disk unavailable"); };
  await assert.rejects(store.change(source, marks => { marks[0].note = "Unsaved"; return true; }), /disk unavailable/);
  assert.equal(store.forFile(source)[0].note, "Original");
  assert.equal(JSON.parse(files.get(target).toString()).marks[0].note, "Original");
});
