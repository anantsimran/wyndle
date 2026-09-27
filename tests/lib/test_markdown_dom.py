from wyndle.lib.markdown_dom import (
    HeadingBlock,
    MarkdownDoc,
    parse_added_date,
    parse_estimate,
    parse_status_tag,
    strip_all_metadata,
    strip_estimate,
)

DOC = """---
date: 2026-04-07
tags: [a, b]
---
preamble line
# Title
## Task Details
### Auth
- [ ] Read docs ~30m
  - note one
    - nested note
- [x] Ship it
### Auth refactor
- [ ] Split module ~45m
## Log
"""


def test_inline_metadata_helpers():
    assert parse_estimate("Read ~30m") == 30
    assert parse_estimate("no estimate") == 0
    assert strip_estimate("Read docs ~30m") == "Read docs"
    assert parse_status_tag("Task ~future more") == ("Task more", "future")
    assert parse_status_tag("plain") == ("plain", "")
    assert parse_added_date("X (added: 2026-04-01)") == ("X", "2026-04-01")
    assert strip_all_metadata("X ~15m ~done (added: 2026-04-01)") == "X"


def test_roundtrip_is_lossless():
    assert MarkdownDoc(DOC).serialize() == DOC


def test_frontmatter_and_preamble():
    doc = MarkdownDoc(DOC)
    assert doc.frontmatter.data == {"date": "2026-04-07", "tags": ["a", "b"]}
    assert doc.preamble == ["preamble line"]


def test_find_subsection_is_exact_and_case_insensitive():
    doc = MarkdownDoc(DOC)
    details = doc.find_section("Task Details", level=2)
    assert doc.find_subsection(details, "Auth refactor").title == "Auth refactor"
    assert doc.find_subsection(details, " auth ").title == "Auth"
    assert doc.find_subsection(details, "refactor") is None
    assert doc.find_subsection(details, "Auth refactor v2") is None


def test_checkboxes_and_notes():
    doc = MarkdownDoc(DOC)
    auth = doc.find_section("Auth", level=3)
    assert doc.get_checkboxes(auth) == [(0, False, "Read docs ~30m"), (3, True, "Ship it")]
    assert doc.get_checkbox_notes(auth) == {
        "Read docs": ["note one", "nested note"],
        "Ship it": [],
    }


def test_nested_notes_tree():
    doc = MarkdownDoc(DOC)
    auth = doc.find_section("Auth", level=3)
    tree = doc.get_nested_notes(auth)
    assert [n.text for n in tree] == ["[ ] Read docs ~30m", "[x] Ship it"]
    assert tree[0].children[0].text == "note one"
    assert tree[0].children[0].children[0].text == "nested note"


def test_insert_and_remove_respect_nesting():
    doc = MarkdownDoc(DOC)
    details = doc.find_section("Task Details", level=2)
    new = HeadingBlock(level=2, title="Notes", heading_line="## Notes")
    doc.insert_after(details, new)
    titles = [b.title for b in doc.blocks]
    assert titles.index("Notes") == titles.index("Auth refactor") + 1

    doc.remove_subsection(details)
    assert [b.title for b in doc.blocks] == ["Title", "Notes", "Log"]
