"""Administrative routes for health, info, and shutdown."""

import os
import signal

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from minirag.api.models.info import HealthResponse, InfoResponse, ShutdownResponse
from minirag.api.responses import success_response
from minirag.api.utils import ensure_healthy, get_config

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
