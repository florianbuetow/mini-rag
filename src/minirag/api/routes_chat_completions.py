"""Chat completions endpoint with SSE streaming."""

import json
import logging
import threading
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any, Protocol

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from starlette.responses import StreamingResponse

from minirag.api.responses import error_response
from minirag.api.utils import ensure_healthy
from minirag.chat_stream import STATUS_QUEUED_MESSAGE, STATUS_RESET_MESSAGE, ChatStreamEvent


class StreamableAgent(Protocol):
    """Protocol for agents that support streaming responses."""

    def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        corpus: str,
        search_mode: str,
        top_k: int,
        alpha: float,
        reranking: bool,
        cancellation_event: threading.Event,
    ) -> Generator[ChatStreamEvent, None, None]:
        """Yield typed events for a streaming chat response."""
        ...


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1")


class ChatMessage(BaseModel):
    """A single chat message."""

    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    """Request body for chat completions."""

    messages: list[ChatMessage]
    model: str
    corpus: str
    search_mode: str = "hybrid"
    top_k: int = 50
    alpha: float = 0.5
    reranking: bool = True

    @field_validator("messages")
    @classmethod
    def validate_messages_not_empty(cls, value: list[ChatMessage]) -> list[ChatMessage]:
        """Ensure at least one message is provided."""
        if len(value) == 0:
            raise ValueError("messages must not be empty")
        return value

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

    @field_validator("search_mode")
    @classmethod
    def validate_search_mode(cls, value: str) -> str:
        """Ensure search_mode is one of the allowed values."""
        allowed = {"hybrid", "dense", "sparse"}
        if value not in allowed:
            raise ValueError(f"search_mode must be one of {sorted(allowed)}")
        return value

    @field_validator("top_k")
    @classmethod
    def validate_top_k(cls, value: int) -> int:
        """Ensure top_k is positive."""
        if value <= 0:
            raise ValueError("top_k must be greater than 0")
        return value

    @field_validator("alpha")
    @classmethod
    def validate_alpha(cls, value: float) -> float:
        """Ensure alpha is in [0.0, 1.0]."""
        if value < 0.0 or value > 1.0:
            raise ValueError("alpha must be between 0.0 and 1.0")
        return value


def _sse_event(event_name: str, payload: dict[str, object]) -> str:
    """Serialize one named SSE event with a single JSON data field."""
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event_name}\ndata: {data}\n\n"


def _status_payload(message: str, status_type: str) -> dict[str, object]:
    """Build the public status payload."""
    if status_type not in {"info", "warn", "error"}:
        status_type = "info"
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "message": message,
        "type": status_type,
    }


def _normalize_agent_event(event: ChatStreamEvent | str) -> tuple[str, dict[str, object]]:
    """Map an internal agent event to public SSE event name and payload."""
    if isinstance(event, str):
        return "token", {"text": event}

    event_type = _event_type(event)
    if event_type == "token":
        return "token", {"text": _event_text(event)}
    if event_type == "status":
        return "status", _status_payload(
            message=_event_message(event),
            status_type=_event_status_type(event),
        )
    if event_type == "error":
        return "error", {"message": _event_error_message(event)}
    if event_type == "done":
        return "done", {}
    return "error", {"message": f"unknown stream event type: {event_type}"}


def _event_type(event: ChatStreamEvent) -> str:
    """Return event type while preserving compatibility with legacy fake agents."""
    if "type" in event:
        return event["type"]
    return "token"


def _event_text(event: ChatStreamEvent) -> str:
    """Return token text while preserving compatibility with incomplete fake events."""
    if "text" in event:
        return str(event["text"])
    return ""


def _event_message(event: ChatStreamEvent) -> str:
    """Return a status message while preserving compatibility with incomplete fake events."""
    if "message" in event:
        return str(event["message"])
    return ""


def _event_status_type(event: ChatStreamEvent) -> str:
    """Return a status type while preserving compatibility with incomplete fake events."""
    if "status_type" in event:
        return str(event["status_type"])
    return "info"


