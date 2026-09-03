"""Fixtures for MCP server end-to-end tests.

Lifecycle:
    1. Read project config.yaml to locate the real data directory.
    2. Create a temporary data directory with symlinks to model and test corpus.
    3. Write an MCP-specific config file pointing to the temp data dir.
    4. Start the API server as a subprocess.
    5. Poll the health endpoint until the API server is ready.
    6. Run md2txt and ingest to populate the test corpus.
    7. Start the MCP server subprocess and initialize the client.
    8. Yield environment info to the test session.
    9. Shut down MCP client, API server, and remove temporary directory.
"""

import os
import shutil
import subprocess
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
import yaml

from minirag.config import Config
from tests_mcp.mcp_client import McpClient

MCP_HOST = "127.0.0.1"
MCP_PORT = 7097
MCP_CORPUS = "test"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Cold-loading the optional fastText model can exceed the default test timeout.
_SERVER_STARTUP_TIMEOUT_S = 120
_COMMAND_TIMEOUT_S = 30


@dataclass(frozen=True)
class McpEnv:
    """Environment info yielded to MCP lifecycle tests."""

    base_url: str
    config_path: Path
    data_dir: Path
    corpus: str
    mcp_client: McpClient


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

    deadline_mono = __import__("time").monotonic() + timeout_s
    while __import__("time").monotonic() < deadline_mono:
        try:
            response = httpx.get(f"{base_url}/v1/health", timeout=2.0)
            if response.status_code != 200:
                return
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.TimeoutException):
            return
        __import__("time").sleep(1.0)

    raise RuntimeError(f"Existing service at {base_url} did not shut down within {timeout_s}s")


def _read_available(stream) -> str:
    """Read buffered subprocess output without waiting for inherited pipes to close."""
    if stream is None:
        return ""
    with suppress(Exception):
        os.set_blocking(stream.fileno(), False)
        return stream.read().decode(errors="replace")
    return ""


def _wait_for_health_or_exit(base_url: str, timeout_s: int, proc: subprocess.Popen[bytes]) -> None:
    """Wait for healthy service or fail fast when the process exits."""
    import time

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

    stdout = _read_available(proc.stdout)
    stderr = _read_available(proc.stderr)
    raise RuntimeError(f"Service at {base_url} did not become healthy within {timeout_s}s.\nstdout: {stdout}\nstderr: {stderr}")


def _resolve_test_input_source() -> Path:
    """Resolve test corpus source directory from repo-local test fixtures."""
    test_input_src = PROJECT_ROOT / "data" / "input" / MCP_CORPUS
    if test_input_src.exists():
        return test_input_src

    raise FileNotFoundError(f"test corpus not found: {test_input_src}")


def _prepare_corpus_input_tree(*, data_dir: Path, test_input_src: Path) -> None:
    """Create writable corpus directory and symlink read-only source subdirs."""
    corpus_dir = data_dir / "input" / MCP_CORPUS
    corpus_dir.mkdir(parents=True)

    for subdir_name in ("md", "evals", "metadata"):
        src_subdir = test_input_src / subdir_name
        if src_subdir.exists():
            os.symlink(src_subdir, corpus_dir / subdir_name)

    (corpus_dir / "txt").mkdir()


def _build_mcp_config_dict(
    *,
    project_config: Config,
    data_dir: Path,
    model_name: str,
) -> dict[str, object]:
    """Build MCP test configuration payload (reranking always off)."""
    return {
        "service": {
            "host": MCP_HOST,
            "port": MCP_PORT,
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
                "db_filename": "minirag_mcp.db",
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
                "enabled": False,
                "model_name": project_config.search.reranking.model_name,
                "candidate_multiplier": project_config.search.reranking.candidate_multiplier,
            },
        },
    }


def _build_server_env() -> dict[str, str]:
    """Build environment for the API server subprocess."""
    return {
        **os.environ,
        "PYTHONPATH": str(PROJECT_ROOT / "src"),
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "TOKENIZERS_PARALLELISM": "false",
    }


def _create_temp_data_dir(project_config: Config) -> tuple[Path, Path]:
    """Create temp data dir with model symlink and corpus input tree.

    Returns (data_dir, config_path).
    """
    tmp = tempfile.mkdtemp(prefix="minirag-mcp-")
    data_dir = Path(tmp)
    (data_dir / "models").mkdir()
    (data_dir / "storage").mkdir()
    (data_dir / "index").mkdir(parents=True)

    model_name = project_config.index.embeddings.model_name
    model_src = PROJECT_ROOT / "data" / "models" / model_name
    if not model_src.is_file():
        shutil.rmtree(tmp, ignore_errors=True)
        pytest.skip(f"FastText model not found at {model_src} — run 'just init'")
    os.symlink(model_src, data_dir / "models" / model_name)

    try:
        test_input_src = _resolve_test_input_source()
    except FileNotFoundError as exc:
        shutil.rmtree(tmp, ignore_errors=True)
        pytest.skip(str(exc))

    _prepare_corpus_input_tree(data_dir=data_dir, test_input_src=test_input_src)

    config_dict = _build_mcp_config_dict(
        project_config=project_config,
        data_dir=data_dir,
        model_name=model_name,
    )
    config_path = data_dir / "config_mcp.yaml"
    with config_path.open("w", encoding="utf-8") as fh:
        yaml.dump(config_dict, fh, default_flow_style=False)

    return data_dir, config_path


