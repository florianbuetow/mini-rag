"""Unit tests for the ingestion script."""

import json
from pathlib import Path

import pytest

from scripts.ingest import ingest_files, load_citation, resolve_input_dir

CORPUS = "testcorpus"


class FakeIndexingClient:
    """Fake IndexingClient tracking calls and optionally raising."""

    def __init__(self, fail_on: set[str] | None = None) -> None:
        self.destroyed = False
        self.indexed: list[str] = []
        self.citations: list[dict[str, object] | None] = []
        self._fail_on = fail_on or set()

    def destroy_index(self, corpus: str) -> None:
        del corpus
        self.destroyed = True

    def index_document(self, corpus: str, text: str, citation: dict[str, object] | None = None) -> tuple[int, list[int]]:
        del corpus
        if text.strip() in self._fail_on:
            raise RuntimeError(f"simulated failure for: {text.strip()}")
        self.indexed.append(text)
        self.citations.append(citation)
        doc_id = len(self.indexed)
        return (doc_id, [doc_id * 10 + 1])


def test_resolve_input_dir_valid(tmp_path: Path) -> None:
    """resolve_input_dir should return path when directory exists."""
    input_dir = tmp_path / "input" / CORPUS / "txt"
    input_dir.mkdir(parents=True)

    result = resolve_input_dir(tmp_path, CORPUS)
    assert result == input_dir


def test_resolve_input_dir_missing_raises(tmp_path: Path) -> None:
    """resolve_input_dir should raise when directory is missing."""
    with pytest.raises(FileNotFoundError):
        resolve_input_dir(tmp_path, CORPUS)


def test_resolve_input_dir_not_a_directory(tmp_path: Path) -> None:
    """resolve_input_dir should raise when path is not a directory."""
    input_path = tmp_path / "input" / CORPUS / "txt"
    input_path.parent.mkdir(parents=True)
    input_path.write_text("not a dir", encoding="utf-8")

    with pytest.raises(ValueError):
        resolve_input_dir(tmp_path, CORPUS)


def test_ingest_empty_directory(tmp_path: Path) -> None:
    """Empty directory should log warning and not destroy index."""
    client = FakeIndexingClient()
    ingest_files(client=client, corpus=CORPUS, input_dir=tmp_path, data_dir=tmp_path)  # type: ignore[arg-type]
    assert not client.destroyed
    assert client.indexed == []


def test_ingest_successful(tmp_path: Path) -> None:
    """All files should be ingested with correct counts."""
    (tmp_path / "a.txt").write_text("alpha content", encoding="utf-8")
    (tmp_path / "b.txt").write_text("beta content", encoding="utf-8")

    client = FakeIndexingClient()
    ingest_files(client=client, corpus=CORPUS, input_dir=tmp_path, data_dir=tmp_path)  # type: ignore[arg-type]

    assert client.destroyed
    assert len(client.indexed) == 2
    assert len(client.citations) == 2
    # Auto-generated citations should have stem as citation_key
    for citation in client.citations:
        assert citation is not None
        assert "citation_key" in citation
        assert citation["source_type"] == "text_file"


def test_ingest_fails_fast_on_first_error(tmp_path: Path) -> None:
    """Failure should propagate immediately without processing remaining files."""
    (tmp_path / "a.txt").write_text("good", encoding="utf-8")
    (tmp_path / "b.txt").write_text("bad", encoding="utf-8")
    (tmp_path / "c.txt").write_text("also good", encoding="utf-8")

    client = FakeIndexingClient(fail_on={"bad"})

    with pytest.raises(RuntimeError, match="simulated failure for: bad"):
        ingest_files(client=client, corpus=CORPUS, input_dir=tmp_path, data_dir=tmp_path)  # type: ignore[arg-type]

    assert client.destroyed
    assert len(client.indexed) == 1  # only a.txt; c.txt was never reached


def test_ingest_skips_empty_files(tmp_path: Path) -> None:
    """Files with empty or whitespace-only content should be skipped."""
    (tmp_path / "a.txt").write_text("real content", encoding="utf-8")
    (tmp_path / "b.txt").write_text("", encoding="utf-8")
    (tmp_path / "c.txt").write_text("   \n\t  \n", encoding="utf-8")
    (tmp_path / "d.txt").write_text("also real", encoding="utf-8")

    client = FakeIndexingClient()
    ingest_files(client=client, corpus=CORPUS, input_dir=tmp_path, data_dir=tmp_path)  # type: ignore[arg-type]

    assert client.destroyed
    assert len(client.indexed) == 2


def test_load_citation_from_json_file(tmp_path: Path) -> None:
    """load_citation should load citation from matching .json file."""
    txt_path = tmp_path / "doc.txt"
    txt_path.write_text("content", encoding="utf-8")
    json_path = tmp_path / "doc.json"
    citation_data: dict[str, object] = {"citation_key": "doc_key", "source_type": "journal", "common": {}, "source_data": {}}
    json_path.write_text(json.dumps(citation_data), encoding="utf-8")

    result = load_citation(txt_path)
    assert result["citation_key"] == "doc_key"
    assert result["source_type"] == "journal"


def test_load_citation_auto_generates_when_no_json(tmp_path: Path) -> None:
    """load_citation should auto-generate citation when no .json file exists."""
    txt_path = tmp_path / "my_document.txt"
    txt_path.write_text("content", encoding="utf-8")

    result = load_citation(txt_path)
    assert result["citation_key"] == "my_document"
    assert result["source_type"] == "text_file"
    common = result["common"]
    assert isinstance(common, dict)
    assert common["title"] == "my_document.txt"


def test_load_citation_rejects_malformed_json(tmp_path: Path) -> None:
    """load_citation should fail fast on malformed JSON."""
    txt_path = tmp_path / "bad.txt"
    txt_path.write_text("content", encoding="utf-8")
    json_path = tmp_path / "bad.json"
    json_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(ValueError, match="malformed citation JSON"):
        load_citation(txt_path)


def test_load_citation_rejects_missing_citation_key(tmp_path: Path) -> None:
    """load_citation should fail when citation_key is missing."""
    txt_path = tmp_path / "nokey.txt"
    txt_path.write_text("content", encoding="utf-8")
    json_path = tmp_path / "nokey.json"
    json_path.write_text(json.dumps({"source_type": "journal"}), encoding="utf-8")

    with pytest.raises(ValueError, match="missing 'citation_key'"):
        load_citation(txt_path)


def test_load_citation_rejects_missing_source_type(tmp_path: Path) -> None:
    """load_citation should fail when source_type is missing."""
    txt_path = tmp_path / "notype.txt"
    txt_path.write_text("content", encoding="utf-8")
    json_path = tmp_path / "notype.json"
    json_path.write_text(json.dumps({"citation_key": "key1"}), encoding="utf-8")

    with pytest.raises(ValueError, match="cannot infer source_type"):
        load_citation(txt_path)


def test_ingest_with_json_citation(tmp_path: Path) -> None:
    """Ingestion should pass citation from .json file to client."""
    (tmp_path / "a.txt").write_text("content", encoding="utf-8")
    citation_data: dict[str, object] = {"citation_key": "custom_key", "source_type": "blog", "common": {}, "source_data": {}}
    (tmp_path / "a.json").write_text(json.dumps(citation_data), encoding="utf-8")

    client = FakeIndexingClient()
    ingest_files(client=client, corpus=CORPUS, input_dir=tmp_path, data_dir=tmp_path)  # type: ignore[arg-type]

    assert len(client.citations) == 1
    assert client.citations[0] is not None
    assert client.citations[0]["citation_key"] == "custom_key"
