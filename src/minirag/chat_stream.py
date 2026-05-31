"""Typed event payloads for chat completion streams."""

from typing import Final, Literal, TypedDict

STATUS_QUEUED_MESSAGE: Final[str] = "Preparing request..."
STATUS_GENERATING_QUERY_MESSAGE: Final[str] = "Generating search query..."
STATUS_SEARCHING_MESSAGE: Final[str] = "Searching corpus..."
STATUS_SEARCHING_WITH_SCOPE_MESSAGE: Final[str] = "Searching corpus with {document_count} documents and {chunk_count} chunks..."
STATUS_RERANKING_MESSAGE: Final[str] = "Reranking candidates..."
STATUS_STREAMING_ANSWER_MESSAGE: Final[str] = "Streaming answer..."
STATUS_NO_RESULTS_MESSAGE: Final[str] = "Using 0 chunks from 0 documents"
STATUS_RESET_MESSAGE: Final[str] = ""


class ChatStreamEvent(TypedDict, total=False):
    """Internal event shape before SSE serialization."""

    type: Literal["status", "token", "error", "done"]
    message: str
    status_type: Literal["info", "warn", "error"]
    text: str
