"""Chat persistence CRUD endpoints."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from minirag.api.responses import error_response, success_response
from minirag.api.utils import ensure_healthy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1")


_DEFAULT_SEARCH_SETTINGS: dict[str, object] = {
    "search_mode": "hybrid",
    "top_k": 50,
    "alpha": 0.5,
    "reranking": True,
}


class CreateChatRequest(BaseModel):
    """Request body for creating a new chat."""

    model: str
    corpus: str
    name: str | None = None
    search_settings: dict[str, object] | None = None

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        """Ensure model is non-empty."""
        if not value.strip():
            raise ValueError("model must not be empty")
        return value

    @field_validator("corpus")
    @classmethod
    def validate_corpus(cls, value: str) -> str:
        """Ensure corpus is non-empty."""
        if not value.strip():
            raise ValueError("corpus must not be empty")
        return value


class UpdateChatRequest(BaseModel):
    """Request body for updating a chat."""

    name: str | None = None
    messages: list[dict[str, str]] | None = None
    search_settings: dict[str, object] | None = None


def _get_chats_dir(request: Request) -> Path:
    """Get the chats directory from app state."""
    data_dir: Path = request.app.state.data_dir
    return data_dir / "chats"


def _generate_chat_id() -> str:
    """Generate a timestamp-based chat ID with microsecond precision."""
    now = datetime.now(tz=UTC)
    return now.strftime("%Y%m%d-%H%M%S-") + f"{now.microsecond:06d}"


def _default_chat_name() -> str:
    """Generate a default chat name from the current datetime."""
    return datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S")


def _read_chat(chat_file: Path) -> dict[str, object] | None:
    """Read and parse a chat JSON file. Returns None if invalid."""
    try:
        with chat_file.open("r", encoding="utf-8") as f:
            data: object = json.load(f)
        if isinstance(data, dict):
            return cast(dict[str, object], data)
        return None
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read chat file %s: %s", chat_file, exc)
        return None


def _write_chat(chat_file: Path, chat_data: dict[str, object]) -> None:
    """Write chat data to a JSON file atomically (temp file + rename).

    Writing in place with "w" truncates the target before the new content is
    written, so a crash or disconnect mid-write leaves a 0-byte, unreadable
    chat. Writing to a temp file and renaming keeps the existing file intact
    until the full new content is safely on disk.
    """
    temp_file = chat_file.parent / f"{chat_file.name}.tmp"
    with temp_file.open("w", encoding="utf-8") as f:
        json.dump(chat_data, f, indent=2, ensure_ascii=False)
    temp_file.replace(chat_file)


def _chat_id_from_filename(filename: str) -> str:
    """Extract chat ID from filename (remove .json extension)."""
    return filename.removesuffix(".json")


def _find_chat_file(chats_dir: Path, chat_id: str) -> Path | None:
    """Find a chat file by ID. Returns None if not found."""
    chat_file = chats_dir / f"{chat_id}.json"
    if chat_file.exists():
        return chat_file
    return None


@router.post("/chats")
async def create_chat(request: Request, body: CreateChatRequest) -> JSONResponse:
    """Create a new chat."""
    guard = ensure_healthy(request)
    if guard is not None:
        return guard

    chats_dir = _get_chats_dir(request)
    chats_dir.mkdir(parents=True, exist_ok=True)

    chat_id = _generate_chat_id()
    now_iso = datetime.now(tz=UTC).isoformat()
    chat_name = body.name if body.name is not None else _default_chat_name()

    chat_data: dict[str, object] = {
        "id": chat_id,
        "name": chat_name,
        "model": body.model,
        "corpus": body.corpus,
        "messages": [],
        "search_settings": body.search_settings if body.search_settings is not None else dict(_DEFAULT_SEARCH_SETTINGS),
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    chat_file = chats_dir / f"{chat_id}.json"
    _write_chat(chat_file, chat_data)

    return success_response(status=201, data=chat_data)


@router.get("/chats")
async def list_chats(request: Request) -> JSONResponse:
    """List all chats (summary: id, name, updated_at)."""
    guard = ensure_healthy(request)
    if guard is not None:
        return guard

    chats_dir = _get_chats_dir(request)
    if not chats_dir.exists():
        return success_response(status=200, data={"chats": []})

    chats: list[dict[str, object]] = []
    for chat_file in chats_dir.glob("*.json"):
        chat_data = _read_chat(chat_file)
        if chat_data is None:
            continue
        chats.append(
            {
                # Older chat files may lack these fields — defaults are required
                "id": chat_data.get("id", _chat_id_from_filename(chat_file.name)),  # nosemgrep: xrag.no-dict-get-with-default
                "name": chat_data.get("name", ""),  # nosemgrep: xrag.no-dict-get-with-default
                "updated_at": chat_data.get("updated_at", ""),  # nosemgrep: xrag.no-dict-get-with-default
            }
        )

    chats.sort(key=lambda c: str(c.get("updated_at", "")), reverse=True)  # nosemgrep: xrag.no-dict-get-with-default

    return success_response(status=200, data={"chats": chats})


@router.get("/chats/{chat_id}")
async def get_chat(request: Request, chat_id: str) -> JSONResponse:
    """Load a specific chat by ID."""
    guard = ensure_healthy(request)
    if guard is not None:
        return guard

    chats_dir = _get_chats_dir(request)
    chat_file = _find_chat_file(chats_dir, chat_id)
    if chat_file is None:
        return error_response(status=404, message=f"chat not found: {chat_id}")

    chat_data = _read_chat(chat_file)
    if chat_data is None:
        return error_response(status=500, message=f"corrupted chat file: {chat_id}")

    return success_response(status=200, data=chat_data)


@router.put("/chats/{chat_id}")
async def update_chat(request: Request, chat_id: str, body: UpdateChatRequest) -> JSONResponse:
    """Update a chat (rename or replace messages)."""
    guard = ensure_healthy(request)
    if guard is not None:
        return guard

    chats_dir = _get_chats_dir(request)
    chat_file = _find_chat_file(chats_dir, chat_id)
    if chat_file is None:
        return error_response(status=404, message=f"chat not found: {chat_id}")

    chat_data = _read_chat(chat_file)
    if chat_data is None:
        return error_response(status=500, message=f"corrupted chat file: {chat_id}")

    if body.name is not None:
        chat_data["name"] = body.name
    if body.messages is not None:
        chat_data["messages"] = body.messages
    if body.search_settings is not None:
        chat_data["search_settings"] = body.search_settings

    chat_data["updated_at"] = datetime.now(tz=UTC).isoformat()
    _write_chat(chat_file, chat_data)

    return success_response(status=200, data=chat_data)


@router.post("/chats/{chat_id}/generate-title")
async def generate_title(request: Request, chat_id: str) -> JSONResponse:
    """Generate a short title for a chat using the conversation content."""
    guard = ensure_healthy(request)
    if guard is not None:
        return guard

    chats_dir = _get_chats_dir(request)
    chat_file = _find_chat_file(chats_dir, chat_id)
    if chat_file is None:
        return error_response(status=404, message=f"chat not found: {chat_id}")

    chat_data = _read_chat(chat_file)
    if chat_data is None:
        return error_response(status=500, message=f"corrupted chat file: {chat_id}")

    messages_raw = chat_data.get("messages")  # nosemgrep: xrag.no-dict-get-with-default
    if not messages_raw or not isinstance(messages_raw, list):
        return error_response(status=400, message="chat has no messages")

    messages = cast(list[dict[str, str]], messages_raw)
    model_raw = chat_data.get("model")  # nosemgrep: xrag.no-dict-get-with-default
    if not model_raw or not isinstance(model_raw, str):
        return error_response(status=400, message="chat has no model set")

    title_agent = request.app.state.title_agent
    try:
        import asyncio

        title = await asyncio.to_thread(title_agent.generate_title, messages, model_raw)
    except Exception as exc:
        logger.exception("Failed to generate title for chat %s", chat_id)
        return error_response(status=500, message=f"title generation failed: {exc}")

    chat_data["name"] = title
    chat_data["updated_at"] = datetime.now(tz=UTC).isoformat()
    _write_chat(chat_file, chat_data)

    return success_response(status=200, data=chat_data)


@router.delete("/chats/{chat_id}")
async def delete_chat(request: Request, chat_id: str) -> JSONResponse:
    """Delete a chat by ID."""
    guard = ensure_healthy(request)
    if guard is not None:
        return guard

    chats_dir = _get_chats_dir(request)
    chat_file = _find_chat_file(chats_dir, chat_id)
    if chat_file is None:
        return error_response(status=404, message=f"chat not found: {chat_id}")

    chat_file.unlink()
    return success_response(status=200, data={"message": f"chat {chat_id} deleted"})
