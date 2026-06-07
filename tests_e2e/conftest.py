"""Shared fixtures for Chat UI end-to-end tests.

Production-server fixtures require:
- mini-rag service running on port 9191
- LM Studio running on port 1234 (for model-related tests)

Deterministic fixtures (for @pytest.mark.deterministic tests) run a local
FastAPI test server on a free port with fake models/corpora/streaming.
"""

import json
import os
import shutil
import tempfile
import threading
import time
from collections.abc import Generator, Iterator
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from minirag.api.responses import error_response, success_response
from minirag.api.routes_chats import router as chats_router
from minirag.api.utils import ensure_healthy

# Skip collecting broken test modules with missing imports
collect_ignore = ["test_lifecycle.py"]

PROJECT_ROOT: Path = Path(__file__).parent.parent
BASE_URL: str = "http://localhost:9191"
LM_STUDIO_URL: str = "http://127.0.0.1:1234"

# ---------------------------------------------------------------------------
# Deterministic fake data
# ---------------------------------------------------------------------------
FAKE_MODELS: list[dict[str, str]] = [
    {"id": "gemma-3-1b", "object": "model"},
    {"id": "qwen-2.5-7b", "object": "model"},
    {"id": "llama-3.1-70b", "object": "model"},
]

FAKE_CORPORA: list[str] = ["alpha", "beta", "gamma"]

FAKE_STREAM_CHUNKS: list[str] = ["Hello", " from", " the", " deterministic", " agent."]

# Server-side error tracking for deterministic test server
_server_errors: list[tuple[str, Exception]] = []

# Markdown response split into newline-safe chunks (SSE strips \n from data lines).
# Each \n must be sent as its own chunk so the frontend accumulates the full text.
FAKE_MARKDOWN_TEXT: str = (
    "# Research Summary\n\n"
    "The study found **significant results** in *quantum computing*.\n\n"
    "## Key Findings\n\n"
    "1. First finding with `inline code`\n"
    "2. Second finding\n\n"
    '```python\ndef hello():\n    print("world")\n```\n\n'
    "[feynman2026quantum] described the theoretical framework. "
    "See also [cousteau2026coral] for related work.\n\n"
    "| Column A | Column B |\n|----------|----------|\n| Value 1  | Value 2  |\n\n"
    "For more info visit [Example](https://example.com).\n"
)


# ---------------------------------------------------------------------------
# Mark helper
# ---------------------------------------------------------------------------
def _is_deterministic(request: pytest.FixtureRequest) -> bool:
    """Check if the current test is marked as deterministic."""
    return any(m.name == "deterministic" for m in request.node.iter_markers())


def _sse_event(event_name: str, payload: dict[str, object]) -> str:
    """Build one named SSE event."""
    if event_name == "status":
        payload = {
            "timestamp": "2026-05-23T00:00:00+00:00",
            "message": str(payload.get("message", "")),
            "type": str(payload.get("type", "info")),
        }
    return f"event: {event_name}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"


# ---------------------------------------------------------------------------
# Production-server fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def base_url() -> str:
    """Base URL for the mini-rag service."""
    return BASE_URL


@pytest.fixture()
def api_client() -> Iterator[httpx.Client]:
    """httpx client for API-level setup/teardown (production server)."""
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        yield client


@pytest.fixture(autouse=True)
def clean_chats(request: pytest.FixtureRequest) -> Iterator[None]:
    """Delete all chats before and after each test.

    Skipped for deterministic tests (they have their own cleanup).

    DESTRUCTIVE: this deletes every chat on the server at BASE_URL. If that
    server is a developer's real instance (e.g. started via ``just start``),
    these tests would wipe real conversations. To prevent that, production
    cleanup runs only when ``MINIRAG_E2E_ALLOW_DESTRUCTIVE=1`` is set; that flag
    must point at a throwaway test instance, never real data.
    """
    if _is_deterministic(request):
        yield
        return
    if os.environ.get("MINIRAG_E2E_ALLOW_DESTRUCTIVE") != "1":
        pytest.skip(
            f"Refusing to delete all chats on the live server at {BASE_URL}: "
            "set MINIRAG_E2E_ALLOW_DESTRUCTIVE=1 only against a throwaway "
            "test instance to run production-server e2e tests."
        )
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        _delete_all_production(client)
        yield
        _delete_all_production(client)


@pytest.fixture(autouse=True)
def _fail_on_server_errors() -> Iterator[None]:
    """Fail fast if the deterministic test server raised unhandled exceptions."""
    _server_errors.clear()
    yield
    if _server_errors:
        details = "\n".join(f"  {path}: {type(exc).__name__}: {exc}" for path, exc in _server_errors)
        pytest.fail(f"Unhandled server-side exception(s) during test:\n{details}")


