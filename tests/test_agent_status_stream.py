"""Unit tests for chat status events emitted by the RAG agent."""

import asyncio
import threading
from collections.abc import Callable
from typing import Any, cast

from strands import Agent

from minirag.agent import ChatEventQueue, MiniRagAgent, stream_sync
from minirag.chat_stream import (
    STATUS_NO_RESULTS_MESSAGE,
    STATUS_RERANKING_MESSAGE,
    STATUS_SEARCHING_MESSAGE,
    STATUS_STREAMING_ANSWER_MESSAGE,
    ChatStreamEvent,
)
from minirag.corpus import CorpusManager
from minirag.orchestration import SearchTrace
from minirag.search.types import SearchResult
from minirag.storage.interface import CorpusStats


class FakeOrchestration:
    """Fake orchestration that returns configured search results."""

    def __init__(self, results: list[SearchResult], *, hybrid_candidate_count: int | None = None, reranking_active: bool = True) -> None:
        self.results = results
        self.hybrid_candidate_count = hybrid_candidate_count
        self.reranking_active = reranking_active

    def search_dense(self, query: str, top_k: int) -> list[SearchResult]:
        del query, top_k
        return self.results

    def search_sparse(self, query: str, top_k: int) -> list[SearchResult]:
        del query, top_k
        return self.results

    def search_hybrid(self, query: str, top_k: int, alpha: float | None, use_reranking: bool | None) -> list[SearchResult]:
        del query, top_k, alpha, use_reranking
        return self.results

    def search_hybrid_with_trace(
        self,
        query: str,
        top_k: int,
        alpha: float | None,
        use_reranking: bool | None,
        reranking_candidate_callback: Callable[[int], None] | None = None,
    ) -> tuple[list[SearchResult], SearchTrace]:
        del query, alpha
        candidate_count = self.hybrid_candidate_count if self.hybrid_candidate_count is not None else len(self.results)
        should_rerank = self.reranking_active and use_reranking is not False
        if should_rerank and reranking_candidate_callback is not None:
            reranking_candidate_callback(candidate_count)
        return self.results, SearchTrace(
            reranking_active=should_rerank,
            retrieval_top_k=top_k,
            dense_count=candidate_count,
            sparse_count=candidate_count,
            merged_candidate_count=candidate_count,
            final_result_count=len(self.results),
        )


class FakeCorpusManager:
    """Fake corpus manager that returns one orchestration."""

    def __init__(self, orchestration: FakeOrchestration, stats: CorpusStats | None = None) -> None:
        self.orchestration = orchestration
        self.stats = stats
        self.stats_call_count = 0

    def get(self, corpus: str) -> FakeOrchestration:
        del corpus
        return self.orchestration

    def corpus_stats(self, corpus: str) -> CorpusStats:
        del corpus
        self.stats_call_count += 1
        if self.stats is None:
            raise RuntimeError("stats unavailable")
        return self.stats


def _make_agent(
    results: list[SearchResult],
    *,
    hybrid_candidate_count: int | None = None,
    reranking_active: bool = True,
    stats: CorpusStats | None = None,
) -> MiniRagAgent:
    """Create an agent with fake search results."""
    return MiniRagAgent(
        corpus_manager=cast(
            CorpusManager,
            FakeCorpusManager(
                FakeOrchestration(
                    results,
                    hybrid_candidate_count=hybrid_candidate_count,
                    reranking_active=reranking_active,
                ),
                stats=stats,
            ),
        ),
        lm_studio_base_url="http://unused",
        context_pruning_config=None,
        model_info=None,
        context_pruner=None,
    )


def _run_tool(agent: MiniRagAgent, events: list[ChatStreamEvent], search_mode: str = "hybrid") -> dict[str, Any]:
    """Invoke the generated search tool directly."""
    search_tool = agent.make_search_tool(
        corpus="docs",
        search_mode=search_mode,
        top_k=5,
        alpha=0.4,
        reranking=True,
        status_callback=events.append,
        context_window_tokens=4096,
    )
    result = search_tool(query="query")
    assert isinstance(result, dict)
    return cast(dict[str, Any], result)


