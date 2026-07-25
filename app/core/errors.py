"""RFC-7807 problem+json errors, one shape for every endpoint (docs/11 §0).

A single `APIError` + handler beats each router inventing its own error body —
clients (web/mobile) parse one shape everywhere, forever.

Two things make that promise real rather than aspirational, and both live here:

- `_handle_http_exception` catches the framework's own `HTTPException`, so a
  router that raises one (or Starlette itself, on an unrouted path) still emits
  problem+json instead of `{"detail": ...}` — the second shape clients would
  otherwise have to special-case.
- `problems()` + `ProblemDocumentedFastAPI` publish the failure cases in the
  OpenAPI document. A generated client (ADR-025: the contract is the ONLY
  coupling to mobile/web) can only model errors that are declared, and an
  undeclared 403 is one a client will meet for the first time in production.
"""

from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_MEDIA_TYPE = "application/problem+json"
PROBLEM_SCHEMA_NAME = "ProblemDetail"
PROBLEM_TYPE_PREFIX = "https://adera.bid/errors/"

# The exact body the handlers below emit, written as an OpenAPI schema so
# clients generate ONE problem type instead of an anonymous copy per endpoint.
# tests/test_problem_contract.py pins the two representations together — if you
# change the body, that test fails until you change this too.
PROBLEM_DETAIL_SCHEMA: dict[str, Any] = {
    "title": PROBLEM_SCHEMA_NAME,
    "type": "object",
    "description": (
        "RFC 7807 problem+json. Every error from this API has this shape. "
        "Branch on `type` (a stable URL ending in the error code), never on `title` "
        "or on the prose in `detail`."
    ),
    "properties": {
        "type": {
            "type": "string",
            "description": f"`{PROBLEM_TYPE_PREFIX}<code>` — the stable, matchable identity.",
        },
        "title": {"type": "string", "description": "Human-readable summary of the code."},
        "status": {"type": "integer", "description": "Repeats the HTTP status code."},
        "detail": {
            "type": "string",
            "description": "What went wrong this time. Prose; may change.",
        },
        "instance": {"type": "string", "description": "Request path the failure applies to."},
    },
    "required": ["type", "title", "status", "detail", "instance"],
}

VALIDATION_SCHEMA_NAME = "ValidationProblem"

# 422 is the one error that carries more than prose: which field, and why. RFC
# 7807 allows extension members, so field detail rides along in `errors` rather
# than forcing clients to keep a second parser for the one status they hit most
# while developing.
VALIDATION_PROBLEM_SCHEMA: dict[str, Any] = {
    "title": VALIDATION_SCHEMA_NAME,
    "type": "object",
    "description": "A ProblemDetail with per-field validation detail attached.",
    "properties": {
        **PROBLEM_DETAIL_SCHEMA["properties"],
        "errors": {
            "type": "array",
            "description": "Pydantic's per-field errors: `loc`, `msg`, `type`.",
            "items": {"type": "object"},
        },
    },
    "required": PROBLEM_DETAIL_SCHEMA["required"],
}


@dataclass(frozen=True)
class Problem:
    """One entry of the docs/11 §0 error catalog, in a form a route can declare."""

    status: int
    code: str
    when: str


# The catalog, as far as a client can actually observe it. Codes are load-bearing
# API surface: renaming one is a breaking change for every generated client.
UNAUTHENTICATED = Problem(401, "unauthenticated", "no session cookie, or it is expired or revoked")
FORBIDDEN = Problem(403, "forbidden", "authenticated, but not permitted (e.g. no organization)")
CSRF_FAILED = Problem(403, "csrf_failed", "missing or mismatched X-CSRF-Token on an unsafe method")
AUDIENCE_RESTRICTED = Problem(
    403,
    "audience_restricted",
    "org_type=local is supply-side only (ADR-029); bidder features are for "
    "diaspora/foreign orgs. Render a named blocked state, never an empty list",
)
ORG_ID_REQUIRED = Problem(
    400, "org_id_required", "the user belongs to several orgs; repeat the call with ?org_id="
)
NOT_FOUND = Problem(
    404, "not_found", "no such resource — also returned instead of 403 across orgs, deliberately"
)
CONFLICT = Problem(409, "conflict", "duplicate email, or an illegal state transition")
VALIDATION_ERROR = Problem(
    422, "validation_error", "the request did not match the schema; see the `errors` member"
)
RATE_LIMITED = Problem(
    429, "rate_limited", "too many requests in one minute; honour the Retry-After header"
)

# Framework-raised HTTPExceptions carry no code of their own. Map the ones a
# client can actually provoke onto catalog codes; anything else is `http_error`
# rather than a silently invented code that looks catalogued but isn't.
_STATUS_CODES: dict[int, str] = {
    400: "bad_request",
    401: UNAUTHENTICATED.code,
    403: FORBIDDEN.code,
    404: NOT_FOUND.code,
    405: "method_not_allowed",
    409: CONFLICT.code,
    422: "validation_error",
    429: RATE_LIMITED.code,
}