def _event_error_message(event: ChatStreamEvent) -> str:
    """Return an error message while preserving compatibility with incomplete fake events."""
    if "message" in event:
        return str(event["message"])
    return "stream failed"


def stream_agent_response(
    agent: StreamableAgent,
    messages: list[dict[str, str]],
    model: str,
    corpus: str,
    search_mode: str,
    top_k: int,
    alpha: float,
    reranking: bool,
    cancellation_event: threading.Event,
) -> Generator[str, None, None]:
    """Stream the agent response as SSE events.

    Args:
        agent: The conversational agent with a stream() method.
        messages: The conversation history.
        model: The LLM model to use.
        corpus: The corpus to query.
        search_mode: Search mode (hybrid, dense, sparse).
        top_k: Number of results to retrieve.
        alpha: Dense/sparse weighting for hybrid search.
        reranking: Whether to enable reranking.
        cancellation_event: Optional signal set when the stream closes early.

    Yields:
        SSE-formatted event strings.
    """
    try:
        try:
            yield _sse_event("status", _status_payload(STATUS_QUEUED_MESSAGE, "info"))
            for agent_event in _agent_stream(
                agent=agent,
                messages=messages,
                model=model,
                corpus=corpus,
                search_mode=search_mode,
                top_k=top_k,
                alpha=alpha,
                reranking=reranking,
                cancellation_event=cancellation_event,
            ):
                if cancellation_event.is_set():
                    break
                event_name, payload = _normalize_agent_event(agent_event)
                yield _sse_event(event_name, payload)
        except Exception as exc:
            logger.exception("Error during agent streaming")
            if not cancellation_event.is_set():
                yield _sse_event("error", {"message": str(exc)})

        if not cancellation_event.is_set():
            yield _sse_event("status", _status_payload(STATUS_RESET_MESSAGE, "info"))
            yield _sse_event("done", {})
    finally:
        cancellation_event.set()


def _agent_stream(
    *,
    agent: StreamableAgent,
    messages: list[dict[str, str]],
    model: str,
    corpus: str,
    search_mode: str,
    top_k: int,
    alpha: float,
    reranking: bool,
    cancellation_event: threading.Event,
) -> Generator[ChatStreamEvent | str, None, None]:
    """Call the agent stream, falling back for older test doubles."""
    kwargs: dict[str, Any] = {
        "messages": messages,
        "model": model,
        "corpus": corpus,
        "search_mode": search_mode,
        "top_k": top_k,
        "alpha": alpha,
        "reranking": reranking,
        "cancellation_event": cancellation_event,
    }
    try:
        yield from agent.stream(**kwargs)
    except TypeError as exc:
        if "cancellation_event" not in str(exc):
            raise
        kwargs.pop("cancellation_event")
        yield from agent.stream(**kwargs)


@router.post("/chat/completions", response_model=None)
async def chat_completions(request: Request, body: ChatCompletionRequest) -> StreamingResponse | JSONResponse:
    """Stream a chat completion response via SSE."""
    guard = ensure_healthy(request)
    if guard is not None:
        return guard

    # Validate corpus exists
    corpus_manager = request.app.state.corpus_manager
    if hasattr(corpus_manager, "corpus_exists"):
        if not corpus_manager.corpus_exists(body.corpus):
            return error_response(status=422, message=f"corpus not found: {body.corpus}")
    elif hasattr(corpus_manager, "list_corpora") and body.corpus not in corpus_manager.list_corpora():
        return error_response(status=422, message=f"corpus not found: {body.corpus}")

    agent = request.app.state.agent
    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    cancellation_event = threading.Event()

    return StreamingResponse(
        content=stream_agent_response(
            agent,
            messages,
            body.model,
            body.corpus,
            search_mode=body.search_mode,
            top_k=body.top_k,
            alpha=body.alpha,
            reranking=body.reranking,
            cancellation_event=cancellation_event,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
