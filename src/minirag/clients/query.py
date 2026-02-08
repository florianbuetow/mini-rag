"""Query client for dense/sparse/hybrid search endpoints."""

from typing import cast

from minirag.clients.base import BaseClient
from minirag.search.types import SearchResult


class QueryClient(BaseClient):
    """Client for querying dense, sparse, and hybrid endpoints."""

    def _as_object_list(self, value: object, context: str) -> list[object]:
        """Validate and cast a generic object into a list of objects."""
        if not isinstance(value, list):
            raise RuntimeError(f"{context} must be a list")
        return cast(list[object], value)

    def _as_object_map(self, value: object, context: str) -> dict[str, object]:
        """Validate and cast a generic object into a string-key object map."""
        if not isinstance(value, dict):
            raise RuntimeError(f"{context} must be an object")

        typed_value = cast(dict[object, object], value)
        result: dict[str, object] = {}
        for raw_key, raw_value in typed_value.items():
            if not isinstance(raw_key, str):
                raise RuntimeError(f"{context} contains non-string key")
            result[raw_key] = raw_value
        return result

    def _search(self, path: str, query: str, top_k: int) -> list[SearchResult]:
        """Run one query endpoint and parse SearchResult list."""
        if query.strip() == "":
            raise ValueError("query must not be empty")

        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        data = self._request(
            method="GET",
            path=path,
            payload={"query": query, "top_k": top_k},
            require_healthy=True,
        )

        results_value = data.get("results")
        results_list = self._as_object_list(results_value, "query response results")
        parsed_results: list[SearchResult] = []
        for raw_result in results_list:
            result_map = self._as_object_map(raw_result, "query result item")

            text_value = result_map.get("text")
            score_value = result_map.get("score")

            if not isinstance(text_value, str):
                raise RuntimeError("query result missing string text")

            if not isinstance(score_value, (int, float)):
                raise RuntimeError("query result missing numeric score")

            parsed_results.append(SearchResult(text=text_value, score=float(score_value)))

        return parsed_results

    def search_dense(self, query: str, top_k: int) -> list[SearchResult]:
        """Run dense search."""
        return self._search(path="/v1/query/dense", query=query, top_k=top_k)

    def search_sparse(self, query: str, top_k: int) -> list[SearchResult]:
        """Run sparse search."""
        return self._search(path="/v1/query/sparse", query=query, top_k=top_k)

    def search_hybrid(self, query: str, top_k: int) -> list[SearchResult]:
        """Run hybrid search."""
        return self._search(path="/v1/query/hybrid", query=query, top_k=top_k)
