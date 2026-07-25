"""Document parsing service logic (M3, FR-3.1, FR-3.4).

Text layer extraction via `pypdfium2`, Ethiopic script language detection,
size cap enforcement (25 MB max), and `TenderDocument` persistence.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.models import ParseMethod, TenderDocument

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB size cap


def detect_language(text: str) -> str:
    """Detect language of parsed text (FR-3.4).

    Ethiopic Unicode range (0x1200 to 0x137F) -> "am", otherwise default to "en".
    """
    if not text:
        return "en"
    ethiopic_chars = sum(1 for c in text if 0x1200 <= ord(c) <= 0x137F)
    if ethiopic_chars / len(text) > 0.10:
        return "am"
    return "en"


def extract_pdf_text_pdfium(content_bytes: bytes) -> tuple[str, float, int]:
    """Extract text layer using `pypdfium2` (FR-3.1).

    Returns (text, confidence, char_count).
    """
    try:
        import pypdfium2 as pdfium  # lazy import
    except ImportError:
        # Fallback if pypdfium2 is not installed in environment
        text = content_bytes.decode("utf-8", errors="ignore")
        return text, 0.5, len(text)

    try:
        pdf = pdfium.PdfDocument(content_bytes)
        pages_text = []
        for page in pdf:
            textpage = page.get_textpage()
            pages_text.append(textpage.get_text_range())

        full_text = "\n".join(pages_text).strip()
        char_count = len(full_text)
        page_count = max(len(pdf), 1)
        avg_chars_per_page = char_count / page_count

        # High confidence if text density >= 100 chars/page; lower confidence if sparse
        confidence = 0.95 if avg_chars_per_page >= 100 else 0.40
        return full_text, confidence, char_count
    except Exception:
        text = content_bytes.decode("utf-8", errors="ignore")
        return text, 0.2, len(text)


async def parse_and_store_document(
    session: AsyncSession,
    tender_id: uuid.UUID,
    filename: str,
    content_bytes: bytes,
    storage_key: str | None = None,
    mime_type: str = "application/pdf",
) -> TenderDocument:
    """Parse document bytes, extract text layer, detect language, and persist (FR-3.1, FR-3.4).

    Enforces 25 MB size cap.
    """
    if len(content_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"File size {len(content_bytes)} bytes exceeds max limit of {MAX_FILE_SIZE_BYTES} bytes"
        )

    storage_key = storage_key or f"tenders/{tender_id}/{filename}"

    if mime_type == "application/pdf":
        text, confidence, char_count = extract_pdf_text_pdfium(content_bytes)
        method = ParseMethod.PDFIUM
    else:
        text = content_bytes.decode("utf-8", errors="ignore")
        char_count = len(text)
        confidence = 0.8
        method = ParseMethod.PDFIUM

    lang = detect_language(text)

    doc = TenderDocument(
        tender_id=tender_id,
        storage_key=storage_key,
        filename=filename,
        mime_type=mime_type,
        file_size_bytes=len(content_bytes),
        parse_method=method,
        text=text,
        confidence=confidence,
        detected_language=lang,
        char_count=char_count,
    )
    session.add(doc)
    await session.flush()
    return doc
