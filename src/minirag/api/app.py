"""FastAPI application factory."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from minirag.api.routes_index import router as index_router
from minirag.api.routes_info import router as info_router
from minirag.api.routes_query import router as query_router
from minirag.api.utils import error_response
from minirag.config import Config
from minirag.orchestration import Orchestration
from minirag.retrieval.faiss_dense import FAISSDense
from minirag.retrieval.tantivy_sparse import TantivySparse
from minirag.search.embeddings import FastTextEmbeddings
from minirag.storage.sqlite import SQLiteStorage


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Wrap uncaught errors in the standard error envelope."""
    del request
    return error_response(status=500, message=str(exc))


def create_app(config: Config, project_root: Path) -> FastAPI:
    """Create and configure FastAPI app and stateful backend services."""
    config.validate_startup(project_root)

    data_dir = config.resolve_data_dir(project_root)
    index_config = config.get_index_config()

    embeddings = FastTextEmbeddings(
        model_path=data_dir / "models" / index_config.embeddings.model_name,
        expected_dimension=index_config.embeddings.dimension,
    )
    storage = SQLiteStorage(database_path=data_dir / "storage" / index_config.storage.db_filename)
    dense = FAISSDense(
        dimension=index_config.embeddings.dimension,
        index_dir=data_dir / "index" / "faiss",
        nprobe=index_config.faiss.nprobe,
    )
    sparse = TantivySparse(
        index_dir=data_dir / "index" / "tantivy",
        language=index_config.tantivy.language,
        stemming=index_config.tantivy.stemming,
    )

    orchestration = Orchestration(
        chunking_config=index_config.chunking,
        embeddings=embeddings,
        storage=storage,
        dense=dense,
        sparse=sparse,
        search_config=config.get_search_config(),
    )

    app = FastAPI()
    app.state.config = config
    app.state.orchestration = orchestration
    app.state.app_status = "healthy"
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(info_router)
    app.include_router(index_router)
    app.include_router(query_router)

    return app
