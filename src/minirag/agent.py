"""Conversational RAG agent powered by Strands Agents SDK and LM Studio."""

import asyncio
import logging
import queue
import threading
from collections import deque
from collections.abc import Callable, Generator
from typing import Any, Literal, Protocol

from strands import Agent, tool
from strands.models import OpenAIModel

from minirag.chat_stream import (
    STATUS_GENERATING_QUERY_MESSAGE,
    STATUS_NO_RESULTS_MESSAGE,
    STATUS_RERANKING_MESSAGE,
    STATUS_SEARCHING_MESSAGE,
    STATUS_SEARCHING_WITH_SCOPE_MESSAGE,
    STATUS_STREAMING_ANSWER_MESSAGE,
    ChatStreamEvent,
)
from minirag.config import ContextPruningConfig
from minirag.context_pruning import ContextPruner, PruningResult, format_search_result_for_context
from minirag.corpus import CorpusManager
from minirag.lm_studio import LMStudioModelInfo

logger = logging.getLogger(__name__)

SYSTEM_PROMPT: str = (
    "You are a friendly, competent assistant that always backs up claims "
    "with data from RAG tools. ALWAYS use the search_documents tool to "
    "find relevant information before answering a question.\n\n"
    "CITATION RULES:\n"
    "- Search results are tagged as [source_key#chunkN]. The part before "
    "'#' is the source document key; the part after '#' identifies the "
    "specific chunk within that document.\n"
    "- Assign each unique SOURCE DOCUMENT (the part before '#') a "
    "sequential number starting at 1. Multiple chunks from the same "
    "source share ONE number.\n"
    "- Cite sources inline using numbered references in square brackets, "
    "e.g. [1], [2].\n"
    "- At the END of your response, include a 'Sources' section that maps "
    "each number to the source document key (without the #chunkN suffix).\n"
    "- Format the Sources section as a bullet list under an h4 heading.\n"
    "- Each source MUST be its own bullet point.\n"
    "- Format the Sources section exactly like this:\n\n"
    "#### Sources\n\n"
    "- [1] source_document_key\n"
    "- [2] another_source_key\n\n"
    "- NEVER invent, guess, or fabricate citation keys. Use ONLY the "
    "source document keys from the search results (the part before '#').\n"
    "- If the tool returns no relevant documents, clearly state that no "
    "relevant information was found in the corpus and do NOT cite any sources."
)

LM_STUDIO_BASE_URL: str = "http://127.0.0.1:1234/v1"
LM_STUDIO_STREAM_TIMEOUT_SECONDS: float = 900.0


class ChatEventSink(Protocol):
    """Queue-like sink used for cross-thread chat events."""

    def put(self, item: ChatStreamEvent | None | Exception) -> None:
        """Append one item to the stream queue."""

    def get(self, timeout: float) -> ChatStreamEvent | None | Exception:
        """Pop one item from the stream queue."""


class ChatEventQueue:
    """FIFO queue backed by a deque for one-reader chat status forwarding."""

    def __init__(self) -> None:
        """Initialize the queue."""
        self._items: deque[ChatStreamEvent | None | Exception] = deque()
        self._condition = threading.Condition()

    def put(self, item: ChatStreamEvent | None | Exception) -> None:
        """Append one item and wake the reader."""
        with self._condition:
            self._items.append(item)
            self._condition.notify()

    def get(self, timeout: float) -> ChatStreamEvent | None | Exception:
        """Pop the next item in FIFO order."""
        with self._condition:
            if not self._items:
                self._condition.wait(timeout)
            if not self._items:
                raise queue.Empty
            return self._items.popleft()


