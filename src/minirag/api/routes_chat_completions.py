"""Chat completions endpoint with SSE streaming."""

import logging
from collections.abc import Generator
from typing import Protocol

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from starlette.responses import StreamingResponse

from minirag.api.responses import error_response
from minirag.api.utils import ensure_healthy


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
    ) -> Generator[str, None, None]:
        """Yield text chunks for a streaming chat response."""
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
    top_k: int = 10
    alpha: float = 0.7
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


def _stream_agent_response(
    agent: StreamableAgent,
    messages: list[dict[str, str]],
    model: str,
    corpus: str,
    search_mode: str,
    top_k: int,
    alpha: float,
    reranking: bool,
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

    Yields:
        SSE-formatted event strings.
    """
    try:
        for chunk in agent.stream(
            messages=messages,
            model=model,
            corpus=corpus,
            search_mode=search_mode,
            top_k=top_k,
            alpha=alpha,
            reranking=reranking,
        ):
            yield f"data: {chunk}\n\n"
    except Exception as exc:
        logger.exception("Error during agent streaming")
        yield f"data: error: {exc}\n\n"

    yield "data: [DONE]\n\n"


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

    return StreamingResponse(
        content=_stream_agent_response(
            agent,
            messages,
            body.model,
            body.corpus,
            search_mode=body.search_mode,
            top_k=body.top_k,
            alpha=body.alpha,
            reranking=body.reranking,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
