"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from minirag.api.responses import error_response
from minirag.api.routes_index import router as index_router
from minirag.api.routes_info import router as info_router
from minirag.api.routes_query import router as query_router
from minirag.backend_factory import build_orchestration
from minirag.config import Config
from minirag.corpus import CorpusManager
from minirag.search.embeddings import FastTextEmbeddings

logger = logging.getLogger(__name__)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Wrap uncaught errors in the standard error envelope."""
    del request
    logger.exception("Unhandled exception")
    return error_response(status=500, message="Internal server error")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifecycle — close all corpus storage on shutdown."""
    yield
    if hasattr(app.state, "corpus_manager"):
        try:
            app.state.corpus_manager.close_all()
        except RuntimeError:
            logger.exception("Errors while closing corpus storage during shutdown")


def create_app(config: Config, project_root: Path) -> FastAPI:
    """Create and configure FastAPI app and stateful backend services."""
    config.validate_startup(project_root)

    data_dir = config.resolve_data_dir(project_root)
    index_config = config.get_index_config()

    embeddings = FastTextEmbeddings(
        model_path=data_dir / "models" / index_config.embeddings.model_name,
        expected_dimension=index_config.embeddings.dimension,
    )

    corpus_manager = CorpusManager(
        data_dir=data_dir,
        index_config=index_config,
        search_config=config.get_search_config(),
        embeddings=embeddings,
        backend_factory=build_orchestration,
    )

    app = FastAPI(lifespan=lifespan)
    app.state.config = config
    app.state.corpus_manager = corpus_manager
    app.state.app_status = "healthy"
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(info_router)
    app.include_router(index_router)
    app.include_router(query_router)

    return app
