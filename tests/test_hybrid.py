"""Unit tests for hybrid search result merge."""

import pytest

from minirag.search.hybrid import merge_hybrid_results
from minirag.search.types import SearchResult


def test_merge_hybrid_results_combines_scores() -> None:
    """Hybrid merge should combine dense and sparse scores by alpha."""
    dense = [
        SearchResult(chunk_id=1, document_id=1, citation_key="k1", text="a", score=1.0),
        SearchResult(chunk_id=2, document_id=1, citation_key="k1", text="b", score=0.5),
    ]
    sparse = [
        SearchResult(chunk_id=1, document_id=1, citation_key="k1", text="a", score=0.2),
        SearchResult(chunk_id=3, document_id=2, citation_key="k2", text="c", score=1.0),
    ]

    merged = merge_hybrid_results(dense_results=dense, sparse_results=sparse, alpha=0.5, top_k=3)

    assert [item.text for item in merged] == ["a", "c", "b"]
    assert abs(merged[0].score - 0.6) < 1e-9
    assert abs(merged[1].score - 0.5) < 1e-9
    assert abs(merged[2].score - 0.25) < 1e-9
    assert merged[0].document_id == 1
    assert merged[0].citation_key == "k1"
    assert merged[1].document_id == 2
    assert merged[1].citation_key == "k2"


@pytest.mark.parametrize(
    ("alpha", "top_k"),
    [(-0.1, 5), (1.1, 5), (0.5, 0)],
)
def test_merge_hybrid_results_invalid_parameters_raise(alpha: float, top_k: int) -> None:
    """Invalid alpha or top_k should raise ValueError."""
    with pytest.raises(ValueError):
        merge_hybrid_results(dense_results=[], sparse_results=[], alpha=alpha, top_k=top_k)
