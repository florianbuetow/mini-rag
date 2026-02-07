"""API response and app-state guard helpers."""

from fastapi import Request
from fastapi.responses import JSONResponse


def success_response(status: int, data: dict[str, object]) -> JSONResponse:
    """Build a success envelope response."""
    return JSONResponse(status_code=status, content={"status": status, "data": data})


def error_response(status: int, message: str) -> JSONResponse:
    """Build an error envelope response."""
    return JSONResponse(status_code=status, content={"status": status, "error": message})


def ensure_healthy(request: Request) -> JSONResponse | None:
    """Return a 503 envelope when app state is not healthy."""
    app_status = request.app.state.app_status
    if app_status != "healthy":
        return error_response(status=503, message=f"service is {app_status}")

    return None
