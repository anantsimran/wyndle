"""Render the Wyndle guide, README, and requirements as static Pages files."""

import argparse
import html
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "src/wyndle/web/HOW_TO_USE.md"
TEMPLATE = ROOT / "scripts/guide-template.html"
DOCUMENT_TEMPLATE = ROOT / "scripts/document-template.html"
PAGES = {
    "src/wyndle/web/HOW_TO_USE.md": "index.html",
    "README.md": "get-started.html",
    "REQUIREMENTS.md": "requirements.html",
    "vscode-timers/REQUIREMENTS.md": "timers-requirements.html",
    "vscode-reader/REQUIREMENTS.md": "reading-desk-requirements.html",
}
GITHUB_FILES = "https://github.com/anantsimran/wyndle/blob/main/"


def slugify(title: str) -> str:
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-") or "section"


def rewrite_links(tokens, source: Path) -> None:
    for token in tokens:
        if not token.children:
            continue
        for child in token.children:
            if child.type != "link_open":
                continue
            href = child.attrGet("href") or ""
            parsed = urlsplit(href)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            try:
                target = (source.parent / unquote(parsed.path)).resolve().relative_to(ROOT)
            except ValueError:
                continue
            relative = target.as_posix()
            destination = PAGES.get(relative, GITHUB_FILES + relative)
            child.attrSet("href", destination + (f"#{parsed.fragment}" if parsed.fragment else ""))


def markdown_sections(source: Path):
    lines = source.read_text(encoding="utf-8").splitlines()
    if not lines or not lines[0].startswith("# "):
        raise ValueError(f"{source} must start with a Markdown title")
    first_section = next((i for i, line in enumerate(lines) if line.startswith("## ")), None)
    if first_section is None:
        raise ValueError(f"{source} must contain at least one section")

    title = lines[0][2:]
    intro = "\n".join(lines[1:first_section]).strip()
    body = "\n".join(lines[first_section:]) + "\n"
    markdown = MarkdownIt("commonmark", {"html": False})
    intro_tokens = markdown.parse(intro)
    tokens = markdown.parse(body)
    headings = []
    used_ids = set()
    for index, token in enumerate(tokens):
        if token.type != "heading_open" or token.tag != "h2":
            continue
        label = tokens[index + 1].content
        base = slugify(label)
        anchor = base
        suffix = 2
        while anchor in used_ids:
            anchor = f"{base}-{suffix}"
            suffix += 1
        used_ids.add(anchor)
        token.attrSet("id", anchor)
        headings.append((anchor, label))

    rewrite_links(intro_tokens, source)
    rewrite_links(tokens, source)

    contents = "\n".join(
        f'<li><a href="#{html.escape(anchor, quote=True)}">{html.escape(label)}</a></li>'
        for anchor, label in headings
    )
    return (title, markdown.renderer.render(intro_tokens, markdown.options, {}),
            contents, markdown.renderer.render(tokens, markdown.options, {}))


def fill_template(template: Path, title: str, intro: str, contents: str, body: str) -> str:
    replacements = {
        "{{PAGE_TITLE}}": html.escape(title),
        "{{INTRO}}": intro,
        "{{CONTENTS}}": contents,
        "{{GUIDE_CONTENT}}": body,
    }
    page = template.read_text(encoding="utf-8")
    for placeholder, value in replacements.items():
        expected = 2 if placeholder == "{{PAGE_TITLE}}" else 1
        if page.count(placeholder) != expected:
            raise ValueError(f"Expected {expected} {placeholder} markers in the page template")
        page = page.replace(placeholder, value)
    return page


def render_page(source: Path = GUIDE) -> str:
    title, intro, contents, body = markdown_sections(source)
    template = TEMPLATE if source == GUIDE else DOCUMENT_TEMPLATE
    return fill_template(template, title, intro, contents, body)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="fail if a generated Pages file is stale"
    )
    args = parser.parse_args()
    stale = []
    for source_name, output_name in PAGES.items():
        output = ROOT / "docs" / output_name
        page = render_page(ROOT / source_name)
        if args.check:
            if not output.exists() or output.read_text(encoding="utf-8") != page:
                stale.append(output_name)
        else:
            output.write_text(page, encoding="utf-8")
            print(f"Wrote {output.relative_to(ROOT)}")
    if stale:
        parser.exit(
            1, f"Stale Pages files: {', '.join(stale)}; run python scripts/build_guide.py\n"
        )


if __name__ == "__main__":
    main()
