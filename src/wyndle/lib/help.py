"""One packaged guide for the dashboard and terminal help."""

from importlib.resources import files

import click
from markdown_it import MarkdownIt


def guide_markdown() -> str:
    """Return the packaged ``HOW_TO_USE.md`` guide as Markdown text."""
    return files("wyndle.web").joinpath("HOW_TO_USE.md").read_text(encoding="utf-8")


def help_content() -> dict[str, str]:
    """Build the dashboard help payload.

    Returns:
        ``guideHtml``: the guide rendered to HTML; ``cliHelp``: ``wyndle --help`` text.
    """
    # Import lazily: CLI registration also uses guide_markdown.
    from wyndle.cli import main

    with click.Context(main, info_name="wyndle") as context:
        cli = main.get_help(context)
    # Only our packaged guide is rendered. Raw HTML and unsafe links are disabled.
    return {"guideHtml": MarkdownIt("commonmark", {"html": False}).render(guide_markdown()),
            "cliHelp": cli}
