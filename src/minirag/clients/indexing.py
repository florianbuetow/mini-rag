"""Indexing client for document/index management endpoints."""

from typing import cast

from minirag.clients.base import BaseClient


class IndexingClient(BaseClient):
    """Client for indexing and destroying index data."""

    def _as_object_list(self, value: object, context: str) -> list[object]:
        """Validate and cast a generic object into a list of objects."""
        if not isinstance(value, list):
            raise RuntimeError(f"{context} must be a list")
        return cast(list[object], value)

    def index_document(self, corpus: str, text: str) -> tuple[int, list[int]]:
        """Index one document and return document_id and chunk_ids."""
        if not corpus:
            raise ValueError("corpus must not be empty")

        if text.strip() == "":
            raise ValueError("text must not be empty")

        data = self._request(
            method="POST",
            path=f"/v1/corpus/{corpus}/index",
            payload={"document": text},
            require_healthy=True,
        )

        document_id_value = data.get("document_id")
        chunk_ids_value = data.get("chunk_ids")

        if not isinstance(document_id_value, int):
            raise RuntimeError("index response missing integer document_id")

        chunk_ids_list = self._as_object_list(chunk_ids_value, "index response chunk_ids")
        chunk_ids: list[int] = []
        for chunk_id_value in chunk_ids_list:
            if not isinstance(chunk_id_value, int):
                raise RuntimeError("index response chunk_ids must contain only integers")
            chunk_ids.append(chunk_id_value)

        return (document_id_value, chunk_ids)

    def destroy_index(self, corpus: str) -> None:
        """Destroy index state across all backends for a corpus."""
        if not corpus:
            raise ValueError("corpus must not be empty")

        self._request(
            method="DELETE",
            path=f"/v1/corpus/{corpus}/index",
            payload=None,
            require_healthy=True,
        )
