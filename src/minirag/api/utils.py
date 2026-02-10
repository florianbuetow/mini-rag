"""API app-state guard and accessor helpers."""

from typing import cast

from fastapi import Request
from fastapi.responses import JSONResponse

from minirag.api.responses import error_response
from minirag.config import Config
from minirag.corpus import CorpusManager


def ensure_healthy(request: Request) -> JSONResponse | None:
    """Return a 503 envelope when app state is not healthy, or None when healthy."""
    app_status = request.app.state.app_status
    if app_status != "healthy":
        return error_response(status=503, message=f"service is {app_status}")

    return None


def get_corpus_manager(request: Request) -> CorpusManager:
    """Get corpus manager instance from FastAPI app state."""
    if not hasattr(request.app.state, "corpus_manager"):
        raise RuntimeError("corpus_manager is not initialized on app state")
    return cast(CorpusManager, request.app.state.corpus_manager)


def get_config(request: Request) -> Config:
    """Get config instance from FastAPI app state."""
    if not hasattr(request.app.state, "config"):
        raise RuntimeError("config is not initialized on app state")
    return cast(Config, request.app.state.config)
