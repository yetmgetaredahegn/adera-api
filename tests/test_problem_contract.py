"""One error shape, and a contract that says so (docs/11 §0, ADR-025).

Clients are generated from `contracts/openapi.json` and nothing else, so an
error that is real but undeclared is one the generated client cannot model --
it meets it for the first time in production. These tests pin both halves:
the shape the handlers actually emit, and the shape the document promises.
"""

from typing import Any

import pytest
from app.core.errors import (
    AUDIENCE_RESTRICTED,
    PROBLEM_DETAIL_SCHEMA,
    PROBLEM_MEDIA_TYPE,
    PROBLEM_SCHEMA_NAME,
    UNAUTHENTICATED,
    VALIDATION_SCHEMA_NAME,
    problems,
)
from app.main import create_app
from httpx import ASGITransport, AsyncClient


def _openapi() -> dict[str, Any]:
    return create_app().openapi()


def test_problem_detail_is_published_as_a_component() -> None:
    # $ref'd by every declared error response; without the component itself the
    # references dangle and client generation fails outright.
    assert _openapi()["components"]["schemas"][PROBLEM_SCHEMA_NAME] == PROBLEM_DETAIL_SCHEMA


@pytest.mark.parametrize(
    ("path", "method", "status"),
    [
        ("/api/v1/matches", "get", "401"),
        ("/api/v1/matches", "get", "403"),
        ("/api/v1/matches/{match_id}/save", "post", "403"),
        ("/api/v1/matches/{match_id}/dismiss", "post", "404"),
        ("/api/v1/auth/me", "get", "401"),
        ("/api/v1/auth/logout", "post", "403"),
        ("/api/v1/tenders/{tender_id}", "get", "404"),
    ],
)
def test_error_responses_are_declared_with_the_problem_schema(
    path: str, method: str, status: str
) -> None:
    operation = _openapi()["paths"][path][method]
    assert status in operation["responses"], f"{method.upper()} {path} hides its {status}"
    content = operation["responses"][status]["content"]
    assert content[PROBLEM_MEDIA_TYPE]["schema"]["$ref"].endswith(PROBLEM_SCHEMA_NAME)


def test_audience_restricted_is_findable_by_code_not_just_by_status() -> None:
    """ADR-029's 403 is a *different product state* from a plain forbidden --
    mobile renders a named screen for it (adera-mobile DESIGN.md §3). A client
    dev must be able to learn the code from the contract, not from source."""
    described = _openapi()["paths"]["/api/v1/matches"]["get"]["responses"]["403"]["description"]
    assert AUDIENCE_RESTRICTED.code in described


def test_problems_merges_codes_that_share_a_status() -> None:
    merged = problems(UNAUTHENTICATED, AUDIENCE_RESTRICTED)
    assert set(merged) == {401, 403}
    assert AUDIENCE_RESTRICTED.code in merged[403]["description"]


def test_validation_errors_are_documented_as_problems_not_as_fastapi_defaults() -> None:
    schema = _openapi()
    # FastAPI's own 422 models must be gone, or clients generate dead classes
    # for a shape this API no longer returns.
    assert "HTTPValidationError" not in schema["components"]["schemas"]
    assert schema["components"]["schemas"][VALIDATION_SCHEMA_NAME]["properties"]["errors"]

    documented = schema["paths"]["/api/v1/tenders"]["get"]["responses"]["422"]["content"]
    assert documented[PROBLEM_MEDIA_TYPE]["schema"]["$ref"].endswith(VALIDATION_SCHEMA_NAME)


async def test_validation_errors_keep_field_detail_in_problem_shape() -> None:
    """A 422 must be parseable by the same client code as every other error,
    without giving up the per-field detail that makes it useful."""
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="https://example.com"
    ) as client:
        resp = await client.get("/api/v1/tenders?limit=999")

    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    body = resp.json()
    assert set(PROBLEM_DETAIL_SCHEMA["required"]) <= set(body)
    assert body["type"].endswith("/validation_error")
    assert body["errors"][0]["loc"] == ["query", "limit"]
    assert "limit" in body["detail"]


async def test_framework_errors_are_problem_json_too() -> None:
    """An unrouted path is raised by Starlette, not by our code. Before the
    handler in app/core/errors.py this returned `{"detail": "Not Found"}` --
    a second error shape on the very endpoints a client hits by typo."""
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="https://example.com"
    ) as client:
        resp = await client.get("/api/v1/no-such-endpoint")

    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    body = resp.json()
    assert set(PROBLEM_DETAIL_SCHEMA["required"]) <= set(body)
    assert body["type"].endswith("/not_found")
