"""Hybrid result merge logic."""

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

    dense_by_id: dict[int, tuple[str, float]] = {}
    sparse_by_id: dict[int, tuple[str, float]] = {}

    for result in dense_results:
        dense_by_id[result.chunk_id] = (result.text, result.score)

    for result in sparse_results:
        sparse_by_id[result.chunk_id] = (result.text, result.score)

    all_chunk_ids: set[int] = set(dense_by_id.keys()) | set(sparse_by_id.keys())

    merged_results: list[SearchResult] = []
    for chunk_id in all_chunk_ids:
        dense_score = 0.0
        sparse_score = 0.0
        text = ""

        if chunk_id in dense_by_id:
            text, dense_score = dense_by_id[chunk_id]

        if chunk_id in sparse_by_id:
            text, sparse_score = sparse_by_id[chunk_id]

        final_score = alpha * dense_score + (1.0 - alpha) * sparse_score
        merged_results.append(SearchResult(chunk_id=chunk_id, text=text, score=final_score))

    ranked_results = sorted(merged_results, key=lambda result: result.score, reverse=True)
    return ranked_results[:top_k]
