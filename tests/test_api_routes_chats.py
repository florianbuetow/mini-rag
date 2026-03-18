"""Unit tests for chat persistence CRUD endpoints.

Spec: docs/specs/chat-persistence-specification.md
Test spec: docs/specs/chat-persistence-test-specification.md

These tests will FAIL until the chat persistence feature is implemented.
"""

import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from minirag.api.app import unhandled_exception_handler
from minirag.api.routes_info import router as info_router


class FakeServiceConfig:
    def __init__(self, reload: bool) -> None:
        self.reload = reload


class FakeConfig:
    def model_dump(self):
        return {"service": {"host": "127.0.0.1", "port": 9191}}

    def get_service_config(self):
        return FakeServiceConfig(reload=False)


class FakeCorpusManager:
    def list_corpora(self) -> list[str]:
        return ["docs"]


def _make_app(data_dir: Path, status: str = "healthy") -> FastAPI:
    """Create app with chat routes.

    Imports the chat router that does not exist yet — will fail until implemented.
    """
    from minirag.api.routes_chats import router as chats_router  # noqa: F401

    app = FastAPI()
    app.state.app_status = status
    app.state.config = FakeConfig()
    app.state.corpus_manager = FakeCorpusManager()
    app.state.data_dir = data_dir
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(info_router)
    app.include_router(chats_router)
    return app


def _create_chat(client: TestClient, model: str = "gemma-3-1b", corpus: str = "docs", name: str | None = None):
    """Helper to create a chat and return the response JSON data."""
    body = {"model": model, "corpus": corpus}
    if name is not None:
        body["name"] = name
    resp = client.post("/v1/chats", json=body)
    assert resp.status_code == 201
    return resp.json()["data"]


# TS-1: Create a new chat
def test_create_chat_with_model_and_corpus(tmp_path: Path):
    client = TestClient(_make_app(tmp_path))

    resp = client.post("/v1/chats", json={"model": "gemma-3-1b", "corpus": "docs"})

    assert resp.status_code == 201
    chat = resp.json()["data"]
    assert isinstance(chat["id"], str) and len(chat["id"]) > 0
    assert chat["model"] == "gemma-3-1b"
    assert chat["corpus"] == "docs"
    assert chat["messages"] == []
    assert "created_at" in chat
    assert "updated_at" in chat
    assert "name" in chat


# TS-2: Default chat name is datetime
def test_create_chat_default_name_is_datetime(tmp_path: Path):
    client = TestClient(_make_app(tmp_path))

    resp = client.post("/v1/chats", json={"model": "gemma-3-1b", "corpus": "docs"})

    assert resp.status_code == 201
    name = resp.json()["data"]["name"]
    # Expected format: "2026-03-11 14:30:22" (or similar datetime pattern)
    assert re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", name)


# TS-3: List all chats
def test_list_chats_returns_summary_entries(tmp_path: Path):
    client = TestClient(_make_app(tmp_path))
    _create_chat(client)
    _create_chat(client)

    resp = client.get("/v1/chats")

    assert resp.status_code == 200
    chats = resp.json()["data"]["chats"]
    assert len(chats) == 2
    for chat in chats:
        assert "id" in chat
        assert "name" in chat
        assert "updated_at" in chat
        assert "messages" not in chat


# TS-4: Chats sorted by most recent first
def test_list_chats_sorted_by_updated_at_descending(tmp_path: Path):
    client = TestClient(_make_app(tmp_path))
    _create_chat(client, name="Chat A")
    time.sleep(0.05)  # ensure different timestamps
    _create_chat(client, name="Chat B")

    resp = client.get("/v1/chats")

    chats = resp.json()["data"]["chats"]
    assert len(chats) == 2
    # Chat B (created later) should appear first
    assert chats[0]["name"] == "Chat B"
    assert chats[1]["name"] == "Chat A"


# TS-5: Load a specific chat
def test_get_chat_returns_full_object(tmp_path: Path):
    client = TestClient(_make_app(tmp_path))
    chat = _create_chat(client)
    chat_id = chat["id"]

    # Add messages via PUT
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
        {"role": "user", "content": "how are you?"},
    ]
    client.put(f"/v1/chats/{chat_id}", json={"messages": messages})

    resp = client.get(f"/v1/chats/{chat_id}")

    assert resp.status_code == 200
    loaded = resp.json()["data"]
    assert len(loaded["messages"]) == 3
    assert loaded["messages"][0]["content"] == "hello"


# TS-6: Load non-existent chat
def test_get_chat_returns_404_for_nonexistent(tmp_path: Path):
    client = TestClient(_make_app(tmp_path))

    resp = client.get("/v1/chats/nonexistent-id")

    assert resp.status_code == 404


# TS-7: Rename a chat
def test_update_chat_rename(tmp_path: Path):
    client = TestClient(_make_app(tmp_path))
    chat = _create_chat(client, name="old name")
    chat_id = chat["id"]
    original_updated_at = chat["updated_at"]
    time.sleep(0.05)

    resp = client.put(f"/v1/chats/{chat_id}", json={"name": "new name"})

    assert resp.status_code == 200
    updated = resp.json()["data"]
    assert updated["name"] == "new name"
    assert updated["updated_at"] > original_updated_at