@pytest.fixture(autouse=True)
def _fail_on_console_errors(request: pytest.FixtureRequest, page) -> Iterator[None]:
    """Fail fast if unexpected browser console.error calls occurred.

    Tests that intentionally trigger console errors must be marked with
    @pytest.mark.expect_console_errors to opt out.
    """
    if any(m.name == "expect_console_errors" for m in request.node.iter_markers()):
        yield
        return
    errors: list[str] = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    yield
    if errors:
        details = "\n".join(f"  {e}" for e in errors)
        pytest.fail(f"Browser console.error(s) during test:\n{details}")


@pytest.fixture(autouse=True)
def navigate_to_app(
    request: pytest.FixtureRequest,
    page,
    clean_chats: None,
    _fail_on_console_errors: None,
) -> None:
    """Navigate to the app before each test (after cleaning chats).

    Skipped for deterministic tests (they use det_navigate).
    """
    if _is_deterministic(request):
        return
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")


def _delete_all_production(client: httpx.Client) -> None:
    """Delete all chats via the production API."""
    try:
        resp = client.get("/v1/chats")
        if resp.status_code == 200:
            for chat in resp.json().get("data", {}).get("chats", []):
                client.delete(f"/v1/chats/{chat['id']}")
    except httpx.ConnectError:
        pytest.skip("mini-rag service not running on port 9191")


# ---------------------------------------------------------------------------
# Deterministic test server internals
# ---------------------------------------------------------------------------
def _build_fake_info_router() -> APIRouter:
    """Build a router with fake /v1/models, /v1/corpora, /v1/health."""
    router = APIRouter(prefix="/v1")

    @router.get("/health")
    async def health(request: Request) -> JSONResponse:
        return success_response(status=200, data={"status": request.app.state.app_status})

    @router.get("/models")
    async def models(request: Request) -> JSONResponse:
        guard = ensure_healthy(request)
        if guard is not None:
            return guard
        return JSONResponse(content={"data": FAKE_MODELS})

    @router.get("/corpora")
    async def corpora(request: Request) -> JSONResponse:
        guard = ensure_healthy(request)
        if guard is not None:
            return guard
        return success_response(status=200, data={"corpora": FAKE_CORPORA})

    return router


def _build_normal_stream() -> Generator[str, None, None]:
    """Build a normal SSE stream from FAKE_STREAM_CHUNKS."""
    yield _sse_event("status", {"phase": "queued", "message": "Preparing request..."})
    yield _sse_event(
        "status",
        {"phase": "searching", "message": "Searching corpus...", "search_mode": "hybrid", "top_k": 5, "reranking": True},
    )
    yield _sse_event("status", {"phase": "context_ready", "message": "Using 5 chunks from 2 documents", "chunks": 5, "documents": 2})
    yield _sse_event("status", {"phase": "streaming_answer", "message": "Streaming answer..."})
    for chunk in FAKE_STREAM_CHUNKS:
        yield _sse_event("token", {"text": chunk})
    yield _sse_event("status", {"message": ""})
    yield _sse_event("done", {})


def _build_markdown_stream() -> Generator[str, None, None]:
    """Build an SSE stream with markdown content.

    SSE "data: X\\n\\n" strips \\n from X. Each text line is sent as its own
    data event and each newline as an empty "data: \\n\\n" event.
    The frontend treats empty data as a newline character.
    """
    yield _sse_event("status", {"phase": "queued", "message": "Preparing request..."})
    yield _sse_event("status", {"phase": "context_ready", "message": "Using 8 chunks from 3 documents", "chunks": 8, "documents": 3})
    for line in FAKE_MARKDOWN_TEXT.split("\n"):
        if line:
            yield _sse_event("token", {"text": line})
        yield _sse_event("token", {"text": "\n"})
    yield _sse_event("status", {"message": ""})
    yield _sse_event("done", {})


def _build_error_stream() -> Generator[str, None, None]:
    """Build an SSE stream that simulates a streaming error."""
    yield _sse_event("status", {"phase": "queued", "message": "Preparing request..."})
    yield _sse_event("token", {"text": "Partial"})
    yield _sse_event("error", {"message": "simulated streaming error"})
    yield _sse_event("status", {"message": ""})
    yield _sse_event("done", {})


