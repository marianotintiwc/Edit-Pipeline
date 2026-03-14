from __future__ import annotations

from fastapi.responses import JSONResponse


def error_response(
    *,
    status_code: int,
    error_code: str,
    message: str,
    details: list[str] | None = None,
) -> JSONResponse:
    payload: dict[str, object] = {
        "error_code": error_code,
        "detail": message,
    }
    if details:
        payload["errors"] = details
    return JSONResponse(status_code=status_code, content=payload)

