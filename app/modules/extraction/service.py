"""Extraction service (M4, FR-4.1/4.2).

Two paths, chosen by whether the source is structured:

- Structured sources (SourceType.API, e.g. World Bank): the adapter already mapped
  clean fields onto the tender. Extraction is deterministic and free — "deterministic
  parsers where the source is structured" (FR-4.2). No LLM call.

- Unstructured sources (HTML/PDF, e.g. e-GP later): send the document text through
  the kernel with prompt B1, validate into TenderExtraction, one repair retry, else
  route to human review (FR-4.4). This path is built and ready; it needs an LLM key
  and a source that produces raw document text (a later week).
"""

from app.kernel.router import Kernel
from app.modules.extraction.schemas import TenderExtraction
from app.modules.ingestion.models import Tender
from app.modules.sources.models import Source, SourceType

PROMPT_VERSION = "v1"


def _deterministic(tender: Tender) -> TenderExtraction:
    """Structured source: fields are already on the tender from the adapter."""
    return TenderExtraction(
        title=tender.title,
        buyer=tender.buyer,
        summary=tender.summary,
        region=tender.region,
        language=tender.language,
        published_at=tender.published_at,
        closing_at=tender.closing_at,
        bid_bond_minor=tender.bid_bond_minor,
        bid_bond_currency=tender.bid_bond_currency,
        doc_price_minor=tender.doc_price_minor,
        doc_price_currency=tender.doc_price_currency,
        confidence=1.0,
    )


async def extract(
    source: Source, tender: Tender, document_text: str | None, kernel: Kernel | None
) -> TenderExtraction:
    if source.type == SourceType.API:
        return _deterministic(tender)

    if kernel is None or document_text is None:
        raise ValueError(
            "unstructured extraction needs a kernel and document text "
            "(LLM path — a later week with an API key)"
        )

    from app.kernel.prompts import load_prompt

    prompt = load_prompt("extract", PROMPT_VERSION).replace("{document}", document_text)
    return await kernel.complete(
        task="extract",
        prompt=prompt,
        schema=TenderExtraction,
        prompt_version=PROMPT_VERSION,
    )
