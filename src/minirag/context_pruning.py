"""Token-budget pruning for retrieved RAG context."""

from dataclasses import dataclass

import tiktoken

from minirag.search.types import SearchResult


@dataclass(frozen=True)
class PruningResult:
    """Result of applying a document-context token budget."""

    results: list[SearchResult]
    token_budget: int
    used_tokens: int
    original_chunk_count: int


class ContextPruner:
    """Prune ranked search results to a document-token budget."""

    def __init__(self) -> None:
        """Initialize the token encoder used for local budget estimation."""
        self._encoding = tiktoken.get_encoding("cl100k_base")

    def prune(
        self,
        results: list[SearchResult],
        *,
        context_window_tokens: int,
        document_context_fraction: float,
    ) -> PruningResult:
        """Keep highest-ranked chunks that fit within the document token budget."""
        if context_window_tokens <= 0:
            raise ValueError("context_window_tokens must be greater than 0")
        if document_context_fraction <= 0.0 or document_context_fraction > 1.0:
            raise ValueError("document_context_fraction must be in (0.0, 1.0]")

        token_budget = max(1, int(context_window_tokens * document_context_fraction))
        kept: list[SearchResult] = []
        used_tokens = 0
        for result in results:
            chunk_tokens = self.count_result_tokens(result)
            if used_tokens + chunk_tokens > token_budget:
                continue
            kept.append(result)
            used_tokens += chunk_tokens

        return PruningResult(
            results=kept,
            token_budget=token_budget,
            used_tokens=used_tokens,
            original_chunk_count=len(results),
        )

    def count_result_tokens(self, result: SearchResult) -> int:
        """Count tokens for the exact chunk text shape returned to the LLM."""
        return len(self._encoding.encode(format_search_result_for_context(result)))


def format_search_result_for_context(result: SearchResult) -> str:
    """Format one search result exactly as it appears in tool context."""
    return f"[{result.citation_key}#chunk{result.chunk_id}] {result.text}"