def _message(event: ChatStreamEvent) -> str:
    """Return required message from a status test event."""
    assert "message" in event
    return event["message"]


def test_search_tool_emits_searching_before_retrieval() -> None:
    """The search tool should report that retrieval has started."""
    events: list[ChatStreamEvent] = []
    agent = _make_agent(
        [
            SearchResult(
                chunk_id=1,
                document_id=1,
                citation_key="doc",
                text="alpha",
                score=0.9,
                source_path="docs/sample.txt",
                chunk_index=0,
                char_start=0,
                char_end=5,
                line_from=1,
                line_to=1,
            )
        ]
    )

    _run_tool(agent, events)

    assert _message(events[0]) == STATUS_SEARCHING_MESSAGE
    assert set(events[0]) <= {"type", "message", "status_type"}


def test_search_tool_reports_cached_corpus_scope_metrics_when_available() -> None:
    """Search status should include corpus-wide counts when the manager exposes them."""
    events: list[ChatStreamEvent] = []
    agent = _make_agent(
        [
            SearchResult(
                chunk_id=1,
                document_id=1,
                citation_key="doc",
                text="alpha",
                score=0.9,
                source_path="docs/sample.txt",
                chunk_index=0,
                char_start=0,
                char_end=5,
                line_from=1,
                line_to=1,
            )
        ],
        stats=CorpusStats(document_count=12, chunk_count=34),
    )

    _run_tool(agent, events)

    assert _message(events[0]) == "Searching corpus with 12 documents and 34 chunks..."


def test_search_tool_context_ready_counts_chunks_and_unique_documents() -> None:
    """Final context metrics should use exact results and document_id de-duplication."""
    events: list[ChatStreamEvent] = []
    agent = _make_agent(
        [
            SearchResult(
                chunk_id=1,
                document_id=10,
                citation_key="doc-a",
                text="alpha",
                score=0.9,
                source_path="docs/sample.txt",
                chunk_index=0,
                char_start=0,
                char_end=5,
                line_from=1,
                line_to=1,
            ),
            SearchResult(
                chunk_id=2,
                document_id=10,
                citation_key="doc-a",
                text="beta",
                score=0.8,
                source_path="docs/sample.txt",
                chunk_index=0,
                char_start=0,
                char_end=5,
                line_from=1,
                line_to=1,
            ),
            SearchResult(
                chunk_id=3,
                document_id=20,
                citation_key="doc-b",
                text="gamma",
                score=0.7,
                source_path="docs/sample.txt",
                chunk_index=0,
                char_start=0,
                char_end=5,
                line_from=1,
                line_to=1,
            ),
        ]
    )

    _run_tool(agent, events)

    context_events = [event for event in events if _message(event) == "Using 3 chunks from 2 documents"]
    assert context_events == [
        {
            "type": "status",
            "message": "Using 3 chunks from 2 documents",
            "status_type": "info",
        }
    ]


def test_search_tool_reports_exact_hybrid_reranking_candidate_count() -> None:
    """Hybrid reranking status should use the actual merged candidate count."""
    events: list[ChatStreamEvent] = []
    agent = _make_agent(
        [
            SearchResult(
                chunk_id=1,
                document_id=10,
                citation_key="doc-a",
                text="alpha",
                score=0.9,
                source_path="docs/sample.txt",
                chunk_index=0,
                char_start=0,
                char_end=5,
                line_from=1,
                line_to=1,
            ),
            SearchResult(
                chunk_id=2,
                document_id=20,
                citation_key="doc-b",
                text="beta",
                score=0.8,
                source_path="docs/sample.txt",
                chunk_index=0,
                char_start=0,
                char_end=5,
                line_from=1,
                line_to=1,
            ),
        ],
        hybrid_candidate_count=7,
    )

    _run_tool(agent, events, search_mode="hybrid")

    assert [_message(event) for event in events] == [
        STATUS_SEARCHING_MESSAGE,
        "Retrieved 7 candidates for reranking",
        STATUS_RERANKING_MESSAGE,
        "Using 2 chunks from 2 documents",
    ]


