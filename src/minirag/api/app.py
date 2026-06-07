"""FastAPI application factory."""

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from minirag.agent import LM_STUDIO_BASE_URL, MiniRagAgent
from minirag.api.responses import error_response
from minirag.api.routes_chat_completions import router as completions_router
from minirag.api.routes_chats import router as chats_router
from minirag.api.routes_citation import router as citation_router
from minirag.api.routes_index import router as index_router
from minirag.api.routes_info import router as info_router
from minirag.api.routes_query import router as query_router
from minirag.api.static import mount_static_files
from minirag.backend_factory import build_embeddings, build_orchestration
from minirag.config import Config
from minirag.context_pruning import ContextPruner
from minirag.corpus import CorpusManager
from minirag.lm_studio import LMStudioModelInfo
from minirag.reranking.cross_encoder import CrossEncoderReranker
from minirag.reranking.interface import Reranker
from minirag.startup_validation import validate_startup_environment
from minirag.title_agent import ConversationTitleAgent

logger = logging.getLogger(__name__)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Log and return detailed validation errors for bad requests."""
    logger.debug(
        "Validation error on %s %s: %s",
        request.method,
        request.url.path,
        exc.errors(),
    )
    return error_response(status=422, message=str(exc))


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Wrap uncaught errors in the standard error envelope."""
    del request
    logger.exception("Unhandled exception")
    return error_response(status=500, message=str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Manage application lifecycle — close all corpus storage on shutdown."""
    yield
    if hasattr(app.state, "corpus_manager"):
        try:
            app.state.corpus_manager.close_all()
        except RuntimeError:
            logger.exception("Errors while closing corpus storage during shutdown")


def create_app(config: Config, project_root: Path) -> FastAPI:
    """Create and configure FastAPI app and stateful backend services."""
    validate_startup_environment(config=config, project_root=project_root)

    data_dir = config.resolve_data_dir(project_root)
    index_config = config.get_index_config()
    search_config = config.get_search_config()

    embeddings = build_embeddings(index_config.embeddings, data_dir)

    reranker: Reranker | None = None
    if search_config.reranking.enabled:
        reranker = CrossEncoderReranker(
            model_name=search_config.reranking.model_name,
            model_cache_dir=data_dir / "models",
            candidate_multiplier=search_config.reranking.candidate_multiplier,
        )

    corpus_manager = CorpusManager(
        data_dir=data_dir,
        index_config=index_config,
        search_config=search_config,
        embeddings=embeddings,
        backend_factory=build_orchestration,
        reranker=reranker,
    )

    lm_studio_url_override = os.environ.get("MINIRAG_LM_STUDIO_URL")
    lm_studio_url = lm_studio_url_override if lm_studio_url_override is not None else LM_STUDIO_BASE_URL
    agent = MiniRagAgent(
        corpus_manager=corpus_manager,
        lm_studio_base_url=lm_studio_url,
        context_pruning_config=search_config.context_pruning,
        model_info=LMStudioModelInfo(
            lm_studio_url,
            fallback_context_window_tokens=search_config.context_pruning.fallback_context_window_tokens,
            timeout_seconds=2.0,
        ),
        context_pruner=ContextPruner(),
    )

    title_agent = ConversationTitleAgent(lm_studio_base_url=lm_studio_url)

    app = FastAPI(lifespan=lifespan)
    app.state.config = config
    app.state.corpus_manager = corpus_manager
    app.state.data_dir = data_dir
    app.state.agent = agent
    app.state.title_agent = title_agent
    app.state.app_status = "healthy"
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(info_router)
    app.include_router(index_router)
    app.include_router(query_router)
    app.include_router(citation_router)
    app.include_router(chats_router)
    app.include_router(completions_router)

    # Static file serving must be mounted last — API routes take precedence
    web_dir_override = os.environ.get("MINIRAG_WEB_DIR")
    web_dir = Path(web_dir_override) if web_dir_override else project_root / "web"
    mount_static_files(app, web_dir)

    return app
