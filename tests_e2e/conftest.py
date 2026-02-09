"""Fixtures for mini-rag end-to-end lifecycle tests.

Lifecycle:
    1. Read project config.yaml to locate the real data directory.
    2. Create a temporary data directory with symlinks to model and test corpus.
    3. Write an e2e-specific config file pointing to the temp data dir.
    4. Start the service as a subprocess via ``start_server.py``.
    5. Poll the health endpoint until the service is ready.
    6. Yield environment info to the test session.
    7. Shut down the service and remove the temporary directory.
"""

import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
import yaml

from minirag.config import Config

E2E_HOST = "127.0.0.1"
E2E_PORT = 7098
E2E_CORPUS = "test"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SERVER_STARTUP_TIMEOUT_S = 120


@dataclass(frozen=True)
class E2EEnv:
    """Environment info yielded to lifecycle tests."""

    base_url: str
    config_path: Path
    data_dir: Path
    project_root: Path
    host: str
    port: int
    corpus: str


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


@pytest.fixture(scope="session")
def e2e_env():
    """Start a real server subprocess and yield E2EEnv."""
    # Read the project config to resolve the real data directory
    project_config_path = PROJECT_ROOT / "config.yaml"
    if not project_config_path.exists():
        pytest.skip(f"Project config not found at {project_config_path}")
    project_config = Config.from_yaml(project_config_path)
    source_data_dir = project_config.resolve_data_dir(PROJECT_ROOT)

    tmp = tempfile.mkdtemp(prefix="minirag-e2e-lifecycle-")
    data_dir = Path(tmp)

    # Required sub-directories
    (data_dir / "models").mkdir()
    (data_dir / "storage").mkdir()
    (data_dir / "index").mkdir(parents=True)

    # Symlink the (large) FastText model from the configured data directory
    model_name = project_config.index.embeddings.model_name
    model_src = source_data_dir / "models" / model_name
    if not model_src.exists():
        shutil.rmtree(tmp, ignore_errors=True)
        pytest.skip(f"FastText model not found at {model_src} – run 'just init'")
    os.symlink(model_src, data_dir / "models" / model_name)

    # Set up the test corpus input directory with writable txt/
    test_input_src = source_data_dir / "input" / E2E_CORPUS
    if not test_input_src.exists():
        # Fall back to the repo-tracked test corpus
        test_input_src = PROJECT_ROOT / "data" / "input" / E2E_CORPUS
    if not test_input_src.exists():
        shutil.rmtree(tmp, ignore_errors=True)
        pytest.skip(f"Test corpus not found at {test_input_src}")

    # Create corpus dir as a real directory (not a symlink) so txt/ is writable
    corpus_dir = data_dir / "input" / E2E_CORPUS
    corpus_dir.mkdir(parents=True)

    # Symlink read-only subdirectories from the source corpus
    for subdir_name in ("md", "evals", "metadata"):
        src_subdir = test_input_src / subdir_name
        if src_subdir.exists():
            os.symlink(src_subdir, corpus_dir / subdir_name)

    # Create a writable txt/ directory for md2txt output
    (corpus_dir / "txt").mkdir()

    # Write e2e config pointing to the temp data directory
    config_dict = {
        "service": {
            "host": E2E_HOST,
            "port": E2E_PORT,
            "reload": False,
            "log_level": "WARNING",
        },
        "data": {
            "data_dir": str(data_dir),
        },
        "index": {
            "chunking": {
                "chunk_size": project_config.index.chunking.chunk_size,
                "overlap": project_config.index.chunking.overlap,
            },
            "embeddings": {
                "model_name": model_name,
                "dimension": project_config.index.embeddings.dimension,
            },
            "storage": {
                "db_filename": "minirag_e2e.db",
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
            "hybrid": {"alpha": project_config.search.hybrid.alpha},
            "dense": {},
            "sparse": {},
        },
    }

    config_path = data_dir / "config_e2e.yaml"
    with config_path.open("w", encoding="utf-8") as fh:
        yaml.dump(config_dict, fh, default_flow_style=False)

    # Start server subprocess
    launcher = PROJECT_ROOT / "tests_e2e" / "start_server.py"
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "src")}
    proc = subprocess.Popen(
        ["uv", "run", str(launcher), str(config_path)],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    base_url = f"http://{E2E_HOST}:{E2E_PORT}"

    try:
        _wait_for_health(base_url, _SERVER_STARTUP_TIMEOUT_S)
    except RuntimeError as exc:
        proc.kill()
        stdout, stderr = proc.communicate(timeout=5)
        shutil.rmtree(tmp, ignore_errors=True)
        raise RuntimeError(f"Server failed to start.\nstdout: {stdout.decode()}\nstderr: {stderr.decode()}") from exc

    yield E2EEnv(
        base_url=base_url,
        config_path=config_path,
        data_dir=data_dir,
        project_root=PROJECT_ROOT,
        host=E2E_HOST,
        port=E2E_PORT,
        corpus=E2E_CORPUS,
    )

    # Graceful shutdown
    try:
        httpx.post(f"{base_url}/v1/shutdown", timeout=5.0)
        proc.wait(timeout=15)
    except Exception:
        proc.kill()
        proc.wait(timeout=5)

    shutil.rmtree(tmp, ignore_errors=True)
