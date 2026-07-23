"""Qualification service (M5, FR-5.1/5.2).

Two stages, cheapest first:
1. Rule prefilter (free): source-specific signals that reliably indicate a
   tender is not biddable. World Bank "Contract Award" notices are the one rule
   today — verified empirically against the real corpus (2026-07-23): 121/121
   Contract Award notices have no closing date, and zero non-award notices lack
   one. Anything the rule stage doesn't reject proceeds to stage 2.
2. LLM qualification (prompt B2): the real judgment call — status, urgency,
   sector, reasons, confidence — for everything not already free-rejected.

Re-qualification (FR-5.3) and the correction review queue (FR-5.4) are not
built here yet — `corrected_status`/`correction_note` exist on the model as
the landing spot for FR-5.4, but no endpoint writes them. `qualify_tender` is
idempotent per tender (updates in place on re-run) so FR-5.3 has somewhere to
call into later without a schema change.
"""

from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.kernel.prompts import load_prompt
from app.kernel.router import MODEL_ROUTES, Kernel
from app.modules.ingestion.models import Tender
from app.modules.qualification.models import (
    Qualification,
    QualificationMethod,
    QualificationStatus,
    Urgency,
)
from app.modules.qualification.schemas import QualifyOut

PROMPT_VERSION = "v1"

# World Bank notice_type values that are never biddable — verified against the
# real ingested corpus, not assumed. Source-specific; extend per-source as new
# sources land, don't generalize past what's actually been checked.
_RULE_REJECT_NOTICE_TYPES = frozenset({"Contract Award"})


def _urgency_from_closing_at(closing_at: datetime | None) -> Urgency:
    if closing_at is None:
        return Urgency.UNKNOWN
    days = (closing_at - datetime.now(UTC)).days
    if days <= 7:
        return Urgency.URGENT
    if days <= 14:
        return Urgency.SOON
    return Urgency.NORMAL


def _rule_reject(tender: Tender) -> bool:
    """Free stage 1 (FR-5.1). True = confidently not biddable, skip the LLM."""
    notice_type = tender.raw_data.get("notice_type")
    return notice_type in _RULE_REJECT_NOTICE_TYPES


def _tender_text(tender: Tender) -> str:
    """Extracted fields only — never the raw untrusted document (NFR-SEC-2)."""
    deadline = tender.closing_at.isoformat() if tender.closing_at else "no deadline stated"
    lines = [
        f"Title: {tender.title}",
        f"Buyer: {tender.buyer or 'unknown'}",
        f"Summary: {tender.summary or 'none'}",
        f"Region: {tender.region or 'unknown'}",
        f"Closing: {deadline}",
    ]
    return "\n".join(lines)


async def _llm_qualify(kernel: Kernel, tender: Tender) -> QualifyOut | None:
    """Returns None on any failure — NEEDS_REVIEW is the caller's fallback,
    never a guessed status (AGENTS.md rule 11: never simulate model output)."""
    prompt = load_prompt("qualify", PROMPT_VERSION).replace("{tender}", _tender_text(tender))
    try:
        return await kernel.complete(
            task="qualify",
            prompt=prompt,
            schema=QualifyOut,
            prompt_version=PROMPT_VERSION,
        )
    except ValidationError:
        return None
    except Exception:
        # Provider-side failures (rate limit, network, budget breaker) aren't
        # ValidationError; rule 2 forbids importing litellm here to catch a
        # narrower type. Same justification as matching/service.py::_explain.
        return None


async def qualify_tender(
    session: AsyncSession, tender: Tender, kernel: Kernel | None
) -> Qualification:
    """Idempotent per tender: updates the existing row on re-run rather than
    duplicating (mirrors ingestion's upsert pattern)."""
    existing = (
        await session.execute(select(Qualification).where(Qualification.tender_id == tender.id))
    ).scalar_one_or_none()

    reasons: list[str]
    sector: str | None
    model: str | None
    raw_response: dict[str, object] | None

    if _rule_reject(tender):
        status = QualificationStatus.REJECTED
        urgency = _urgency_from_closing_at(tender.closing_at)
        sector, confidence = None, 1.0
        reasons = ["Rule stage: source notice type is never biddable (e.g. a Contract Award)."]
        method, model, raw_response = QualificationMethod.RULE, None, None
    else:
        result = await _llm_qualify(kernel, tender) if kernel is not None else None
        if result is None:
            status = QualificationStatus.NEEDS_REVIEW
            urgency = _urgency_from_closing_at(tender.closing_at)
            sector, confidence = None, 0.0
            reasons = ["LLM qualification unavailable or failed — needs human review."]
            model, raw_response = None, None
        else:
            status = result.status
            urgency = result.urgency
            sector = result.sector
            reasons = result.reasons
            confidence = result.confidence
            model = MODEL_ROUTES.get("qualify")
            raw_response = result.model_dump(mode="json")
        method = QualificationMethod.LLM

    if existing is not None:
        existing.status = status
        existing.urgency = urgency
        existing.sector = sector
        existing.reasons = reasons
        existing.confidence = confidence
        existing.method = method
        existing.model = model
        existing.raw_response = raw_response
        qualification = existing
    else:
        qualification = Qualification(
            tender_id=tender.id,
            status=status,
            urgency=urgency,
            sector=sector,
            reasons=reasons,
            confidence=confidence,
            method=method,
            model=model,
            raw_response=raw_response,
        )
        session.add(qualification)

    await session.flush()
    return qualification
