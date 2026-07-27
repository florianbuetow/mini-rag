"""Unit tests for token-budget context pruning."""

import tiktoken

from minirag.context_pruning import ContextPruner, format_search_result_for_context
from minirag.search.types import SearchResult


def _result(chunk_id: int, text: str) -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id,
        document_id=chunk_id,
        citation_key=f"doc-{chunk_id}",
        text=text,
        score=1.0 / chunk_id,
        source_path=f"docs/doc-{chunk_id}.txt",
        chunk_index=0,
        char_start=0,
        char_end=len(text),
        line_from=1,
        line_to=1,
    )


def test_context_pruner_preserves_order_and_budget() -> None:
    """Pruning should keep ranked order and skip chunks that exceed the budget."""
    pruner = ContextPruner()
    first = _result(1, "short")
    oversized = _result(2, " ".join(["large"] * 200))
    third = _result(3, "also short")

    pruned = pruner.prune(
        [first, oversized, third],
        context_window_tokens=100,
        document_context_fraction=0.5,
    )

    assert pruned.results == [first, third]
    assert pruned.token_budget == 50
    assert pruned.original_chunk_count == 3
    assert pruned.used_tokens <= pruned.token_budget


def test_context_pruner_counts_exact_tool_context_shape() -> None:
    """Token counting should match the citation-tagged text sent to the LLM."""
    pruner = ContextPruner()
    result = _result(7, "alpha beta")

    encoding = tiktoken.get_encoding("cl100k_base")

    assert pruner.count_result_tokens(result) == len(encoding.encode(format_search_result_for_context(result)))
