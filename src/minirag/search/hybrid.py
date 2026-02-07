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

    dense_scores_by_text: dict[str, float] = {}
    sparse_scores_by_text: dict[str, float] = {}

    for result in dense_results:
        dense_scores_by_text[result.text] = result.score

    for result in sparse_results:
        sparse_scores_by_text[result.text] = result.score

    all_texts: set[str] = set(dense_scores_by_text.keys()) | set(sparse_scores_by_text.keys())

    merged_results: list[SearchResult] = []
    for text in all_texts:
        dense_score = 0.0
        sparse_score = 0.0

        if text in dense_scores_by_text:
            dense_score = dense_scores_by_text[text]

        if text in sparse_scores_by_text:
            sparse_score = sparse_scores_by_text[text]

        final_score = alpha * dense_score + (1.0 - alpha) * sparse_score
        merged_results.append(SearchResult(text=text, score=final_score))

    ranked_results = sorted(merged_results, key=lambda result: result.score, reverse=True)
    return ranked_results[:top_k]
