"""Conversational RAG agent powered by Strands Agents SDK and LM Studio."""

import asyncio
import logging
import queue
import threading
from collections.abc import Callable, Generator
from typing import Any

from strands import Agent, tool
from strands.models import OpenAIModel

from minirag.corpus import CorpusManager

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
    ) -> None:
        """Initialize the agent.

        Args:
            corpus_manager: Provides per-corpus search access.
            lm_studio_base_url: OpenAI-compatible endpoint (e.g. LM Studio).
        """
        self._corpus_manager = corpus_manager
        self._lm_studio_base_url = lm_studio_base_url

    def _make_search_tool(
        self,
        corpus: str,
        search_mode: str,
        top_k: int,
        alpha: float,
        reranking: bool,
    ) -> Callable[..., Any]:
        """Create a @tool-decorated search function bound to a specific corpus.

        Args:
            corpus: Corpus name the tool will search against.
            search_mode: One of "hybrid", "dense", "sparse".
            top_k: Number of results to retrieve.
            alpha: Dense/sparse weighting for hybrid search.
            reranking: Whether to enable reranking for hybrid search.

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
            orch = corpus_manager.get(corpus)
            if search_mode == "dense":
                results = orch.search_dense(query=query, top_k=top_k)
            elif search_mode == "sparse":
                results = orch.search_sparse(query=query, top_k=top_k)
            else:
                results = orch.search_hybrid(
                    query=query,
                    top_k=top_k,
                    alpha=alpha,
                    use_reranking=reranking,
                )
            if not results:
                return {
                    "status": "success",
                    "content": [{"text": "No relevant documents found in the corpus."}],
                }
            text = "\n\n".join(f"[{r.citation_key}#chunk{r.chunk_id}] {r.text}" for r in results)
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
    ) -> Generator[str, None, None]:
        """Stream a RAG-augmented response token by token.

        Args:
            messages: Full conversation history.
            model: LLM model ID to use.
            corpus: Corpus name to search.
            search_mode: One of "hybrid", "dense", "sparse".
            top_k: Number of results to retrieve.
            alpha: Dense/sparse weighting for hybrid search.
            reranking: Whether to enable reranking.

        Yields:
            Text chunks of the agent's response.
        """
        last_user_msg = _extract_last_user_message(messages)
        if not last_user_msg:
            yield "I could not find any relevant documents in the corpus."
            return

        prompt = _build_prompt(messages, last_user_msg)
        search_tool = self._make_search_tool(
            corpus,
            search_mode=search_mode,
            top_k=top_k,
            alpha=alpha,
            reranking=reranking,
        )

        # Strands requires openai/ prefix for models served via OpenAI-compatible APIs
        strands_model_id = model if model.startswith("openai/") else f"openai/{model}"

        openai_model = OpenAIModel(
            client_args={
                "api_key": "lm-studio",
                "base_url": self._lm_studio_base_url,
            },
            model_id=strands_model_id,
        )
        agent = Agent(
            model=openai_model,
            system_prompt=SYSTEM_PROMPT,
            tools=[search_tool],
        )

        yield from _stream_sync(agent, prompt)


def _stream_sync(agent: Agent, prompt: str) -> Generator[str, None, None]:
    """Bridge async stream_async to a synchronous generator via a thread + queue."""
    q: queue.Queue[str | None | Exception] = queue.Queue()

    async def _consume() -> None:
        try:
            async for event in agent.stream_async(prompt):
                if "data" in event:
                    q.put(event["data"])
        except Exception as exc:
            q.put(exc)
        finally:
            q.put(None)

    def _run() -> None:
        asyncio.run(_consume())

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    while True:
        item = q.get()
        if item is None:
            break
        if isinstance(item, Exception):
            raise item
        yield item

    thread.join()


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