def test_search_tool_skips_candidate_status_when_hybrid_reranking_is_disabled() -> None:
    """Candidate status is meaningful only when hybrid reranking is active."""
    events: list[ChatStreamEvent] = []
    agent = _make_agent(
        [
            SearchResult(
                chunk_id=1,
                document_id=10,
                citation_key="doc-a",
                text="alpha",
                score=0.9,
                source_path="docs/sample.txt",
                chunk_index=0,
                char_start=0,
                char_end=5,
                line_from=1,
                line_to=1,
            )
        ],
        hybrid_candidate_count=7,
        reranking_active=False,
    )

    _run_tool(agent, events, search_mode="hybrid")

    assert [_message(event) for event in events] == [
        STATUS_SEARCHING_MESSAGE,
        "Using 1 chunks from 1 documents",
    ]


def test_search_tool_no_results_emits_zero_context_metrics() -> None:
    """Empty retrieval should emit no_results with zero chunk and document counts."""
    events: list[ChatStreamEvent] = []
    agent = _make_agent([])

    result = _run_tool(agent, events, search_mode="dense")

    assert result["content"] == [{"text": "No relevant documents found in the corpus."}]
    assert events[-1] == {
        "type": "status",
        "message": STATUS_NO_RESULTS_MESSAGE,
        "status_type": "info",
    }


def test_search_tool_prunes_context_to_token_budget_before_final_metrics() -> None:
    """Final context metrics should describe the pruned result list sent to the LLM."""
    events: list[ChatStreamEvent] = []
    agent = _make_agent(
        [
            SearchResult(
                chunk_id=1,
                document_id=10,
                citation_key="doc-a",
                text="short",
                score=0.9,
                source_path="docs/sample.txt",
                chunk_index=0,
                char_start=0,
                char_end=5,
                line_from=1,
                line_to=1,
            ),
            SearchResult(
                chunk_id=2,
                document_id=20,
                citation_key="doc-b",
                text=" ".join(["large"] * 200),
                score=0.8,
                source_path="docs/sample.txt",
                chunk_index=0,
                char_start=0,
                char_end=5,
                line_from=1,
                line_to=1,
            ),
            SearchResult(
                chunk_id=3,
                document_id=30,
                citation_key="doc-c",
                text="small",
                score=0.7,
                source_path="docs/sample.txt",
                chunk_index=0,
                char_start=0,
                char_end=5,
                line_from=1,
                line_to=1,
            ),
        ]
    )

    search_tool = agent.make_search_tool(
        corpus="docs",
        search_mode="dense",
        top_k=5,
        alpha=0.4,
        reranking=True,
        status_callback=events.append,
        context_window_tokens=80,
    )
    result = search_tool(query="query")

    messages = [_message(event) for event in events]
    assert any(message.startswith("Pruned context to 2 chunks within 48 document tokens") for message in messages)
    assert messages[-1] == "Using 2 chunks from 2 documents"
    assert result["content"] == [{"text": "[doc-a#chunk1] short\n\n[doc-c#chunk3] small"}]


class FakeStreamingAgent:
    """Fake Strands agent that emits data around tool status callbacks."""

    def __init__(self, q: ChatEventQueue, context_message: str) -> None:
        self.q = q
        self.context_message = context_message

    async def stream_async(self, prompt: str) -> Any:
        del prompt
        yield {"data": "\n\n"}
        self.q.put({"type": "status", "message": STATUS_SEARCHING_MESSAGE})
        self.q.put({"type": "status", "message": self.context_message})
        yield {"data": "Answer"}


class FakeNoToolStreamingAgent:
    """Fake Strands agent that emits direct answer text without tool status."""

    async def stream_async(self, prompt: str) -> Any:
        del prompt
        yield {"data": "\n\n"}
        yield {"data": "Direct answer"}


class FakeEmptyStreamingAgent:
    """Fake Strands agent that completes without tool status or answer text."""

    async def stream_async(self, prompt: str) -> Any:
        del prompt
        if False:
            yield {}


