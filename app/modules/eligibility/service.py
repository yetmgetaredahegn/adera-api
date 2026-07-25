"""Eligibility service (M16, FR-16.2, prompt B6).

Two gates before any LLM call happens, both existing so a wrong "confident"
verdict is structurally hard to produce (NFR-LEGAL-1 — `unknown` is a
first-class, correct answer, never a defect):

1. **Retrieval floor.** If nothing in `law_chunks` is actually similar to the
   question, return `unknown` immediately — never send a low-relevance
   excerpt to the LLM and hope it notices. This is also the honest behavior
   given the corpus today: only Article 2 (definitions) of Proclamation
   1333/2024 is ingested (see HANDOFF.md), not the articles that actually
   govern bidder eligibility. Most real eligibility questions SHOULD return
   `unknown` right now, for a true reason — an incomplete corpus, not a bug.
2. **Citation floor.** After the LLM answers, any verdict other than
   `unknown` must carry at least one citation naming a real ingested chunk
   (checked against what was actually retrieved) — an uncited "eligible" is
   downgraded to `unknown` here, not trusted.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.kernel.prompts import load_prompt
from app.kernel.router import Kernel
from app.modules.eligibility.models import LawChunk
from app.modules.eligibility.schemas import EligibilityOut
from app.modules.identity.service import Org, require_bidder_audience
from app.modules.ingestion.service import BiddingTrack, Tender
from app.modules.matching.service import EligibilityVerdict

PROMPT_VERSION = "v1"


def classify_bidding_track(tender: Tender) -> tuple[BiddingTrack, float, str]:
    """Classify the bidding track for a tender (FR-16.1).

    Returns (track, confidence, evidence_snippet).
    Deterministic rule-based classifier first; falls back to UNKNOWN.
    """
    text = f"{tender.title} {tender.summary or ''}".lower()
    raw_type = str(tender.raw_data.get("notice_type", "")).lower()

    if "world bank" in text or "contract award" in raw_type or "wb" in text:
        return BiddingTrack.DONOR, 0.95, "World Bank notice or donor publication"
    if "icb" in text or "international competitive bidding" in text:
        return BiddingTrack.ICB, 0.90, "Matched ICB keyword in title/summary"
    if "ncb" in text or "national competitive bidding" in text:
        return BiddingTrack.NCB, 0.90, "Matched NCB keyword in title/summary"
    if "private" in text or "commercial" in text:
        return BiddingTrack.PRIVATE, 0.70, "Matched private keyword in title/summary"

    return BiddingTrack.UNKNOWN, 0.0, "Unstated bidding track"


# Below this cosine similarity, a "relevant" law chunk is noise -- same
# reasoning as matching's SIMILARITY_FLOOR, applied to legal grounding.
RETRIEVAL_SIMILARITY_FLOOR = 0.35
MAX_CHUNKS = 5


async def retrieve_relevant_chunks(
    session: AsyncSession, query_embedding: list[float], limit: int = MAX_CHUNKS
) -> list[tuple[LawChunk, float]]:
    """Nearest law chunks to a query vector, as (chunk, similarity 0..1).
    Mirrors ingestion.service.rank_by_embedding's exact pattern."""
    distance = LawChunk.embedding.cosine_distance(query_embedding)
    rows = await session.execute(
        select(LawChunk, distance.label("distance"))
        .where(LawChunk.embedding.is_not(None))
        .order_by(distance)
        .limit(limit)
    )
    return [(chunk, 1.0 - float(dist)) for chunk, dist in rows.all()]


def _query_text(org: Org, tender: Tender) -> str:
    """What we embed to find relevant law -- org type + tender category are
    the facts that actually determine eligibility, not free-text noise."""
    return (
        f"Org type: {org.org_type.value}. Org country: {org.country}. "
        f"Tender: {tender.title}. Bidding track: {tender.bidding_track.value}."
    )


def _org_text(org: Org) -> str:
    return f"Org type: {org.org_type.value}\nCountry: {org.country}"


def _tender_text(tender: Tender) -> str:
    return f"Title: {tender.title}\nBidding track: {tender.bidding_track.value}"


def _law_excerpts_text(chunks: list[LawChunk]) -> str:
    return "\n\n".join(f"[{c.document_name}, {c.article_ref}]\n{c.text_en}" for c in chunks)


def _unknown(reason: str) -> EligibilityOut:
    return EligibilityOut(
        verdict=EligibilityVerdict.UNKNOWN, reasons=[reason], citations=[], confidence=0.0
    )


async def assess_eligibility(
    session: AsyncSession, org: Org, tender: Tender, kernel: Kernel | None
) -> EligibilityOut:
    """Raises `identity.service.AudienceRestricted` for a `local`-type org
    (ADR-029) -- the router maps this to 403 `audience_restricted`, never a
    silent `unknown` verdict, which would look like a corpus gap rather than
    an audience gate."""
    require_bidder_audience(org)

    if kernel is None:
        return _unknown("no kernel available for this assessment")

    from app.kernel.embeddings import embed_texts

    query_embedding = embed_texts([_query_text(org, tender)])[0]
    ranked = await retrieve_relevant_chunks(session, query_embedding)
    relevant = [(c, s) for c, s in ranked if s >= RETRIEVAL_SIMILARITY_FLOOR]

    if not relevant:
        return _unknown(
            "no sufficiently relevant law found in the ingested corpus for this question"
        )

    chunks = [c for c, _ in relevant]
    prompt = (
        load_prompt("eligibility", PROMPT_VERSION)
        .replace("{org}", _org_text(org))
        .replace("{tender}", _tender_text(tender))
        .replace("{law_excerpts}", _law_excerpts_text(chunks))
    )

    try:
        result = await kernel.complete(
            task="eligibility",
            prompt=prompt,
            schema=EligibilityOut,
            prompt_version=PROMPT_VERSION,
        )
    except Exception:
        # rule 2 forbids importing litellm here to catch a narrower type.
        return _unknown("eligibility assessment failed (provider error)")

    if result.verdict != EligibilityVerdict.UNKNOWN:
        retrieved_refs = {(c.document_name, c.article_ref) for c in chunks}
        cited_refs = {(c.document_name, c.article_ref) for c in result.citations}
        if not cited_refs or not cited_refs.issubset(retrieved_refs):
            # A confident verdict citing nothing real is downgraded, not
            # trusted -- the citation floor (module docstring, point 2).
            return _unknown(
                "model returned a non-unknown verdict without a valid citation "
                "into the retrieved law chunks -- downgraded rather than trusted"
            )
    return result
