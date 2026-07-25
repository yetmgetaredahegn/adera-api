"""Celery document processing tasks (M3, FR-3.1, queue=cpu)."""

import asyncio
import uuid

import httpx

from app.core.db import async_session_factory
from app.modules.documents.service import parse_and_store_document
from app.workers.celery_app import celery_app


@celery_app.task(name="documents.parse_tender_document", queue="cpu")  # type: ignore[untyped-decorator]
def parse_tender_document(tender_id_str: str, document_url: str, filename: str) -> str:
    """Fetch PDF from document_url, extract text layer, and persist TenderDocument."""

    async def _parse() -> str:
        tender_id = uuid.UUID(tender_id_str)
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(document_url)
            resp.raise_for_status()
            content = resp.content

        async with async_session_factory() as session:
            doc = await parse_and_store_document(
                session,
                tender_id=tender_id,
                filename=filename,
                content_bytes=content,
                mime_type="application/pdf",
            )
            await session.commit()
            return str(doc.id)

    return asyncio.run(_parse())