class MiniRagAgent:
    """RAG-augmented conversational agent using Strands and LM Studio.

    Each call to ``stream()`` creates a fresh Strands ``Agent`` equipped
    with a ``search_documents`` @tool. The agent autonomously decides
    when to search the corpus and uses retrieved context to generate
    grounded responses.
    """

    def __init__(
        self,
        corpus_manager: CorpusManager,
        lm_studio_base_url: str,
        context_pruning_config: ContextPruningConfig | None,
        model_info: LMStudioModelInfo | None,
        context_pruner: ContextPruner | None,
    ) -> None:
        """Initialize the agent.

        Args:
            corpus_manager: Provides per-corpus search access.
            lm_studio_base_url: OpenAI-compatible endpoint (e.g. LM Studio).
            context_pruning_config: Token-budget pruning settings for retrieved chunks.
            model_info: Optional LM Studio metadata client for context-window discovery.
            context_pruner: Optional token counter and document context pruner.
        """
        self._corpus_manager = corpus_manager
        self._lm_studio_base_url = lm_studio_base_url
        if context_pruning_config is None:
            self._context_pruning_config = ContextPruningConfig()
        else:
            self._context_pruning_config = context_pruning_config
        self._model_info = model_info
        if context_pruner is None:
            self._context_pruner = ContextPruner()
        else:
            self._context_pruner = context_pruner

    def make_search_tool(
        self,
        corpus: str,
        search_mode: str,
        top_k: int,
        alpha: float,
        reranking: bool,
        status_callback: Callable[[ChatStreamEvent], None] | None,
        context_window_tokens: int,
    ) -> Callable[..., Any]:
        """Create a @tool-decorated search function bound to a specific corpus.

        Args:
            corpus: Corpus name the tool will search against.
            search_mode: One of "hybrid", "dense", "sparse".
            top_k: Number of results to retrieve.
            alpha: Dense/sparse weighting for hybrid search.
            reranking: Whether to enable reranking for hybrid search.
            status_callback: Receives transient progress events during retrieval.
            context_window_tokens: Active model context window in tokens.

        Returns:
            A Strands @tool decorated function.
        """
        corpus_manager = self._corpus_manager

        @tool
        def search_documents(query: str) -> dict[str, object]:
            """Search the knowledge base for relevant documents.

            Use this tool to find information before answering the user's question.

            Args:
                query: The search query to find relevant documents.

            Returns:
                Search results with citation keys and document text.
            """
            _emit_status(
                status_callback,
                message=_searching_status_message(corpus_manager, corpus),
                status_type="info",
            )
            orch = corpus_manager.get(corpus)
            if search_mode == "dense":
                results = orch.search_dense(query=query, top_k=top_k)
            elif search_mode == "sparse":
                results = orch.search_sparse(query=query, top_k=top_k)
            else:
                results, _trace = orch.search_hybrid_with_trace(
                    query=query,
                    top_k=top_k,
                    alpha=alpha,
                    use_reranking=reranking,
                    reranking_candidate_callback=lambda candidate_count: _emit_reranking_candidate_status(
                        status_callback,
                        candidate_count,
                    ),
                )
            pruning = self._context_pruner.prune(
                results,
                context_window_tokens=context_window_tokens,
                document_context_fraction=self._context_pruning_config.document_context_fraction,
            )
            _emit_pruning_status(status_callback, pruning)
            results = pruning.results

            if not results:
                _emit_status(
                    status_callback,
                    message=STATUS_NO_RESULTS_MESSAGE,
                    status_type="info",
                )
                return {
                    "status": "success",
                    "content": [{"text": "No relevant documents found in the corpus."}],
                }
            chunk_count = len(results)
            document_count = len({result.document_id for result in results})
            _emit_status(
                status_callback,
                message=f"Using {chunk_count} chunks from {document_count} documents",
                status_type="info",
            )
            text = "\n\n".join(format_search_result_for_context(result) for result in results)
            return {
                "status": "success",
                "content": [{"text": text}],
            }

        return search_documents

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
        """Stream a RAG-augmented response token by token.

        Args:
            messages: Full conversation history.
            model: LLM model ID to use.
            corpus: Corpus name to search.
            search_mode: One of "hybrid", "dense", "sparse".
            top_k: Number of results to retrieve.
            alpha: Dense/sparse weighting for hybrid search.
            reranking: Whether to enable reranking.
            cancellation_event: Optional signal used to stop the active model stream.

        Yields:
            Typed status and token events for the chat stream.
        """
        last_user_msg = _extract_last_user_message(messages)
        if not last_user_msg:
            yield {"type": "token", "text": "I could not find any relevant documents in the corpus."}
            return

        prompt = _build_prompt(messages, last_user_msg)

        event_queue = ChatEventQueue()

        def status_callback(event: ChatStreamEvent) -> None:
            event_queue.put(event)

        context_window_tokens = self._context_window_tokens(model)
        search_tool = self.make_search_tool(
            corpus,
            search_mode=search_mode,
            top_k=top_k,
            alpha=alpha,
            reranking=reranking,
            status_callback=status_callback,
            context_window_tokens=context_window_tokens,
        )

        # Use the model identifier exactly as provided by LM Studio /v1/models
        openai_model = OpenAIModel(
            client_args={
                "api_key": "lm-studio",
                "base_url": self._lm_studio_base_url,
                "timeout": LM_STUDIO_STREAM_TIMEOUT_SECONDS,
            },
            model_id=model,
        )
        agent = Agent(
            model=openai_model,
            system_prompt=SYSTEM_PROMPT,
            tools=[search_tool],
        )

        yield {"type": "status", "message": STATUS_GENERATING_QUERY_MESSAGE}
        yield from stream_sync(agent, prompt, event_queue, cancellation_event=cancellation_event)

    def _context_window_tokens(self, model: str) -> int:
        """Return model context window from LM Studio metadata or fallback config."""
        if self._model_info is None:
            return self._context_pruning_config.fallback_context_window_tokens
        return self._model_info.context_window_tokens(model)


