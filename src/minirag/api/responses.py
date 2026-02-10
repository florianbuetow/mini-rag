"""API response envelope helpers."""

from fastapi.responses import JSONResponse


def success_response(status: int, data: dict[str, object]) -> JSONResponse:
    """Build a success envelope response."""
    return JSONResponse(status_code=status, content={"status": status, "data": data})


def error_response(status: int, message: str) -> JSONResponse:
    """Build an error envelope response."""
    return JSONResponse(status_code=status, content={"status": status, "error": message})
