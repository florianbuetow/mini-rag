"""Regression tests for ingest duplicate-citation failures."""

from pathlib import Path

import pytest

from minirag.ingestion import ledger
from scripts.ingest import ingest_files

CORPUS = "testcorpus"
CONFLICT_ERROR = "UNIQUE constraint failed: document_citations.citation_key"


class ConflictClient:
    def __init__(self) -> None:
        self.destroyed = False
        self.indexed: list[str] = []

    def destroy_index(self, corpus: str) -> None:
        del corpus
        self.destroyed = True

    def index_document(
        self,
        corpus: str,
        text: str,
        citation: dict[str, object] | None = None,
        source_path: str = "",
    ) -> tuple[int, list[int]]:
        del corpus, citation, source_path
        if text.strip() == "orphan":
            raise RuntimeError(CONFLICT_ERROR)
        self.indexed.append(text.strip())
        doc_id = len(self.indexed)
        return (doc_id, [doc_id])


def test_duplicate_citation_runtime_error_aborts_without_reconciling_ledger(tmp_path: Path) -> None:
    input_dir = tmp_path / "input" / CORPUS / "txt"
    input_dir.mkdir(parents=True)
    (input_dir / "a.txt").write_text("alpha", encoding="utf-8")
    (input_dir / "b.txt").write_text("orphan", encoding="utf-8")
    (input_dir / "c.txt").write_text("gamma", encoding="utf-8")

    client = ConflictClient()

    with pytest.raises(RuntimeError, match="UNIQUE constraint failed"):
        ingest_files(client=client, corpus=CORPUS, input_dir=input_dir, data_dir=tmp_path, incremental=True)  # type: ignore[arg-type]

    assert client.indexed == ["alpha"]
    assert ledger.load_indexed(tmp_path, CORPUS) == {"a.txt"}