def _emit_status(
    status_callback: Callable[[ChatStreamEvent], None] | None,
    *,
    message: str,
    status_type: Literal["info", "warn", "error"],
) -> None:
    """Emit a status event if the caller provided a callback."""
    if status_callback is None:
        return
    event: ChatStreamEvent = {"type": "status", "message": message}
    event["status_type"] = status_type
    status_callback(event)


def _emit_reranking_candidate_status(
    status_callback: Callable[[ChatStreamEvent], None] | None,
    candidate_count: int,
) -> None:
    """Emit exact hybrid reranking candidate metrics before reranking runs."""
    _emit_status(
        status_callback,
        message=f"Retrieved {candidate_count} candidates for reranking",
        status_type="info",
    )
    _emit_status(
        status_callback,
        message=STATUS_RERANKING_MESSAGE,
        status_type="info",
    )


def _emit_pruning_status(
    status_callback: Callable[[ChatStreamEvent], None] | None,
    pruning: PruningResult,
) -> None:
    """Report context pruning only when it removes retrieved chunks."""
    kept_chunk_count = len(pruning.results)
    if kept_chunk_count == pruning.original_chunk_count:
        return
    _emit_status(
        status_callback,
        message=f"Pruned context to {kept_chunk_count} chunks within {pruning.token_budget} document tokens",
        status_type="info",
    )


def _searching_status_message(corpus_manager: CorpusManager, corpus: str) -> str:
    """Return scoped search status when cached corpus counts are available."""
    if not hasattr(corpus_manager, "corpus_stats"):
        return STATUS_SEARCHING_MESSAGE
    try:
        stats = corpus_manager.corpus_stats(corpus)
    except Exception:
        logger.exception("Failed to load corpus stats for status; falling back to generic search status")
        return STATUS_SEARCHING_MESSAGE
    return STATUS_SEARCHING_WITH_SCOPE_MESSAGE.format(
        document_count=stats.document_count,
        chunk_count=stats.chunk_count,
    )


def stream_sync(
    agent: Agent,
    prompt: str,
    q: ChatEventSink,
    cancellation_event: threading.Event | None,
) -> Generator[ChatStreamEvent, None, None]:
    """Bridge async stream_async to a synchronous generator via a thread + queue."""
    task_holder: dict[str, asyncio.Task[None]] = {}
    loop_holder: dict[str, asyncio.AbstractEventLoop] = {}
    thread = threading.Thread(
        target=_run_stream_consumer,
        args=(agent, prompt, q, cancellation_event, task_holder, loop_holder),
        daemon=True,
    )
    thread.start()

    stream_state = _StreamState()
    yield from _drain_stream_queue(q, cancellation_event, task_holder, loop_holder, stream_state)

    if _is_cancelled(cancellation_event):
        _cancel_model_stream(task_holder, loop_holder)
        thread.join(timeout=2.0)
        return

    thread.join()

    yield from _direct_answer_fallback_events(
        context_ready=stream_state.context_ready,
        streaming_started=stream_state.streaming_started,
        buffered_tokens=stream_state.buffered_pre_context_tokens,
    )


class _StreamState:
    """Mutable state for gating public stream events."""

    def __init__(self) -> None:
        """Initialize stream gating state."""
        self.context_ready = False
        self.streaming_started = False
        self.buffered_pre_context_tokens: list[ChatStreamEvent] = []


async def _consume_stream(
    agent: Agent,
    prompt: str,
    q: ChatEventSink,
    cancellation_event: threading.Event | None,
) -> None:
    """Consume Strands async events into the cross-thread stream queue."""
    try:
        async for event in agent.stream_async(prompt):
            if _is_cancelled(cancellation_event):
                break
            if "data" in event:
                q.put({"type": "token", "text": str(event["data"])})
    except asyncio.CancelledError:
        logger.info("Cancelled active chat model stream")
    except Exception as exc:
        q.put(exc)
    finally:
        q.put(None)


def _run_stream_consumer(
    agent: Agent,
    prompt: str,
    q: ChatEventSink,
    cancellation_event: threading.Event | None,
    task_holder: dict[str, asyncio.Task[None]],
    loop_holder: dict[str, asyncio.AbstractEventLoop],
) -> None:
    """Run the async Strands consumer in a dedicated event loop."""
    loop = asyncio.new_event_loop()
    loop_holder["loop"] = loop
    asyncio.set_event_loop(loop)
    task = loop.create_task(_consume_stream(agent, prompt, q, cancellation_event))
    task_holder["task"] = task
    try:
        loop.run_until_complete(task)
    finally:
        loop.close()


