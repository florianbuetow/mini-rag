"""Query client for dense/sparse/hybrid search endpoints."""

from urllib.parse import quote

from minirag.clients.base import BaseClient
from minirag.corpus import validate_corpus_name
from minirag.search.types import SearchResult


def _parse_search_result(result_map: dict[str, object]) -> SearchResult:
    """Parse one query result payload into a SearchResult."""
    chunk_id_value = result_map.get("chunk_id")
    document_id_value = result_map.get("document_id")
    citation_key_value = result_map.get("citation_key")
    text_value = result_map.get("text")
    score_value = result_map.get("score")
    source_path_value = result_map.get("source_path")

    if not isinstance(chunk_id_value, int):
        raise RuntimeError("query result missing integer chunk_id")

    if not isinstance(document_id_value, int):
        raise RuntimeError("query result missing integer document_id")

    if not isinstance(citation_key_value, str):
        raise RuntimeError("query result missing string citation_key")

    if not isinstance(text_value, str):
        raise RuntimeError("query result missing string text")

    if not isinstance(score_value, (int, float)):
        raise RuntimeError("query result missing numeric score")

    if not isinstance(source_path_value, str):
        raise RuntimeError("query result missing string source_path")

    provenance_ints: dict[str, int] = {}
    for field_name in ("chunk_index", "char_start", "char_end", "line_from", "line_to"):
        field_value = result_map.get(field_name)
        if not isinstance(field_value, int):
            raise RuntimeError(f"query result missing integer {field_name}")
        provenance_ints[field_name] = field_value

    return SearchResult(
        chunk_id=chunk_id_value,
        document_id=document_id_value,
        citation_key=citation_key_value,
        text=text_value,
        score=float(score_value),
        source_path=source_path_value,
        chunk_index=provenance_ints["chunk_index"],
        char_start=provenance_ints["char_start"],
        char_end=provenance_ints["char_end"],
        line_from=provenance_ints["line_from"],
        line_to=provenance_ints["line_to"],
    )


class QueryClient(BaseClient):
    """Client for querying dense, sparse, and hybrid endpoints."""

    def _search(self, corpus: str, path_suffix: str, query: str, top_k: int) -> list[SearchResult]:
        """Run one query endpoint and parse SearchResult list."""
        validate_corpus_name(corpus)

        if query.strip() == "":
            raise ValueError("query must not be empty")

        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        data = self._request(
            method="POST",
            path=f"/v1/corpus/{quote(corpus, safe='')}/query/{path_suffix}",
            payload={"query": query, "top_k": top_k},
            require_healthy=True,
        )

        results_value = data.get("results")
        results_list = self._as_object_list(results_value, "query response results")
        parsed_results: list[SearchResult] = []
        for raw_result in results_list:
            result_map = self._as_object_map(raw_result, "query result item")
            parsed_results.append(_parse_search_result(result_map))

        return parsed_results

    def search_dense(self, corpus: str, query: str, top_k: int) -> list[SearchResult]:
        """Run dense search."""
        return self._search(corpus=corpus, path_suffix="dense", query=query, top_k=top_k)

    def search_sparse(self, corpus: str, query: str, top_k: int) -> list[SearchResult]:
        """Run sparse search."""
        return self._search(corpus=corpus, path_suffix="sparse", query=query, top_k=top_k)

    def search_hybrid(self, corpus: str, query: str, top_k: int) -> list[SearchResult]:
        """Run hybrid search."""
        return self._search(corpus=corpus, path_suffix="hybrid", query=query, top_k=top_k)

    def get_citation(self, corpus: str, citation_key: str) -> dict[str, object]:
        """Fetch citation metadata for a given citation_key."""
        validate_corpus_name(corpus)

        if citation_key.strip() == "":
            raise ValueError("citation_key must not be empty")

        return self._request(
            method="GET",
            path=f"/v1/corpus/{quote(corpus, safe='')}/citation/{quote(citation_key, safe='')}",
            payload=None,
            require_healthy=True,
        )
