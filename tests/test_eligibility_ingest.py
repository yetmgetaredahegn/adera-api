"""Law-corpus parsing, tested against real extracted text from the official
PPA PDF (Proclamation No. 1333/2024) — no network, no PDF library needed
(SKILLS.md R6). The fixture is the real flattened text of Article 2
(definitions), extracted once and saved; this is how the regex is pinned."""

from pathlib import Path

from app.modules.eligibility.ingest import DOCUMENT_NAME, parse_definitions

FIXTURE = Path(__file__).parent / "fixtures" / "proclamation_1333_2024_article2_flat.txt"


def _flat_text() -> str:
    # Explicit encoding: the fixture is UTF-8 (it carries real Ge'ez-script
    # text), and `Path.read_text()` with no encoding falls back to the
    # platform's locale default -- cp1252 on Windows -- which raises
    # UnicodeDecodeError on this file. Found running the suite on Windows.
    return FIXTURE.read_text(encoding="utf-8")


def test_parse_definitions_finds_thirty_eight() -> None:
    """Pinned count from the real document: 40 raw regex matches, minus 2
    (Article 2(4), 2(38)) dropped because they swallowed an intervening
    Amharic block across a page boundary — see parse_definitions' docstring.
    If this changes, the regex or the source text changed; investigate,
    don't just bump the number."""
    defs = parse_definitions(_flat_text())
    assert len(defs) == 38


def test_parse_definitions_article_refs_are_well_formed() -> None:
    defs = parse_definitions(_flat_text())
    for article_ref, _ in defs:
        assert article_ref.startswith("Article 2(")
        assert article_ref.endswith(")")


def test_parse_definitions_first_entry_is_procurement() -> None:
    """Spot-check against the real, known first definition in the real
    document — catches a silent regex regression a bare count wouldn't."""
    defs = parse_definitions(_flat_text())
    article_ref, text = defs[0]
    assert article_ref == "Article 2(1)"
    assert text.startswith('"Procurement" means')
    assert "purchase" in text.lower()


def test_parse_definitions_no_amharic_leaked_into_english_text() -> None:
    """The whole point of this regex approach: it must never accidentally
    capture Ge'ez-script content as if it were the English definition."""
    defs = parse_definitions(_flat_text())
    ge_ez_range = range(0x1200, 0x1380)
    for _, text in defs:
        assert not any(ord(ch) in ge_ez_range for ch in text)


def test_document_name_is_the_real_proclamation() -> None:
    assert "1333/2024" in DOCUMENT_NAME


def test_parse_definitions_drops_the_two_known_corrupted_entries() -> None:
    """Pins the specific failure this session found live: items 4 and 38
    must be absent, not present-but-garbled."""
    defs = parse_definitions(_flat_text())
    refs = {ref for ref, _ in defs}
    assert "Article 2(4)" not in refs
    assert "Article 2(38)" not in refs
