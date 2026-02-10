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
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
import yaml

from minirag.config import Config

E2E_HOST = "127.0.0.1"
E2E_PORT_NO_RERANKING = 7098
E2E_PORT_WITH_RERANKING = 7099
E2E_CORPUS = "test"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SERVER_STARTUP_TIMEOUT_S = 30
_SERVER_STARTUP_TIMEOUT_WITH_RERANKING_S = 30


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
    reranking_enabled: bool
    timings_report_path: Path


def _ensure_service_stopped(base_url: str, timeout_s: int) -> None:
    """Ensure no existing service is running on the target base URL."""
    try:
        health_response = httpx.get(f"{base_url}/v1/health", timeout=2.0)
        service_running = health_response.status_code == 200
    except (httpx.ConnectError, httpx.ReadTimeout, httpx.TimeoutException):
        return

    if not service_running:
        return

    try:
        httpx.post(f"{base_url}/v1/shutdown", timeout=5.0)
    except (httpx.ConnectError, httpx.ReadTimeout, httpx.TimeoutException):
        return

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{base_url}/v1/health", timeout=2.0)
            if response.status_code != 200:
                return
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.TimeoutException):
            return
        time.sleep(1.0)

    raise RuntimeError(f"Existing service at {base_url} did not shut down within {timeout_s}s")