def _cancel_model_stream(
    task_holder: dict[str, asyncio.Task[None]],
    loop_holder: dict[str, asyncio.AbstractEventLoop],
) -> None:
    """Cancel the active async model stream task when it is still running."""
    task = task_holder.get("task")
    loop = loop_holder.get("loop")
    if task is None or loop is None or task.done():
        return
    loop.call_soon_threadsafe(task.cancel)


def _drain_stream_queue(
    q: ChatEventSink,
    cancellation_event: threading.Event | None,
    task_holder: dict[str, asyncio.Task[None]],
    loop_holder: dict[str, asyncio.AbstractEventLoop],
    stream_state: _StreamState,
) -> Generator[ChatStreamEvent, None, None]:
    """Drain queued events and update stream gating state."""
    while True:
        if _is_cancelled(cancellation_event):
            _cancel_model_stream(task_holder, loop_holder)
            break
        try:
            item = q.get(timeout=0.1)
        except queue.Empty:
            continue
        if item is None:
            break
        if isinstance(item, Exception):
            raise item
        yield from _process_stream_item(item, stream_state)


def _process_stream_item(
    item: ChatStreamEvent,
    stream_state: _StreamState,
) -> list[ChatStreamEvent]:
    """Prepare one queued stream item for public emission."""
    _buffer_pre_context_token(
        stream_state.buffered_pre_context_tokens,
        event=item,
        context_ready=stream_state.context_ready,
    )
    events, context_ready, streaming_started = _prepare_public_stream_events(
        item,
        context_ready=stream_state.context_ready,
        streaming_started=stream_state.streaming_started,
    )
    stream_state.context_ready = context_ready
    stream_state.streaming_started = streaming_started
    return events


def _is_cancelled(cancellation_event: threading.Event | None) -> bool:
    """Return whether caller cancellation has been requested."""
    return cancellation_event is not None and cancellation_event.is_set()


def _buffer_pre_context_token(
    buffered_tokens: list[ChatStreamEvent],
    *,
    event: ChatStreamEvent,
    context_ready: bool,
) -> None:
    """Keep non-empty direct model text in case retrieval never starts."""
    if context_ready:
        return
    if event.get("type") != "token":
        return
    text = str(event["text"]) if "text" in event else ""
    if text.strip() == "":
        return
    buffered_tokens.append(event)


def _direct_answer_fallback_events(
    *,
    context_ready: bool,
    streaming_started: bool,
    buffered_tokens: list[ChatStreamEvent],
) -> list[ChatStreamEvent]:
    """Return buffered direct model text only when no retrieval context appeared."""
    if not context_ready and not streaming_started and buffered_tokens:
        return [
            {"type": "status", "message": STATUS_STREAMING_ANSWER_MESSAGE},
            *buffered_tokens,
        ]
    if not context_ready and not streaming_started:
        return [
            {"type": "status", "message": STATUS_STREAMING_ANSWER_MESSAGE},
            {"type": "token", "text": "I could not generate a response from the model."},
        ]
    return []


def _prepare_public_stream_events(
    event: ChatStreamEvent,
    *,
    context_ready: bool,
    streaming_started: bool,
) -> tuple[list[ChatStreamEvent], bool, bool]:
    """Gate internal stream events into the public chat stream."""
    if event.get("type") == "status":
        return [event], context_ready or _is_context_ready_status(event), streaming_started

    if event.get("type") != "token":
        return [event], context_ready, streaming_started

    if not context_ready:
        return [], context_ready, streaming_started

    if streaming_started:
        return [event], context_ready, streaming_started

    return (
        [
            {"type": "status", "message": STATUS_STREAMING_ANSWER_MESSAGE},
            event,
        ],
        context_ready,
        True,
    )


def _is_context_ready_status(event: ChatStreamEvent) -> bool:
    """Return whether a status event means retrieval context is ready."""
    if event.get("type") != "status":
        return False
    message = str(event["message"]) if "message" in event else ""
    return message == STATUS_NO_RESULTS_MESSAGE or message.startswith("Using ")


def _extract_last_user_message(messages: list[dict[str, str]]) -> str:
    """Return the content of the last user message, or empty string."""
    for msg in reversed(messages):
        if msg["role"] == "user":
            return msg["content"]
    return ""


def _build_prompt(messages: list[dict[str, str]], last_user_msg: str) -> str:
    """Build a prompt that includes conversation history for multi-turn chats.

    Args:
        messages: Full conversation history.
        last_user_msg: The latest user message (already extracted).

    Returns:
        A prompt string with optional conversation context prepended.
    """
    prior = messages[:-1]
    if not prior:
        return last_user_msg

    parts: list[str] = ["Previous conversation:"]
    for msg in prior:
        role = "User" if msg["role"] == "user" else "Assistant"
        parts.append(f"{role}: {msg['content']}")
    parts.append(f"\nCurrent question: {last_user_msg}")
    return "\n".join(parts)
