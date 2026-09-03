"""Administrative routes for health, info, and shutdown."""

import logging
import os
import signal

import httpx
from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from minirag.agent import LM_STUDIO_BASE_URL
from minirag.api.models.info import (
    CorporaResponse,
    CorpusDescriptionResponse,
    HealthResponse,
    InfoResponse,
    ShutdownResponse,
)
from minirag.api.responses import error_response, success_response
from minirag.api.utils import ensure_healthy, get_config, get_corpus_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1")


def _shutdown_process_tree(reload_enabled: bool) -> None:
    """Terminate current process and uvicorn reload parent when present."""
    current_pid = os.getpid()
    if reload_enabled:
        parent_pid = os.getppid()
        if parent_pid > 1:
            os.kill(parent_pid, signal.SIGTERM)
    os.kill(current_pid, signal.SIGTERM)


@router.get("/health")
async def health(request: Request) -> JSONResponse:
    """Return service health status."""
    app_status = request.app.state.app_status
    response = HealthResponse(status=app_status)

    if app_status == "healthy":
        return success_response(status=200, data=response.model_dump())

    return success_response(status=503, data=response.model_dump())


@router.get("/info")
async def info(request: Request) -> JSONResponse:
    """Return full service configuration."""
    config = get_config(request)
    response = InfoResponse(config=config.model_dump())
    return success_response(status=200, data=response.model_dump())


@router.post("/shutdown")
async def shutdown(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    """Initiate graceful shutdown and reject subsequent guarded requests."""
    guard_response = ensure_healthy(request)
    if guard_response is not None:
        return guard_response

    config = get_config(request)
    reload_enabled = config.get_service_config().reload
    request.app.state.app_status = "shutting_down"
    background_tasks.add_task(_shutdown_process_tree, reload_enabled)

    response = ShutdownResponse(message="shutdown initiated")
    return success_response(status=200, data=response.model_dump())


@router.get("/models")
async def list_models(request: Request) -> JSONResponse:
    """Proxy LM Studio's model list to avoid browser CORS issues."""
    guard_response = ensure_healthy(request)
    if guard_response is not None:
        return guard_response

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{LM_STUDIO_BASE_URL}/models")
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except httpx.ConnectError:
        logger.warning("LM Studio not reachable at %s", LM_STUDIO_BASE_URL)
        return success_response(status=200, data={"data": []})
    except Exception:
        logger.exception("Failed to fetch models from LM Studio")
        return error_response(status=502, message="Failed to fetch models from LM Studio")


@router.get("/corpora")
async def list_corpora(request: Request) -> JSONResponse:
    """Return available corpora and their descriptions."""
    guard_response = ensure_healthy(request)
    if guard_response is not None:
        return guard_response

    corpus_manager = get_corpus_manager(request)
    try:
        corpora = corpus_manager.list_corpora()
        descriptions = corpus_manager.corpus_descriptions(corpora)
    except (OSError, UnicodeError):
        logger.exception("Failed to read corpus descriptions")
        return error_response(status=500, message="Failed to list corpus descriptions")

    response = CorporaResponse(corpora=corpora, descriptions=descriptions)
    return success_response(status=200, data=response.model_dump())


@router.get("/corpus/{corpus}/description")
async def corpus_description(request: Request, corpus: str) -> JSONResponse:
    """Return the resolved description for one loaded corpus."""
    guard_response = ensure_healthy(request)
    if guard_response is not None:
        return guard_response

    corpus_manager = get_corpus_manager(request)
    try:
        description = corpus_manager.corpus_description(corpus)
    except FileNotFoundError as exc:
        return error_response(status=404, message=str(exc))
    except (OSError, UnicodeError):
        logger.exception("Failed to read description for corpus %s", corpus)
        return error_response(status=500, message="Failed to read corpus description")
    except ValueError as exc:
        return error_response(status=400, message=str(exc))

    response = CorpusDescriptionResponse(corpus=corpus, description=description)
    return success_response(status=200, data=response.model_dump())
