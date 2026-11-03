# Reading Desk

A standalone VS Code extension for reviewing Markdown and Python. It adds
highlights, done (greyed-out) text, return-later comments, review comments, and a recent-first review
list. The [requirements](REQUIREMENTS.md) describe the intended behavior.

Reading Desk opens Markdown in its own reading pane. It uses VS Code's Markdown
renderer, built-in Mermaid support, built-in Markdown CSS, and your
`markdown.styles`. A collapsible Contents sidebar indexes rendered headings and
keeps the saved comments list below the index. Document elements that a style
pins with fixed positioning stay in the text column, so they never cover the
sidebar. VS Code's
native Markdown preview remains untouched and available. Python stays in its
normal syntax-highlighted editor.

## Use

1. Open an `.md` or `.py` file and run **Reading Desk: Open Reading Desk**. The
   Markdown reading pane has a searchable **Contents** sidebar and controls at
   the bottom. In Python, select code and use the editor context menu or Command
   Palette.
2. Select a passage. In the Markdown reading pane, **Later** is selected initially.
   Choose **Review**, **Highlight**, or **Done** to change the mark type.
   **Done** greys out and strikes through the passage; resolve or delete the
   mark to restore it. Green is the
   initial color; yellow and red are available, and **★ Important** applies to
   highlights. Choose **+ Add mark** and enter an optional comment in the
   small inline form. For Python, **Highlight Selection** lets you choose a
   color and importance; **Mark as Done** greys out the selection without a prompt;
   Later and Review prompt for a comment.
   To mark a whole file, run Later or Review in the source editor with no
   selection and explicitly choose **Mark whole file**.
3. Saved passages are colored in the reading pane and source editor. Click a
   marked passage to see its comment beside the text; click or hover over a mark
   in the source editor to read its comment. **Saved comments** stays below
   **Contents** in the reading pane, and saving a mark updates the list without
   opening an overlay. Use **Comments** on the toolbar to focus its search.
   **Sidebar** on the toolbar hides or shows the whole sidebar, and the pane
   remembers the choice.
   The **Reading Desk** activity-bar icon scans entries across files. Both lists
   support searching, type filters, editing, resolution, reopening, and deletion;
   the reading-pane list shows the current file, newest first.

All changes are saved immediately to `.reading-desk/reviews.json` in the
workspace folder. With multiple workspace folders, each folder gets its own
file. Without a workspace, the file goes in a `.reading-desk` folder beside the
open source file. Source Markdown and Python files are not changed by review
actions. The JSON file can be kept in Git if you want to share comments.

The review file is written through VS Code's file API. Reading pane actions save
directly through the extension host; they do not open another window. In Remote
SSH, install Reading Desk on the SSH host; `.reading-desk/reviews.json` is saved in the remote
workspace. The extension does not need the Wyndle server, Python at runtime, or
npm packages.

## Install

From the repository root:

```sh
python3 vscode-reader/package.py
code --install-extension vscode-reader/dist/reading-desk-0.1.2.vsix --force
```

If `code` is unavailable, run **Extensions: Install from VSIX…** and select the
generated file. In a Remote SSH window, choose **Install in SSH: [host]** for
this workspace extension. Reload the window after installing if a Markdown
reading pane was already open.

## Develop

The extension has no npm dependencies or build step. Run tests with Node.js 16
or newer, then package with Python 3:

```sh
cd vscode-reader
node --test test/*.test.js
python3 package.py
```

To try the source in an Extension Development Host:

```sh
code --extensionDevelopmentPath="$PWD/vscode-reader"
```
