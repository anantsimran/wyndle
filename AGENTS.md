# Repository guidance

- Keep Obsidian Markdown parsing and file operations in `src/wyndle/lib/`. They must work without the web server or browser UI.
- Keep `src/wyndle/web/` for browser presentation. It consumes API data and does not interpret or modify Markdown files directly.
- Keep `src/wyndle/commands/ui.py` as a thin HTTP adapter. Put shared note rules in library modules so the CLI and web use the same behavior.
- `src/wyndle/lib/dashboard.py` coordinates stateful dashboard actions; Markdown format and history rules belong in the note libraries.
- Reduce files only when the merged code has one clear responsibility. Preserve the Markdown file formats and existing CLI and web behavior.