def _populate_corpus(config_path: Path) -> None:
    """Run md2txt and ingest to populate the test corpus."""
    md2txt_result = subprocess.run(
        ["uv", "run", "scripts/md2txt.py", "--config", str(config_path)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=_COMMAND_TIMEOUT_S,
    )
    assert md2txt_result.returncode == 0, f"md2txt failed:\nstdout: {md2txt_result.stdout}\nstderr: {md2txt_result.stderr}"

    ingest_result = subprocess.run(
        ["uv", "run", "scripts/ingest.py", "--corpus", MCP_CORPUS, "--config", str(config_path)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=_COMMAND_TIMEOUT_S,
    )
    assert ingest_result.returncode == 0, f"ingest failed:\nstdout: {ingest_result.stdout}\nstderr: {ingest_result.stderr}"

    description_source = config_path.parent / "corpus-description.md"
    description_source.write_text("# MCP Test Corpus\n\nQuantum computing fixture corpus.\n", encoding="utf-8")
    description_result = subprocess.run(
        [
            "uv",
            "run",
            "scripts/ingest_corpus_description.py",
            "--corpus",
            MCP_CORPUS,
            "--file",
            str(description_source),
            "--config",
            str(config_path),
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=_COMMAND_TIMEOUT_S,
    )
    assert description_result.returncode == 0, (
        f"description ingest failed:\nstdout: {description_result.stdout}\nstderr: {description_result.stderr}"
    )


def _start_mcp_client(base_url: str) -> McpClient:
    """Start the MCP server subprocess and initialize the client."""
    mcp_cwd = str(PROJECT_ROOT / "mcp")
    client_env = {
        **os.environ,
        "REST_BASE": base_url,
    }
    client = McpClient(
        command=["npx", "tsx", "mini-rag.ts"],
        env=client_env,
        cwd=mcp_cwd,
    )
    client.initialize()
    client.list_tools()
    return client


def _shutdown_api_server(base_url: str, api_proc: subprocess.Popen[bytes]) -> None:
    """Gracefully shut down the API server, kill if needed."""
    try:
        if api_proc.poll() is None:
            with suppress(httpx.ConnectError, httpx.ReadTimeout, httpx.TimeoutException):
                httpx.post(f"{base_url}/v1/shutdown", timeout=5.0)

            try:
                api_proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                api_proc.kill()
                api_proc.wait(timeout=5)
    finally:
        if api_proc.poll() is None:
            api_proc.kill()
            api_proc.wait(timeout=5)


@pytest.fixture(scope="class")
def mcp_env():
    """Start API server, populate corpus, start MCP server, yield McpEnv."""
    if shutil.which("npx") is None:
        pytest.skip("npx not found — Node.js required for MCP tests")

    project_config_path = PROJECT_ROOT / "config.yaml"
    if not project_config_path.exists():
        pytest.skip(f"Project config not found at {project_config_path}")
    project_config = Config.from_yaml(project_config_path)

    data_dir, config_path = _create_temp_data_dir(project_config)
    tmp = str(data_dir)

    base_url = f"http://{MCP_HOST}:{MCP_PORT}"
    _ensure_service_stopped(base_url=base_url, timeout_s=30)

    launcher = PROJECT_ROOT / "tests_e2e" / "start_server.py"
    env = _build_server_env()
    api_proc = subprocess.Popen(
        ["uv", "run", str(launcher), str(config_path)],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    mcp_client = None
    try:
        _wait_for_health_or_exit(base_url=base_url, timeout_s=_SERVER_STARTUP_TIMEOUT_S, proc=api_proc)
        _populate_corpus(config_path)
        mcp_client = _start_mcp_client(base_url)
    except Exception:
        if mcp_client is not None:
            mcp_client.close()
        if api_proc.poll() is None:
            _shutdown_api_server(base_url, api_proc)
        shutil.rmtree(tmp, ignore_errors=True)
        raise

    print()
    print("=" * 90)
    print("MCP TEST: API + MCP servers running, corpus populated")
    print("=" * 90)
    print()

    yield McpEnv(
        base_url=base_url,
        config_path=config_path,
        data_dir=data_dir,
        corpus=MCP_CORPUS,
        mcp_client=mcp_client,
    )

    try:
        mcp_client.close()
    finally:
        try:
            _shutdown_api_server(base_url, api_proc)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
