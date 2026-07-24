"""Pure-logic unit tests for M3 Document Acquisition & Parsing (SKILLS.md R6, FR-3.1/3.4)."""

import pytest
from app.modules.documents.service import (
    MAX_FILE_SIZE_BYTES,
    detect_language,
    extract_pdf_text_pdfium,
)


def test_detect_language_english() -> None:
    text = "The Ministry of Innovation and Technology hereby invites eligible bidders for IT equipment."
    assert detect_language(text) == "en"


def test_detect_language_amharic() -> None:
    text = "የኢኖቬሽን እና ቴክኖሎጂ ሚኒስቴር ለኮምፒዩተር ግዢ የወጣ የጨረታ ማስታወቂያ"
    assert detect_language(text) == "am"


def test_detect_language_empty() -> None:
    assert detect_language("") == "en"


def test_extract_pdf_text_fallback() -> None:
    content = b"Sample text content inside a plain text or invalid PDF file"
    text, _conf, count = extract_pdf_text_pdfium(content)
    assert "Sample text content" in text
    assert count == len(content)


@pytest.mark.asyncio
async def test_parse_document_size_cap_exceeded() -> None:
    from app.modules.documents.service import parse_and_store_document

    large_content = b"0" * (MAX_FILE_SIZE_BYTES + 1)
    with pytest.raises(ValueError, match="exceeds max limit"):
        await parse_and_store_document(
            session=None,
            tender_id=None,  # type: ignore[arg-type]
            filename="large.pdf",
            content_bytes=large_content,
        )