# TS-8: Update chat messages
def test_update_chat_messages(tmp_path: Path):
    client = TestClient(_make_app(tmp_path))
    chat = _create_chat(client)
    chat_id = chat["id"]
    original_updated_at = chat["updated_at"]
    time.sleep(0.05)

    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]
    resp = client.put(f"/v1/chats/{chat_id}", json={"messages": messages})

    assert resp.status_code == 200
    updated = resp.json()["data"]
    assert len(updated["messages"]) == 2
    assert updated["updated_at"] > original_updated_at


# TS-9: Update non-existent chat
def test_update_chat_returns_404_for_nonexistent(tmp_path: Path):
    client = TestClient(_make_app(tmp_path))

    resp = client.put("/v1/chats/nonexistent-id", json={"name": "test"})

    assert resp.status_code == 404


# TS-10: Delete a chat
def test_delete_chat_removes_it(tmp_path: Path):
    client = TestClient(_make_app(tmp_path))
    chat = _create_chat(client)
    chat_id = chat["id"]

    resp = client.delete(f"/v1/chats/{chat_id}")

    assert resp.status_code == 200

    # Verify it's gone
    get_resp = client.get(f"/v1/chats/{chat_id}")
    assert get_resp.status_code == 404

    list_resp = client.get("/v1/chats")
    chat_ids = [c["id"] for c in list_resp.json()["data"]["chats"]]
    assert chat_id not in chat_ids


# TS-11: Delete non-existent chat
def test_delete_chat_returns_404_for_nonexistent(tmp_path: Path):
    client = TestClient(_make_app(tmp_path))

    resp = client.delete("/v1/chats/nonexistent-id")

    assert resp.status_code == 404


# TS-12: Empty chat list
def test_list_chats_empty_when_none_exist(tmp_path: Path):
    client = TestClient(_make_app(tmp_path))

    resp = client.get("/v1/chats")

    assert resp.status_code == 200
    assert resp.json()["data"]["chats"] == []


# TS-13: Auto-create chats directory
def test_create_chat_auto_creates_directory(tmp_path: Path):
    chats_dir = tmp_path / "chats"
    assert not chats_dir.exists()

    client = TestClient(_make_app(tmp_path))
    _create_chat(client)

    assert chats_dir.exists()


# TS-14: Concurrent chat creation
def test_concurrent_chat_creation_unique_ids(tmp_path: Path):
    app = _make_app(tmp_path)

    def create_one(_: int) -> httpx.Response:
        c = TestClient(app)
        return c.post("/v1/chats", json={"model": "gemma-3-1b", "corpus": "docs"})

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(create_one, range(5)))

    assert all(r.status_code == 201 for r in results)
    ids = [r.json()["data"]["id"] for r in results]
    assert len(set(ids)) == 5  # all unique


# TS-15: Invalid request body
def test_create_chat_invalid_json_returns_422(tmp_path: Path):
    client = TestClient(_make_app(tmp_path))

    resp = client.post(
        "/v1/chats",
        content=b"not valid json",
        headers={"Content-Type": "application/json"},
    )

    assert resp.status_code in (400, 422)


# TS-16: Missing required fields
def test_create_chat_missing_fields_returns_422(tmp_path: Path):
    client = TestClient(_make_app(tmp_path))

    resp = client.post("/v1/chats", json={})

    assert resp.status_code == 422


# TS-17: Corrupted chat file
def test_list_chats_excludes_corrupted_files(tmp_path: Path):
    client = TestClient(_make_app(tmp_path))

    # Create a valid chat
    valid_chat = _create_chat(client)

    # Write a corrupted file directly to the chats directory
    chats_dir = tmp_path / "chats"
    chats_dir.mkdir(exist_ok=True)
    corrupted_file = chats_dir / "20260101-000000.json"
    corrupted_file.write_text("NOT VALID JSON {{{")

    resp = client.get("/v1/chats")

    assert resp.status_code == 200
    chats = resp.json()["data"]["chats"]
    # Only the valid chat should appear
    assert len(chats) == 1
    assert chats[0]["id"] == valid_chat["id"]


# TS-18: Reject when service unhealthy
def test_chats_returns_503_when_unhealthy(tmp_path: Path):
    client = TestClient(_make_app(tmp_path, status="shutting_down"))

    resp = client.get("/v1/chats")

    assert resp.status_code == 503


# --- Generate title tests ---


class FakeTitleAgent:
    """Fake title agent that returns a fixed title."""

    def __init__(self, title: str = "Test Chat Title") -> None:
        self._title = title

    def generate_title(self, messages: list[dict[str, str]], model: str) -> str:
        return self._title


class FailingTitleAgent:
    """Title agent that always raises an error."""

    def generate_title(self, messages: list[dict[str, str]], model: str) -> str:
        raise RuntimeError("LM Studio unreachable")