def _build_fake_completions_router() -> APIRouter:
    """Build a router with fake streaming /v1/chat/completions."""
    router = APIRouter(prefix="/v1")

    @router.post("/chat/completions")
    async def completions(request: Request) -> JSONResponse:
        guard = ensure_healthy(request)
        if guard is not None:
            return guard

        body = await request.json()

        corpus = body.get("corpus", "")
        if corpus not in FAKE_CORPORA:
            return error_response(status=422, message=f"corpus not found: {corpus}")

        messages = body.get("messages", [])
        if not messages:
            return error_response(status=422, message="messages must not be empty")

        last_msg = messages[-1].get("content", "")
        if "TRIGGER_STREAM_ERROR" in last_msg:
            chunks = _build_error_stream()
        elif "TRIGGER_MARKDOWN" in last_msg:
            chunks = _build_markdown_stream()
        else:
            chunks = _build_normal_stream()

        from starlette.responses import StreamingResponse

        return StreamingResponse(
            content=chunks,
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    return router


class _FakeCorpusManager:
    def list_corpora(self) -> list[str]:
        return list(FAKE_CORPORA)

    def corpus_exists(self, name: str) -> bool:
        return name in FAKE_CORPORA


class _FakeConfig:
    def model_dump(self) -> dict[str, object]:
        return {"service": {"host": "127.0.0.1", "port": 0}}

    def get_service_config(self) -> object:
        class _SC:
            reload = False

        return _SC()


class _FakeTitleAgent:
    def generate_title(self, messages: list[dict[str, str]], model: str) -> str:
        return "Test Chat Title"


def _create_test_app(chats_dir: Path) -> FastAPI:
    """Create a FastAPI app for deterministic E2E tests."""
    app = FastAPI()
    app.state.app_status = "healthy"
    app.state.config = _FakeConfig()
    app.state.corpus_manager = _FakeCorpusManager()
    app.state.title_agent = _FakeTitleAgent()
    app.state.data_dir = chats_dir.parent

    async def _capture_server_exception(request: Request, exc: Exception) -> JSONResponse:
        _server_errors.append((request.url.path, exc))
        return JSONResponse(status_code=500, content={"error": str(exc)})

    app.add_exception_handler(Exception, _capture_server_exception)

    app.include_router(_build_fake_info_router())
    app.include_router(_build_fake_completions_router())
    app.include_router(chats_router)

    web_dir = PROJECT_ROOT / "web"
    if web_dir.exists():
        app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="static")

    return app


class _TestServer:
    """Runs a uvicorn server in a background thread."""

    def __init__(self, app: FastAPI, port: int) -> None:
        self.app = app
        self.port = port
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        config = uvicorn.Config(
            app=self.app,
            host="127.0.0.1",
            port=self.port,
            log_level="error",
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                resp = httpx.get(f"http://127.0.0.1:{self.port}/v1/health", timeout=1.0)
                if resp.status_code == 200:
                    return
            except httpx.ConnectError:
                pass
            time.sleep(0.2)
        raise RuntimeError(f"Test server did not start on port {self.port}")

    def stop(self) -> None:
        if self._server:
            self._server.should_exit = True
        if self._thread:
            self._thread.join(timeout=5)


def _find_free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


# ---------------------------------------------------------------------------
# Deterministic test fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def deterministic_server() -> Iterator[tuple[str, Path]]:
    """Start a deterministic test server for the session.

    Yields (base_url, chats_dir).
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="minirag_det_"))
    chats_dir = tmp_dir / "chats"
    chats_dir.mkdir(parents=True)

    port = _find_free_port()
    app = _create_test_app(chats_dir)
    server = _TestServer(app, port)
    server.start()

    yield f"http://127.0.0.1:{port}", chats_dir

    server.stop()
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture()
def det_base_url(deterministic_server: tuple[str, Path]) -> str:
    """Base URL of the deterministic test server."""
    return deterministic_server[0]


@pytest.fixture()
def det_chats_dir(deterministic_server: tuple[str, Path]) -> Path:
    """Path to the chats directory of the deterministic test server."""
    return deterministic_server[1]


@pytest.fixture()
def det_api_client(det_base_url: str) -> Iterator[httpx.Client]:
    """httpx client pointed at the deterministic test server."""
    with httpx.Client(base_url=det_base_url, timeout=10.0) as client:
        yield client


@pytest.fixture(autouse=True)
def det_clean_chats(
    request: pytest.FixtureRequest,
    deterministic_server: tuple[str, Path],
) -> Iterator[None]:
    """Delete all chats before and after each deterministic test.

    No-op for non-deterministic tests.
    """
    if not _is_deterministic(request):
        yield
        return
    base_url, chats_dir = deterministic_server
    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        _delete_all_deterministic(client)
        for f in chats_dir.glob("*.json"):
            f.unlink()
        yield
        _delete_all_deterministic(client)
        for f in chats_dir.glob("*.json"):
            f.unlink()


@pytest.fixture(autouse=True)
def det_navigate(
    request: pytest.FixtureRequest,
    page,
    det_base_url: str,
    det_clean_chats: None,
    _fail_on_console_errors: None,
) -> None:
    """Navigate to the deterministic test app before each test.

    No-op for non-deterministic tests.
    """
    if not _is_deterministic(request):
        return
    page.goto(det_base_url)
    page.wait_for_load_state("networkidle")


def _delete_all_deterministic(client: httpx.Client) -> None:
    """Delete all chats on the deterministic test server."""
    try:
        resp = client.get("/v1/chats")
        if resp.status_code == 200:
            for chat in resp.json().get("data", {}).get("chats", []):
                client.delete(f"/v1/chats/{chat['id']}")
    except httpx.ConnectError:
        pass
