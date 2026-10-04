"""Render the shared Wyndle how-to guide as a static GitHub Pages site."""

import argparse
import html
import re
import unicodedata
from pathlib import Path

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "src/wyndle/web/HOW_TO_USE.md"
TEMPLATE = ROOT / "scripts/guide-template.html"
OUTPUT = ROOT / "docs/index.html"


def slugify(title: str) -> str:
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-") or "section"


def render_page() -> str:
    lines = GUIDE.read_text(encoding="utf-8").splitlines()
    if not lines or not lines[0].startswith("# "):
        raise ValueError("The how-to guide must start with a Markdown title")
    first_section = next((i for i, line in enumerate(lines) if line.startswith("## ")), None)
    if first_section is None:
        raise ValueError("The how-to guide must contain at least one section")

    title = lines[0][2:]
    intro = "\n".join(lines[1:first_section]).strip()
    body = "\n".join(lines[first_section:]) + "\n"
    markdown = MarkdownIt("commonmark", {"html": False})
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

    contents = "\n".join(
        f'<li><a href="#{html.escape(anchor, quote=True)}">{html.escape(label)}</a></li>'
        for anchor, label in headings
    )
    replacements = {
        "{{PAGE_TITLE}}": html.escape(title),
        "{{INTRO}}": markdown.render(intro),
        "{{CONTENTS}}": contents,
        "{{GUIDE_CONTENT}}": markdown.renderer.render(tokens, markdown.options, {}),
    }
    page = TEMPLATE.read_text(encoding="utf-8")
    for placeholder, value in replacements.items():
        expected = 2 if placeholder == "{{PAGE_TITLE}}" else 1
        if page.count(placeholder) != expected:
            raise ValueError(f"Expected {expected} {placeholder} markers in the page template")
        page = page.replace(placeholder, value)
    return page


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if docs/index.html is stale")
    args = parser.parse_args()
    page = render_page()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != page:
            parser.exit(1, "docs/index.html is stale; run python scripts/build_guide.py\n")
        return
    OUTPUT.write_text(page, encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
