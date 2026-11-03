# Reading Desk requirements

## Goal

Review Markdown and Python files with lightweight, persistent annotations. The
extension must not replace VS Code's Markdown or Python renderer, or edit a
source file when an annotation is made.

## Reading experience

1. **Open Reading Desk** opens Markdown in an extension-owned reading pane. It
   uses VS Code's built-in Markdown renderer, built-in preview CSS, Mermaid
   support, and configured `markdown.styles`. Markdown syntax, images, links,
   and contents tables remain readable. VS Code's native Markdown preview is
   left untouched and remains available. Python opens in its native editor,
   with syntax highlighting and language tools.
   The reading pane uses a 46rem text column with the supplied minimal theme
   styling and a searchable Contents sidebar built from rendered headings.
   Saved comments sit directly below the Contents index in the same sidebar,
   with their own search, type filter, and scrollable list. The comments list
   remains available while reading and never covers the Markdown page.
   A **Sidebar** toolbar button collapses or expands the whole sidebar, and the
   pane remembers the choice. Document elements that `markdown.styles` makes
   fixed, or sticky outside the text column, stay in the text column so they
   never cover the sidebar at any width.
2. Selecting rendered Markdown or source text offers **Highlight**, **Done**, **Return
   later**, and **For review** as modes for one **Add mark** action. **Return
   later** is selected initially. The selected color is green initially, remains
   visibly pressed, and can be changed to yellow or red. **Important** is a
   separate toggle for highlights. **Done** marks selected text as finished and
   shows it greyed out with a strikethrough; it needs selected text and takes no
   required comment, and resolving or deleting it restores the text. Return later and For review are comment
   types; a whole-file comment requires an explicit choice from the source
   editor, never an accidental empty reading-pane selection.
3. Saved passages are colored inline in the reading pane or Python editor,
   using their chosen red, green, or yellow color. Clicking a marked passage in
   the reading pane reveals its comment beside the passage, with edit and resolution
   actions. Clicking or hovering over a source editor mark exposes its comment;
   all comments also remain in Reading Desk. Controls must not change diagram rendering, links, source highlighting,
   or the user's CSS. Comments live in Reading Desk's own list; they do not open
   VS Code's global Comments view.
4. A compact review panel lists comments across files with the newest first.
   Search matches text, file, and comment content; a type filter shows Return
   later, For review, Done, or highlights. It supports navigation to a passage,
   comment editing, resolution, reopening, and deletion. Editor context menus
   and the Command Palette expose the same creation actions for keyboard use.
5. Creating or editing a mark must not open or briefly flash another window,
   or open a floating Saved comments panel over the document. Saving a mark
   updates the sidebar list in place without changing the reader layout.
   The reading pane sends actions directly to the extension host and receives a
   save result. Comment entry and review happen inline; the separate review
   panel is for searching and scanning all comments at once.

## Annotation rules

1. **Highlight** identifies text worth seeing again, and its important flag
   identifies a key passage. **Return later** is a personal place to resume;
   **For review** is an item to revisit deliberately. Every annotation can have
   an editable comment, including a comment added after the mark is created.
2. Comments and marks are saved locally in a separate, readable JSON file at
   `.reading-desk/reviews.json` in each workspace folder. For a file opened
   outside a workspace, use that file's parent folder. The array is written in
   reverse chronological order and includes each annotation's relative file
   path. Every create, edit, resolve, reopen, and delete action is saved
   immediately through VS Code's file API, with no manual save step. Source
   Markdown and Python files are never modified by annotation actions.
3. A quote with nearby text and approximate position anchors a passage after
   modest source edits. If the quote disappears, the annotation remains in the
   review list as an unlocated item instead of attaching to the wrong text.
4. Comments and marks can be resolved without a comment or resolved with a
   closing comment. Reopening preserves the original comment and resolution
   history, including previous closing comments. Comments can be edited; all
   entries can be removed.

## Implementation and verification

- Package as a standalone VSIX with no runtime Python, Wyndle server, or npm
  dependencies. It must coexist with the Wyndle and Full Focus Timers extensions.
- Render Markdown through `markdown.api.render` and load the built-in Markdown
  and Mermaid assets in the reading pane. Use webview messages for saves and
  state updates; use editor decorations and selection commands for Python.
  Native Markdown preview and Python language tooling remain untouched.
- Verify anchoring and local file storage behavior with automated tests, then package
  and inspect the VSIX. Document installation and use in this extension's README
  and the shared Wyndle guide, and regenerate the Pages HTML.
