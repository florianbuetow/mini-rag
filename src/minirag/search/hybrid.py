"""Hybrid result merge logic."""

from dataclasses import replace

from minirag.search.types import SearchResult


def merge_hybrid_results(
    dense_results: list[SearchResult],
    sparse_results: list[SearchResult],
    alpha: float,
    top_k: int,
) -> list[SearchResult]:
    """Merge dense and sparse search results using weighted score fusion.

    Args:
        dense_results: Dense search results with normalized scores.
        sparse_results: Sparse search results with normalized scores.
        alpha: Dense weight in [0.0, 1.0].
        top_k: Max number of results to return.

    Returns:
        Re-ranked top-k merged results.

    Raises:
        ValueError: If alpha or top_k is invalid.
    """
    if alpha < 0.0:
        raise ValueError("alpha must be greater than or equal to 0.0")

    if alpha > 1.0:
        raise ValueError("alpha must be less than or equal to 1.0")

    if top_k <= 0:
        raise ValueError("top_k must be greater than 0")

    dense_by_id: dict[int, SearchResult] = {result.chunk_id: result for result in dense_results}
    sparse_by_id: dict[int, SearchResult] = {result.chunk_id: result for result in sparse_results}

    all_chunk_ids: set[int] = set(dense_by_id.keys()) | set(sparse_by_id.keys())

    merged_results: list[SearchResult] = []
    for chunk_id in all_chunk_ids:
        dense_result = dense_by_id.get(chunk_id)
        sparse_result = sparse_by_id.get(chunk_id)
        base_result = dense_result if dense_result is not None else sparse_result
        if base_result is None:
            raise RuntimeError(f"chunk_id={chunk_id} in merged set but absent from both result sources")

        dense_score = dense_result.score if dense_result is not None else 0.0
        sparse_score = sparse_result.score if sparse_result is not None else 0.0
        final_score = alpha * dense_score + (1.0 - alpha) * sparse_score
        merged_results.append(replace(base_result, score=final_score))

    ranked_results = sorted(merged_results, key=lambda result: result.score, reverse=True)
    return ranked_results[:top_k]
