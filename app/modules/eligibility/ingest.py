"""Law corpus ingestion (M16). Currently ingests ONE article — Article 2
(definitions) of the Federal Public Procurement and Property Administration
Proclamation No. 1333/2024 — from the real, official PDF published by PPA
(the regulator itself), not a third-party copy.

WHY ONLY ARTICLE 2, HONESTLY: the source PDF is bilingual (Amharic first,
matching English second, per page) and 100 pages long. Article 2's
definitions extract cleanly with a simple, reliable pattern (`NN/ "Term"
means ...;`) verified against the real document. The articles that actually
govern bidder eligibility (bidding methods, participation restrictions by
bidder nationality, etc.) are later in the document and were NOT verified to
extract this cleanly during this session -- getting a citation wrong is worse
than not having one (NFR-LEGAL-1), so they are deliberately not ingested yet
rather than rushed. Extending this corpus is real, scoped follow-up work.

KNOWN ISSUE, documented not hidden: ppa.gov.et serves an incomplete TLS
certificate chain (found independently this session, also noted in
docs/SECURITY.md as a responsible-disclosure candidate) -- `verify=False`
below is a narrow, explicit workaround for that specific, already-known
issue on a public government document, not a general practice.
"""

import re
from typing import Any

import httpx

PPA_PDF_URL = "https://www.ppa.gov.et/wp-content/uploads/2024/10/Procurement-and-property-proclamation-2024-.pdf"
DOCUMENT_NAME = "Federal Public Procurement and Property Administration Proclamation No. 1333/2024"

# English definitions follow this exact pattern in the extracted text,
# verified against the real PDF: `NN/ "Term" means ...;`. This reliably skips
# the interleaved Amharic text (which never matches a Latin-letter pattern)
# without needing script-classification.
_DEFINITION_RE = re.compile(r'(\d+)/\s*[“"]([^”"]+)[”"]\s+means\s+(.*?);', re.IGNORECASE)


_GE_EZ_RANGE = range(0x1200, 0x1380)


def parse_definitions(flat_text: str) -> list[tuple[str, str]]:
    """Pure function: whitespace-flattened extracted text ->
    [(article_ref, text_en), ...]. Unit-tested against a saved real
    extraction, no PDF library or network needed (SKILLS.md R6).

    Two real entries (Article 2(4), 2(38)) were found, live, to swallow an
    entire intervening Amharic block: their true terminator in the source PDF
    apparently isn't the plain ASCII `;` the regex looks for, so the
    non-greedy match kept expanding across a page boundary until the next
    one. Rather than add more regex cleverness that could still be wrong in a
    way that's hard to notice, any match containing Ge'ez-script characters
    is dropped outright -- a missing definition is honest; a garbled one
    silently entering the law corpus is the actual NFR-LEGAL-1 violation."""
    out: list[tuple[str, str]] = []
    for num, term, definition in _DEFINITION_RE.findall(flat_text):
        text_en = f'"{term}" means {definition.strip()}.'
        if any(ord(ch) in _GE_EZ_RANGE for ch in text_en):
            continue
        out.append((f"Article 2({num})", text_en))
    return out


def extract_definitions(pdf_bytes: bytes, pages: int = 9) -> list[tuple[str, str]]:
    """PDF bytes -> [(article_ref, text_en), ...]. Thin wrapper around
    `parse_definitions`; the PDF-reading half needs a real PDF and isn't
    unit-tested directly (SKILLS.md R6 — that's an integration concern)."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(pdf_bytes)
    text = "\n".join(pdf[i].get_textpage().get_text_range() for i in range(min(pages, len(pdf))))
    flat = re.sub(r"\s+", " ", text)
    return parse_definitions(flat)


async def fetch_proclamation_pdf() -> bytes:
    async with httpx.AsyncClient(verify=False, timeout=30) as client:  # noqa: S501 -- see module docstring
        resp = await client.get(PPA_PDF_URL)
        resp.raise_for_status()
        return resp.content


async def seed_law_corpus(session: Any, kernel_embed: Any) -> int:
    """Idempotent: skips article_refs already present. `kernel_embed` is
    `app.kernel.embeddings.embed_texts` — passed in rather than imported
    directly so this stays testable without pulling in the embeddings model."""
    from sqlalchemy import select

    from app.modules.eligibility.models import LawChunk

    pdf_bytes = await fetch_proclamation_pdf()
    definitions = extract_definitions(pdf_bytes)

    existing = {
        row[0]
        for row in (
            await session.execute(
                select(LawChunk.article_ref).where(LawChunk.document_name == DOCUMENT_NAME)
            )
        ).all()
    }
    new_defs = [(ref, text) for ref, text in definitions if ref not in existing]
    if not new_defs:
        return 0

    embeddings = kernel_embed([text for _, text in new_defs])
    for (article_ref, text_en), embedding in zip(new_defs, embeddings, strict=True):
        session.add(
            LawChunk(
                document_name=DOCUMENT_NAME,
                document_url=PPA_PDF_URL,
                article_ref=article_ref,
                text_en=text_en,
                embedding=embedding,
            )
        )
    await session.commit()
    return len(new_defs)
