"""Fixtures for mini-rag integration tests.

Lifecycle:
    1. Read project config.yaml to locate the real data directory.
    2. Create a temporary data directory with a symlink to the FastText model.
    3. Build Config and start uvicorn in a background thread.
    4. Create IndexingClient and QueryClient pointing at the local server.
    5. Index test documents.
    6. Yield clients to the test session.
    7. Shut down the server and clean up temp directory.
"""

import os
import shutil
import tempfile
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
import yaml

from minirag.api.app import create_app
from minirag.clients.indexing import IndexingClient
from minirag.clients.query import QueryClient
from minirag.config import Config
from tests_integration.documents import (
    CITATION_1,
    CITATION_2,
    DOCUMENT_1,
    DOCUMENT_2,
    E2E_CHUNK_SIZE,
    E2E_OVERLAP,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
INTEGRATION_CORPUS = "integration-test"
INTEGRATION_HOST = "127.0.0.1"
INTEGRATION_PORT = 7099
PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def integration_data_dir():
    """Temporary data directory wired to the real FastText model."""
    # Read the project config to find the real data directory
    project_config_path = PROJECT_ROOT / "config.yaml"
    if not project_config_path.exists():
        pytest.skip(f"Project config not found at {project_config_path}")
    project_config = Config.from_yaml(project_config_path)
    source_data_dir = project_config.resolve_data_dir(PROJECT_ROOT)

    tmp = tempfile.mkdtemp(prefix="minirag-integration-")
    data_dir = Path(tmp)

    # Required sub-directories
    (data_dir / "models").mkdir()
    (data_dir / "storage").mkdir()
    (data_dir / "index").mkdir(parents=True)

    # Symlink the (large) FastText model so we avoid copying 4 GB+
    model_name = project_config.index.embeddings.model_name
    model_src = source_data_dir / "models" / model_name
    if not model_src.exists():
        pytest.skip(f"FastText model not found at {model_src} – run 'just init'")
    os.symlink(model_src, data_dir / "models" / model_name)

    yield data_dir

    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(scope="session")
def integration_config(integration_data_dir):
    """Build and return Config for integration tests."""
    # Read embeddings config from the project config to avoid hardcoding model values
    project_config_path = PROJECT_ROOT / "config.yaml"
    project_config = Config.from_yaml(project_config_path)
    emb = project_config.index.embeddings

    config_dict = {
        "service": {
            "host": INTEGRATION_HOST,
            "port": INTEGRATION_PORT,
            "reload": False,
            "log_level": "WARNING",
        },
        "data": {
            "data_dir": str(integration_data_dir),
        },
        "index": {
            "chunking": {
                "chunk_size": E2E_CHUNK_SIZE,
                "overlap": E2E_OVERLAP,
            },
            "embeddings": {
                "model_name": emb.model_name,
                "dimension": emb.dimension,
            },
            "storage": {
                "db_filename": "minirag_integration.db",
            },
            "faiss": {
                "index_type": project_config.index.faiss.index_type,
                "nprobe": project_config.index.faiss.nprobe,
            },
            "tantivy": {
                "language": project_config.index.tantivy.language,
                "stemming": project_config.index.tantivy.stemming,
            },
        },
        "search": {
            "hybrid": {"alpha": 0.5},
            "dense": {},
            "sparse": {},
            "reranking": {
                "enabled": False,
                "model_name": "cross-encoder/ms-marco-MiniLM-L12-v2",
                "candidate_multiplier": 3,
            },
        },
    }

    # Write config to file and load via Config.from_yaml for full validation
    config_path = integration_data_dir / "config_integration.yaml"
    with config_path.open("w", encoding="utf-8") as fh:
        yaml.dump(config_dict, fh, default_flow_style=False)

    return Config.from_yaml(config_path)


@pytest.fixture(scope="session")
def integration_server(integration_config):
    """Start uvicorn in a background thread and yield when ready."""
    app = create_app(config=integration_config, project_root=PROJECT_ROOT)

    server = uvicorn.Server(
        uvicorn.Config(
            app=app,
            host=INTEGRATION_HOST,
            port=INTEGRATION_PORT,
            log_level="warning",
        )
    )

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server to be ready
    base_url = f"http://{INTEGRATION_HOST}:{INTEGRATION_PORT}"
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(f"{base_url}/v1/health", timeout=2.0)
            if resp.status_code == 200:
                break
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.TimeoutException):
            pass  # Server not ready yet; retry after sleep
        time.sleep(0.5)
    else:
        raise RuntimeError("Integration server did not start within 60s")

    yield

    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture(scope="session")
def integration_http_client(integration_server):
    """httpx.Client for direct HTTP requests to the integration server."""
    base_url = f"http://{INTEGRATION_HOST}:{INTEGRATION_PORT}"
    client = httpx.Client(base_url=base_url, timeout=30.0)

    yield client

    client.close()


@pytest.fixture(scope="session")
def indexing_client(integration_server):
    """IndexingClient backed by the integration server."""
    return IndexingClient(host=INTEGRATION_HOST, port=INTEGRATION_PORT, http_client=None)


@pytest.fixture(scope="session")
def query_client(integration_server):
    """QueryClient backed by the integration server."""
    return QueryClient(host=INTEGRATION_HOST, port=INTEGRATION_PORT, http_client=None)


@pytest.fixture(scope="session")
def indexed_documents(indexing_client):
    """Clear the index, then index both test documents.

    Returns a dict keyed by document name with ``id`` and ``chunk_ids``.
    """
    indexing_client.destroy_index(INTEGRATION_CORPUS)

    doc1_id, doc1_chunks = indexing_client.index_document(INTEGRATION_CORPUS, DOCUMENT_1, CITATION_1)
    doc2_id, doc2_chunks = indexing_client.index_document(INTEGRATION_CORPUS, DOCUMENT_2, CITATION_2)

    return {
        "doc1": {"id": doc1_id, "chunk_ids": doc1_chunks},
        "doc2": {"id": doc2_id, "chunk_ids": doc2_chunks},
    }