class FakeSlowStreamingAgent:
    """Fake Strands agent that waits long enough for cancellation."""

    def __init__(self, q: ChatEventQueue) -> None:
        self.q = q

    async def stream_async(self, prompt: str) -> Any:
        del prompt
        self.q.put({"type": "status", "message": "Using 1 chunks from 1 documents"})
        yield {"data": "first"}
        await asyncio.sleep(5)
        yield {"data": "second"}


def test_stream_sync_suppresses_model_text_until_retrieval_context_is_ready() -> None:
    """Whitespace/query-planning tokens must not leak into the answer stream."""
    q = ChatEventQueue()
    agent = cast(Agent, FakeStreamingAgent(q, "Using 1 chunks from 1 documents"))

    events = list(stream_sync(agent, "prompt", q, cancellation_event=None))

    assert events == [
        {"type": "status", "message": STATUS_SEARCHING_MESSAGE},
        {"type": "status", "message": "Using 1 chunks from 1 documents"},
        {"type": "status", "message": STATUS_STREAMING_ANSWER_MESSAGE},
        {"type": "token", "text": "Answer"},
    ]


def test_stream_sync_releases_direct_model_text_when_no_retrieval_context_arrives() -> None:
    """A model that never calls the tool should not leave the stream tokenless."""
    q = ChatEventQueue()
    agent = cast(Agent, FakeNoToolStreamingAgent())

    events = list(stream_sync(agent, "prompt", q, cancellation_event=None))

    assert events == [
        {"type": "status", "message": STATUS_STREAMING_ANSWER_MESSAGE},
        {"type": "token", "text": "Direct answer"},
    ]


def test_stream_sync_emits_fallback_token_when_model_returns_no_text() -> None:
    """A successful SSE stream should not end without any token event."""
    q = ChatEventQueue()
    agent = cast(Agent, FakeEmptyStreamingAgent())

    events = list(stream_sync(agent, "prompt", q, cancellation_event=None))

    assert events == [
        {"type": "status", "message": STATUS_STREAMING_ANSWER_MESSAGE},
        {"type": "token", "text": "I could not generate a response from the model."},
    ]


def test_stream_sync_allows_answer_after_no_results_context_status() -> None:
    """The no-results status is also a final retrieval context state."""
    q = ChatEventQueue()
    agent = cast(Agent, FakeStreamingAgent(q, STATUS_NO_RESULTS_MESSAGE))

    events = list(stream_sync(agent, "prompt", q, cancellation_event=None))

    assert events == [
        {"type": "status", "message": STATUS_SEARCHING_MESSAGE},
        {"type": "status", "message": STATUS_NO_RESULTS_MESSAGE},
        {"type": "status", "message": STATUS_STREAMING_ANSWER_MESSAGE},
        {"type": "token", "text": "Answer"},
    ]


def test_chat_event_queue_is_fifo() -> None:
    """Deque-backed event queue should preserve fire-and-forget status order."""
    q = ChatEventQueue()
    first: ChatStreamEvent = {"type": "status", "message": "first"}
    second: ChatStreamEvent = {"type": "status", "message": "second"}

    q.put(first)
    q.put(second)

    assert q.get(timeout=0) == first
    assert q.get(timeout=0) == second


def test_stream_sync_cancels_active_model_stream() -> None:
    """Cancellation should stop waiting for long-running model output."""
    q = ChatEventQueue()
    cancellation_event = threading.Event()
    agent = cast(Agent, FakeSlowStreamingAgent(q))

    events: list[ChatStreamEvent] = []
    for event in stream_sync(agent, "prompt", q, cancellation_event=cancellation_event):
        events.append(event)
        if event.get("type") == "token":
            cancellation_event.set()

    assert events == [
        {"type": "status", "message": "Using 1 chunks from 1 documents"},
        {"type": "status", "message": STATUS_STREAMING_ANSWER_MESSAGE},
        {"type": "token", "text": "first"},
    ]
