"""Fixtures for mini-rag end-to-end tests.

Lifecycle:
    1. Create a temporary data directory with a symlink to the FastText model.
    2. Write an e2e-specific config file (separate port, small chunk_size).
    3. Start the service as a subprocess via ``start_server.py``.
    4. Poll the health endpoint until the service is ready.
    5. Yield clients to the test session.
    6. Shut down the service and remove the temporary directory.
"""

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import httpx
import pytest
import yaml

from minirag.clients.indexing import IndexingClient
from minirag.clients.query import QueryClient
from tests_e2e.documents import (
    DOCUMENT_1,
    DOCUMENT_2,
    E2E_CHUNK_SIZE,
    E2E_OVERLAP,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
E2E_HOST = "127.0.0.1"
E2E_PORT = 7099
PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SERVER_STARTUP_TIMEOUT_S = 120  # FastText model loading can be slow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _wait_for_health(base_url: str, timeout_s: int) -> None:
    """Block until the service health endpoint responds 200."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(f"{base_url}/v1/health", timeout=2.0)
            if resp.status_code == 200:
                return
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.TimeoutException):
            pass
        time.sleep(1.0)
    raise RuntimeError(f"Service at {base_url} did not become healthy within {timeout_s}s")


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def e2e_data_dir():
    """Temporary data directory wired to the real FastText model."""
    tmp = tempfile.mkdtemp(prefix="minirag-e2e-")
    data_dir = Path(tmp)

    # Required sub-directories
    (data_dir / "models").mkdir()
    (data_dir / "storage").mkdir()
    (data_dir / "index" / "faiss").mkdir(parents=True)
    (data_dir / "index" / "tantivy").mkdir(parents=True)
    (data_dir / "input" / "txt").mkdir(parents=True)

    # Symlink the (large) FastText model so we avoid copying 4 GB+
    model_src = PROJECT_ROOT / "data" / "models" / "cc.en.300.bin"
    if not model_src.exists():
        pytest.skip(f"FastText model not found at {model_src} – run 'just init'")
    os.symlink(model_src, data_dir / "models" / "cc.en.300.bin")

    yield data_dir

    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(scope="session")
def e2e_config_path(e2e_data_dir):
    """Write the e2e config file and return its path."""
    config = {
        "service": {
            "host": E2E_HOST,
            "port": E2E_PORT,
            "reload": False,
            "log_level": "WARNING",
        },
        "data": {
            "data_dir": str(e2e_data_dir),
        },
        "index": {
            "chunking": {
                "chunk_size": E2E_CHUNK_SIZE,
                "overlap": E2E_OVERLAP,
            },
            "embeddings": {
                "model_name": "cc.en.300.bin",
                "dimension": 300,
            },
            "storage": {
                "db_filename": "minirag_e2e.db",
            },
            "faiss": {
                "index_type": "IndexFlatIP",
                "nprobe": 1,
            },
            "tantivy": {
                "language": "en",
                "stemming": True,
            },
        },
        "search": {
            "hybrid": {"alpha": 0.5},
            "dense": {},
            "sparse": {},
        },
    }

    config_path = e2e_data_dir / "config_e2e.yaml"
    with config_path.open("w", encoding="utf-8") as fh:
        yaml.dump(config, fh, default_flow_style=False)

    return config_path


@pytest.fixture(scope="session")
def e2e_server(e2e_config_path):
    """Start the mini-rag service and yield the base URL."""
    launcher = PROJECT_ROOT / "tests_e2e" / "start_server.py"
    proc = subprocess.Popen(
        ["uv", "run", str(launcher), str(e2e_config_path)],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    base_url = f"http://{E2E_HOST}:{E2E_PORT}"

    try:
        _wait_for_health(base_url, _SERVER_STARTUP_TIMEOUT_S)
    except RuntimeError as exc:
        proc.kill()
        stdout, stderr = proc.communicate(timeout=5)
        raise RuntimeError(f"Server failed to start.\nstdout: {stdout.decode()}\nstderr: {stderr.decode()}") from exc

    yield base_url

    # Graceful shutdown
    try:
        httpx.post(f"{base_url}/v1/shutdown", timeout=5.0)
        proc.wait(timeout=15)
    except Exception:
        proc.kill()
        proc.wait(timeout=5)


@pytest.fixture(scope="session")
def indexing_client(e2e_server):
    """IndexingClient connected to the e2e service."""
    return IndexingClient(host=E2E_HOST, port=E2E_PORT)


@pytest.fixture(scope="session")
def query_client(e2e_server):
    """QueryClient connected to the e2e service."""
    return QueryClient(host=E2E_HOST, port=E2E_PORT)


@pytest.fixture(scope="session")
def indexed_documents(indexing_client):
    """Clear the index, then index both test documents.

    Returns a dict keyed by document name with ``id`` and ``chunk_ids``.
    """
    indexing_client.destroy_index()

    doc1_id, doc1_chunks = indexing_client.index_document(DOCUMENT_1)
    doc2_id, doc2_chunks = indexing_client.index_document(DOCUMENT_2)

    return {
        "doc1": {"id": doc1_id, "chunk_ids": doc1_chunks},
        "doc2": {"id": doc2_id, "chunk_ids": doc2_chunks},
    }