def problems(*declared: Problem) -> dict[int | str, dict[str, Any]]:
    """Render `responses=` for a route from catalog entries.

    Several codes share one status (403 is `forbidden`, `csrf_failed`, AND
    `audience_restricted`), and OpenAPI keys responses by status — so they merge
    into one entry whose description names every code that can arrive with it.
    """
    out: dict[int | str, dict[str, Any]] = {}
    for problem in declared:
        entry = out.setdefault(
            problem.status,
            {
                "description": "",
                "content": {
                    PROBLEM_MEDIA_TYPE: {
                        "schema": {"$ref": f"#/components/schemas/{PROBLEM_SCHEMA_NAME}"}
                    }
                },
            },
        )
        line = f"`{problem.code}` — {problem.when}"
        entry["description"] = f"{entry['description']}\n\n{line}" if entry["description"] else line
    return out


def _validation_response_doc() -> dict[str, Any]:
    return {
        "description": f"`{VALIDATION_ERROR.code}` — {VALIDATION_ERROR.when}",
        "content": {
            PROBLEM_MEDIA_TYPE: {
                "schema": {"$ref": f"#/components/schemas/{VALIDATION_SCHEMA_NAME}"}
            }
        },
    }


class ProblemDocumentedFastAPI(FastAPI):
    """FastAPI whose document tells the truth about errors.

    Two fixes, both invisible from a route decorator:

    1. `ProblemDetail` is published as a component. Responses declared through
       `problems()` `$ref` it, but no route uses it as a response *model*, so
       stock FastAPI never emits it and every generated client would hit a
       dangling reference. Declaring it as a `model` on some arbitrary route
       would instead document the wrong media type for that route's failures.
    2. Every auto-generated 422 is rewritten. FastAPI documents validation
       failures as `application/json` + `HTTPValidationError`; ours are
       problem+json like everything else (see the handler below), and a
       contract that disagrees with the wire is worse than no contract.
    """

    def openapi(self) -> dict[str, Any]:
        schema = super().openapi()
        components: dict[str, Any] = schema.setdefault("components", {}).setdefault("schemas", {})
        components[PROBLEM_SCHEMA_NAME] = PROBLEM_DETAIL_SCHEMA
        components[VALIDATION_SCHEMA_NAME] = VALIDATION_PROBLEM_SCHEMA

        for path_item in schema.get("paths", {}).values():
            for operation in path_item.values():
                if isinstance(operation, dict) and "422" in operation.get("responses", {}):
                    operation["responses"]["422"] = _validation_response_doc()

        # Nothing references FastAPI's own validation models once every 422 is
        # rewritten; leaving them would generate two dead classes in each client.
        components.pop("HTTPValidationError", None)
        components.pop("ValidationError", None)
        return schema


class APIError(Exception):
    """Raise this from anywhere below the router; the handler below turns it
    into the catalog shape from docs/11_API_REFERENCE.md §0."""

    def __init__(self, status_code: int, code: str, detail: str) -> None:
        self.status_code = status_code
        self.code = code
        self.detail = detail
        super().__init__(detail)


def _problem_response(status_code: int, code: str, detail: str, path: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        media_type=PROBLEM_MEDIA_TYPE,
        content={
            "type": f"{PROBLEM_TYPE_PREFIX}{code}",
            "title": code.replace("_", " ").title(),
            "status": status_code,
            "detail": detail,
            "instance": path,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def _handle_api_error(request: Request, exc: APIError) -> JSONResponse:
        return _problem_response(exc.status_code, exc.code, exc.detail, str(request.url.path))

    # Overrides FastAPI's built-in handler, which emits `{"detail": ...}`.
    # Starlette resolves handlers along the exception's MRO, so this covers
    # fastapi.HTTPException (a subclass) and Starlette's own raises alike --
    # unrouted path, wrong method. Without it, "one error shape everywhere" is
    # false on exactly the endpoints mobile calls most.
    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "http_error")
        return _problem_response(exc.status_code, code, str(exc.detail), str(request.url.path))

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # The last client-visible shape that wasn't problem+json. Field detail
        # survives as an RFC 7807 extension member rather than being dropped:
        # it is the whole value of a 422, and trading it for consistency would
        # be a bad deal for whoever is debugging a request body at 2am.
        errors = jsonable_encoder(exc.errors())
        first = errors[0] if errors else {}
        where = ".".join(str(part) for part in first.get("loc", [])) or "request"
        return JSONResponse(
            status_code=422,
            media_type=PROBLEM_MEDIA_TYPE,
            content={
                "type": f"{PROBLEM_TYPE_PREFIX}{VALIDATION_ERROR.code}",
                "title": "Validation Error",
                "status": 422,
                "detail": f"{where}: {first.get('msg', 'failed validation')}",
                "instance": str(request.url.path),
                "errors": errors,
            },
        )
