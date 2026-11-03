"use strict";

const path = require("node:path");

class ReviewStore {
  constructor(vscode) {
    this.vscode = vscode;
    this.cache = new Map();
    this.queue = Promise.resolve();
  }

  rootFor(uri) {
    return this.vscode.workspace.getWorkspaceFolder(uri)?.uri || this.vscode.Uri.joinPath(uri, "..");
  }

  fileForRoot(root) {
    return this.vscode.Uri.joinPath(root, ".reading-desk", "reviews.json");
  }

  relative(root, uri) {
    return path.posix.relative(root.path, uri.path);
  }

  async loadRoot(root, force = false) {
    const key = root.toString();
    if (!force && this.cache.has(key)) return this.cache.get(key);
    let marks = [];
    try {
      const bytes = await this.vscode.workspace.fs.readFile(this.fileForRoot(root));
      const parsed = JSON.parse(Buffer.from(bytes).toString("utf8"));
      if (parsed.version !== 1 || !Array.isArray(parsed.marks)) throw new Error("Unsupported review file format");
      if (parsed.marks.some(mark => !mark || typeof mark.file !== "string" || typeof mark.id !== "string" ||
        !mark.file || mark.file.startsWith("/") || path.posix.normalize(mark.file).startsWith("../") ||
        !/\.(md|py)$/i.test(mark.file) || !mark.anchor || typeof mark.anchor.quote !== "string" ||
        !["highlight", "later", "review"].includes(mark.kind))) throw new Error("Invalid review file entry");
      marks = parsed.marks;
    } catch (error) {
      if (error.code !== "FileNotFound" && error.code !== "ENOENT") throw error;
    }
    marks.sort((a, b) => String(b.created || "").localeCompare(String(a.created || "")));
    this.cache.set(key, { root, marks });
    return this.cache.get(key);
  }

  async loadFor(uri, force = false) { return this.loadRoot(this.rootFor(uri), force); }

  async loadWorkspace() {
    await Promise.all((this.vscode.workspace.workspaceFolders || []).map(folder => this.loadRoot(folder.uri)));
  }

  forFile(uri) {
    const root = this.rootFor(uri);
    const data = this.cache.get(root.toString());
    if (!data) return [];
    const file = this.relative(root, uri);
    return data.marks.filter(mark => mark.file === file);
  }

  all() {
    return [...this.cache.values()].flatMap(({ root, marks }) => marks.map(mark => ({
      mark, uri: this.vscode.Uri.joinPath(root, mark.file),
    }))).sort((a, b) => String(b.mark.created || "").localeCompare(String(a.mark.created || "")));
  }

  change(uri, mutate) {
    this.queue = this.queue.catch(() => {}).then(async () => {
      const root = this.rootFor(uri);
      const data = await this.loadRoot(root, true);
      const file = this.relative(root, uri);
      const previous = data.marks.map(mark => JSON.parse(JSON.stringify(mark)));
      if (!mutate(data.marks, file)) return false;
      data.marks.sort((a, b) => String(b.created || "").localeCompare(String(a.created || "")));
      try {
        const folder = this.vscode.Uri.joinPath(root, ".reading-desk");
        await this.vscode.workspace.fs.createDirectory(folder);
        const target = this.fileForRoot(root);
        const temporary = this.vscode.Uri.joinPath(folder, "reviews.json.tmp");
        const bytes = Buffer.from(JSON.stringify({ version: 1, marks: data.marks }, null, 2) + "\n", "utf8");
        await this.vscode.workspace.fs.writeFile(temporary, bytes);
        await this.vscode.workspace.fs.rename(temporary, target, { overwrite: true });
      } catch (error) {
        data.marks = previous;
        throw error;
      }
      return true;
    });
    return this.queue;
  }
}

module.exports = { ReviewStore };