def _wait_for_health_or_exit(base_url: str, timeout_s: int, proc: subprocess.Popen[bytes]) -> None:
    """Wait for healthy service or fail fast when the process exits."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            stdout, stderr = proc.communicate(timeout=5)
            raise RuntimeError(
                f"Server process exited before healthy (exit={proc.returncode}).\nstdout: {stdout.decode()}\nstderr: {stderr.decode()}"
            )

        try:
            response = httpx.get(f"{base_url}/v1/health", timeout=2.0)
            if response.status_code == 200:
                return
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.TimeoutException):
            pass
        time.sleep(1.0)

    raise RuntimeError(f"Service at {base_url} did not become healthy within {timeout_s}s")


def _resolve_test_input_source(source_data_dir: Path) -> Path:
    """Resolve test corpus source directory from data dir or repo fallback."""
    test_input_src = source_data_dir / "input" / E2E_CORPUS
    if test_input_src.exists():
        return test_input_src

    fallback_input_src = PROJECT_ROOT / "data" / "input" / E2E_CORPUS
    if fallback_input_src.exists():
        return fallback_input_src

    raise FileNotFoundError(f"test corpus not found: {test_input_src} and {fallback_input_src}")


def _prepare_corpus_input_tree(*, data_dir: Path, test_input_src: Path) -> None:
    """Create writable corpus directory and symlink read-only source subdirs."""
    corpus_dir = data_dir / "input" / E2E_CORPUS
    corpus_dir.mkdir(parents=True)

    for subdir_name in ("md", "evals", "metadata"):
        src_subdir = test_input_src / subdir_name
        if src_subdir.exists():
            os.symlink(src_subdir, corpus_dir / subdir_name)

    (corpus_dir / "txt").mkdir()


def _build_e2e_config_dict(
    *,
    project_config: Config,
    data_dir: Path,
    e2e_port: int,
    model_name: str,
    reranking_enabled: bool,
) -> dict[str, object]:
    """Build e2e configuration payload for one reranking mode."""
    return {
        "service": {
            "host": E2E_HOST,
            "port": e2e_port,
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
            "reranking": {
                "enabled": reranking_enabled,
                "model_name": project_config.search.reranking.model_name,
                "candidate_multiplier": project_config.search.reranking.candidate_multiplier,
            },
        },
    }


def _build_server_env() -> dict[str, str]:
    """Build environment for e2e server subprocess."""
    return {
        **os.environ,
        "PYTHONPATH": str(PROJECT_ROOT / "src"),
        # Improve stability on macOS when FAISS/FastText and torch-based reranking run together.
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "TOKENIZERS_PARALLELISM": "false",
    }


@pytest.fixture(scope="class", params=[False, True], ids=["reranking_off", "reranking_on"])
def e2e_env(request: pytest.FixtureRequest):
    """Start a real server subprocess and yield E2EEnv."""
    reranking_enabled = bool(request.param)
    e2e_port = E2E_PORT_WITH_RERANKING if reranking_enabled else E2E_PORT_NO_RERANKING
    startup_timeout_s = _SERVER_STARTUP_TIMEOUT_WITH_RERANKING_S if reranking_enabled else _SERVER_STARTUP_TIMEOUT_S

    project_config_path = PROJECT_ROOT / "config.yaml"
    if not project_config_path.exists():
        pytest.skip(f"Project config not found at {project_config_path}")
    project_config = Config.from_yaml(project_config_path)
    source_data_dir = project_config.resolve_data_dir(PROJECT_ROOT)

    mode_label = "reranking-on" if reranking_enabled else "reranking-off"
    tmp = tempfile.mkdtemp(prefix=f"minirag-e2e-lifecycle-{mode_label}-")
    data_dir = Path(tmp)
    (data_dir / "models").mkdir()
    (data_dir / "storage").mkdir()
    (data_dir / "index").mkdir(parents=True)

    model_name = project_config.index.embeddings.model_name
    model_src = source_data_dir / "models" / model_name
    if not model_src.exists():
        shutil.rmtree(tmp, ignore_errors=True)
        pytest.skip(f"FastText model not found at {model_src} – run 'just init'")
    os.symlink(model_src, data_dir / "models" / model_name)

    try:
        test_input_src = _resolve_test_input_source(source_data_dir)
    except FileNotFoundError as exc:
        shutil.rmtree(tmp, ignore_errors=True)
        pytest.skip(str(exc))

    _prepare_corpus_input_tree(data_dir=data_dir, test_input_src=test_input_src)

    config_dict = _build_e2e_config_dict(
        project_config=project_config,
        data_dir=data_dir,
        e2e_port=e2e_port,
        model_name=model_name,
        reranking_enabled=reranking_enabled,
    )

    config_path = data_dir / "config_e2e.yaml"
    with config_path.open("w", encoding="utf-8") as fh:
        yaml.dump(config_dict, fh, default_flow_style=False)

    reports_dir = PROJECT_ROOT / "reports" / "e2e"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timings_report_path = reports_dir / f"query_timings_{mode_label}.jsonl"
    if timings_report_path.exists():
        timings_report_path.unlink()

    base_url = f"http://{E2E_HOST}:{e2e_port}"
    _ensure_service_stopped(base_url=base_url, timeout_s=30)

    # Start server subprocess
    launcher = PROJECT_ROOT / "tests_e2e" / "start_server.py"
    env = _build_server_env()
    proc = subprocess.Popen(
        ["uv", "run", str(launcher), str(config_path)],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    try:
        _wait_for_health_or_exit(base_url=base_url, timeout_s=startup_timeout_s, proc=proc)
    except RuntimeError as exc:
        if proc.poll() is None:
            proc.kill()
            proc.communicate(timeout=5)
        shutil.rmtree(tmp, ignore_errors=True)
        raise RuntimeError(f"Server failed to start: {exc}") from exc

    print()
    print("=" * 90)
    print(f"E2E MODE: {mode_label} (reranking_enabled={reranking_enabled})")
    print("=" * 90)
    print()

    yield E2EEnv(
        base_url=base_url,
        config_path=config_path,
        data_dir=data_dir,
        project_root=PROJECT_ROOT,
        host=E2E_HOST,
        port=e2e_port,
        corpus=E2E_CORPUS,
        reranking_enabled=reranking_enabled,
        timings_report_path=timings_report_path,
    )

    # Graceful shutdown
    try:
        if proc.poll() is None:
            with suppress(httpx.ConnectError, httpx.ReadTimeout, httpx.TimeoutException):
                httpx.post(f"{base_url}/v1/shutdown", timeout=5.0)

            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)

        shutil.rmtree(tmp, ignore_errors=True)
