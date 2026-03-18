"""Layer C — Integration tests: Chat completion contract.

Tests 8-10 from specifications2.md section 7:
8. Chat completion route returns SSE and [DONE].
9. Chat completion route rejects invalid corpus.
10. Chat completion route streams error when model provider fails.
"""

import shutil
from pathlib import Path

import httpx
import pytest

from tests_integration.helpers_runtime import (
    create_temp_data_dir,
    find_free_port,
    ingest_corpus,
    lm_studio_available,
    seed_corpus,
    start_service,
    stop_service,
    wait_for_service,
)

PROJECT_ROOT: Path = Path(__file__).parent.parent
SEED_DATA_DIR: Path = PROJECT_ROOT / "tests_e2e" / "seed_data"


pytestmark = [
    pytest.mark.integration,
    pytest.mark.timeout(120),
]


@pytest.fixture(scope="module")
def completions_service():
    """Start service with seeded knowledgebase for completion tests.

    Yields (base_url, tmp_dir).
    """
    tmp_dir = create_temp_data_dir()
    data_dir = tmp_dir / "data"

    seed_corpus(tmp_dir, "knowledgebase", SEED_DATA_DIR / "knowledgebase" / "txt")

    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    proc = start_service(port, data_dir)

    ready = wait_for_service(f"{base_url}/v1/health", timeout=30.0)
    if not ready:
        stop_service(proc, base_url)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        pytest.fail(f"Service did not start on port {port}")

    ingest_corpus(base_url, "knowledgebase", data_dir)

    yield base_url, tmp_dir

    stop_service(proc, base_url)
    shutil.rmtree(tmp_dir, ignore_errors=True)


def _parse_sse_events(response: httpx.Response) -> list[str]:
    """Parse SSE events from response text."""
    return [line[6:] for line in response.text.splitlines() if line.startswith("data: ")]


class TestChatCompletionSSE:
    """Test 8: Chat completion returns SSE stream with [DONE]."""

    def test_sse_stream_with_done(self, completions_service) -> None:
        if not lm_studio_available():
            pytest.skip("LM Studio not running — cannot test real completions")

        base_url, _ = completions_service
        with httpx.Client(base_url=base_url, timeout=60.0) as client:
            resp = client.post(
                "/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": "What is RAG?"}],
                    "model": "test-model",
                    "corpus": "knowledgebase",
                },
            )
            assert resp.status_code == 200
            events = _parse_sse_events(resp)
            assert "[DONE]" in events, f"SSE stream missing [DONE]: {events[-5:]}"
            non_done = [e for e in events if e != "[DONE]"]
            assert len(non_done) >= 1, "Expected at least one content chunk"


class TestChatCompletionValidation:
    """Test 9: Rejects invalid corpus."""

    def test_rejects_invalid_corpus(self, completions_service) -> None:
        base_url, _ = completions_service
        with httpx.Client(base_url=base_url, timeout=10.0) as client:
            resp = client.post(
                "/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": "test"}],
                    "model": "test-model",
                    "corpus": "nonexistent_corpus",
                },
            )
            assert resp.status_code == 422, f"Expected 422 for invalid corpus, got {resp.status_code}"


@pytest.fixture(scope="module")
def broken_lm_service():
    """Start service with LM Studio pointed at an unreachable port.

    Yields (base_url, tmp_dir).
    """
    tmp_dir = create_temp_data_dir()
    data_dir = tmp_dir / "data"

    seed_corpus(tmp_dir, "knowledgebase", SEED_DATA_DIR / "knowledgebase" / "txt")

    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    # Point to a port that nothing listens on
    bogus_lm_port = find_free_port()
    proc = start_service(
        port,
        data_dir,
        config_env={"MINIRAG_LM_STUDIO_URL": f"http://127.0.0.1:{bogus_lm_port}/v1"},
    )

    ready = wait_for_service(f"{base_url}/v1/health", timeout=30.0)
    if not ready:
        stop_service(proc, base_url)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        pytest.fail(f"Service did not start on port {port}")

    ingest_corpus(base_url, "knowledgebase", data_dir)

    yield base_url, tmp_dir

    stop_service(proc, base_url)
    shutil.rmtree(tmp_dir, ignore_errors=True)


class TestChatCompletionStreamError:
    """Test 10: Stream error when model provider fails."""

    def test_streams_error_when_model_unavailable(self, broken_lm_service) -> None:
        """When LM Studio is unreachable, SSE stream should contain error and [DONE]."""
        base_url, _ = broken_lm_service
        with httpx.Client(base_url=base_url, timeout=60.0) as client:
            resp = client.post(
                "/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": "test"}],
                    "model": "test-model",
                    "corpus": "knowledgebase",
                },
            )
            # The route always returns 200 with SSE — errors appear in the stream
            assert resp.status_code == 200
            events = _parse_sse_events(resp)
            assert "[DONE]" in events, f"SSE stream missing [DONE] after error: {events[-5:]}"
            # At least one event should contain an error indicator
            error_events = [e for e in events if "error" in e.lower()]
            assert len(error_events) >= 1, f"Expected error event in stream, got: {events}"
