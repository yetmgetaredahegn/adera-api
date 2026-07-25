"""RFC-7807 problem+json errors, one shape for every endpoint (docs/11 §0).

A single `APIError` + handler beats each router inventing its own error body —
clients (web/mobile) parse one shape everywhere, forever.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class APIError(Exception):
    """Raise this from anywhere below the router; the handler below turns it
    into the catalog shape from docs/11_API_REFERENCE.md §0."""

    def __init__(self, status_code: int, code: str, detail: str) -> None:
        self.status_code = status_code
        self.code = code
        self.detail = detail
        super().__init__(detail)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def _handle_api_error(request: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            media_type="application/problem+json",
            content={
                "type": f"https://adera.bid/errors/{exc.code}",
                "title": exc.code.replace("_", " ").title(),
                "status": exc.status_code,
                "detail": exc.detail,
                "instance": str(request.url.path),
            },
        )