def _make_app_with_title_agent(data_dir: Path, title_agent: object, status: str = "healthy") -> FastAPI:
    """Create app with chat routes and a title agent."""
    from minirag.api.routes_chats import router as chats_router  # noqa: F401

    app = FastAPI()
    app.state.app_status = status
    app.state.config = FakeConfig()
    app.state.corpus_manager = FakeCorpusManager()
    app.state.data_dir = data_dir
    app.state.title_agent = title_agent
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.include_router(info_router)
    app.include_router(chats_router)
    return app


# TS-19: Generate title for a chat with messages
def test_generate_title_updates_chat_name(tmp_path: Path):
    title_agent = FakeTitleAgent(title="RAG System Discussion")
    app = _make_app_with_title_agent(tmp_path, title_agent)
    client = TestClient(app)

    # Create a chat and add messages
    chat = _create_chat(client)
    chat_id = chat["id"]
    messages = [
        {"role": "user", "content": "What is RAG?"},
        {"role": "assistant", "content": "RAG stands for Retrieval Augmented Generation."},
    ]
    client.put(f"/v1/chats/{chat_id}", json={"messages": messages})

    resp = client.post(f"/v1/chats/{chat_id}/generate-title")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "RAG System Discussion"

    # Verify the name persisted
    get_resp = client.get(f"/v1/chats/{chat_id}")
    assert get_resp.json()["data"]["name"] == "RAG System Discussion"


# TS-20: Generate title for non-existent chat
def test_generate_title_returns_404_for_nonexistent(tmp_path: Path):
    title_agent = FakeTitleAgent()
    app = _make_app_with_title_agent(tmp_path, title_agent)
    client = TestClient(app)

    resp = client.post("/v1/chats/nonexistent-id/generate-title")

    assert resp.status_code == 404


# --- Search settings persistence tests ---


# TS-SS-1: Create chat with search settings
def test_create_chat_with_search_settings(tmp_path: Path):
    client = TestClient(_make_app(tmp_path))

    settings = {"search_mode": "dense", "top_k": 5, "alpha": 0.3, "reranking": False}
    resp = client.post("/v1/chats", json={"model": "gemma-3-1b", "corpus": "docs", "search_settings": settings})

    assert resp.status_code == 201
    chat = resp.json()["data"]
    assert chat["search_settings"] == settings


# TS-SS-2: Create chat without search settings gets defaults
def test_create_chat_default_search_settings(tmp_path: Path):
    client = TestClient(_make_app(tmp_path))

    resp = client.post("/v1/chats", json={"model": "gemma-3-1b", "corpus": "docs"})

    assert resp.status_code == 201
    chat = resp.json()["data"]
    assert chat["search_settings"] == {"search_mode": "hybrid", "top_k": 10, "alpha": 0.7, "reranking": True}


# TS-SS-3: Update search settings
def test_update_chat_search_settings(tmp_path: Path):
    client = TestClient(_make_app(tmp_path))
    chat = _create_chat(client)
    chat_id = chat["id"]

    new_settings = {"search_mode": "sparse", "top_k": 20, "alpha": 0.5, "reranking": False}
    resp = client.put(f"/v1/chats/{chat_id}", json={"search_settings": new_settings})

    assert resp.status_code == 200
    updated = resp.json()["data"]
    assert updated["search_settings"] == new_settings


# TS-SS-4: Search settings persist across load
def test_search_settings_persist_across_load(tmp_path: Path):
    client = TestClient(_make_app(tmp_path))

    settings = {"search_mode": "dense", "top_k": 15, "alpha": 0.9, "reranking": True}
    chat = _create_chat(client)
    chat_id = chat["id"]
    client.put(f"/v1/chats/{chat_id}", json={"search_settings": settings})

    resp = client.get(f"/v1/chats/{chat_id}")

    assert resp.status_code == 200
    loaded = resp.json()["data"]
    assert loaded["search_settings"] == settings


# TS-21: Generate title for chat with no messages
def test_generate_title_returns_400_for_empty_chat(tmp_path: Path):
    title_agent = FakeTitleAgent()
    app = _make_app_with_title_agent(tmp_path, title_agent)
    client = TestClient(app)

    chat = _create_chat(client)
    chat_id = chat["id"]

    resp = client.post(f"/v1/chats/{chat_id}/generate-title")

    assert resp.status_code == 400


# TS-22: Generate title when agent fails
def test_generate_title_returns_500_on_agent_failure(tmp_path: Path):
    title_agent = FailingTitleAgent()
    app = _make_app_with_title_agent(tmp_path, title_agent)
    client = TestClient(app)

    chat = _create_chat(client)
    chat_id = chat["id"]
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]
    client.put(f"/v1/chats/{chat_id}", json={"messages": messages})

    resp = client.post(f"/v1/chats/{chat_id}/generate-title")

    assert resp.status_code == 500
    assert "title generation failed" in resp.json()["error"]
