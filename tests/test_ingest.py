"""Unit tests for the ingestion script."""

import json
from pathlib import Path

import pytest

from minirag.ingestion import ledger
from minirag.ingestion.citations import infer_source_type, load_citation, normalize_flat_citation, resolve_input_dir
from scripts.ingest import ingest_files

CORPUS = "testcorpus"


def _make_corpus_input(data_dir: Path) -> Path:
    """Create and return a realistic txt inbox under data_dir/input/{corpus}/txt."""
    input_dir = data_dir / "input" / CORPUS / "txt"
    input_dir.mkdir(parents=True)
    return input_dir


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

    result = load_citation(txt_path, tmp_path)
    assert result["citation_key"] == "doc_key"
    assert result["source_type"] == "journal"


def test_load_citation_auto_generates_when_no_json(tmp_path: Path) -> None:
    """load_citation should auto-generate citation using relative path as key."""
    txt_path = tmp_path / "my_document.txt"
    txt_path.write_text("content", encoding="utf-8")

    result = load_citation(txt_path, tmp_path)
    assert result["citation_key"] == "my_document"
    assert result["source_type"] == "text_file"
    common = result["common"]
    assert isinstance(common, dict)
    assert common["title"] == "my_document.txt"


def test_load_citation_auto_generates_with_subdirectory(tmp_path: Path) -> None:
    """load_citation should use relative path for files in subdirectories."""
    sub = tmp_path / "subdir"
    sub.mkdir()
    txt_path = sub / "my_document.txt"
    txt_path.write_text("content", encoding="utf-8")

    result = load_citation(txt_path, tmp_path)
    assert result["citation_key"] == "subdir/my_document"
    assert result["source_type"] == "text_file"


def test_load_citation_rejects_malformed_json(tmp_path: Path) -> None:
    """load_citation should fail fast on malformed JSON."""
    txt_path = tmp_path / "bad.txt"
    txt_path.write_text("content", encoding="utf-8")
    json_path = tmp_path / "bad.json"
    json_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(ValueError, match="malformed citation JSON"):
        load_citation(txt_path, tmp_path)


def test_load_citation_rejects_missing_citation_key(tmp_path: Path) -> None:
    """load_citation should fail when citation_key is missing."""
    txt_path = tmp_path / "nokey.txt"
    txt_path.write_text("content", encoding="utf-8")
    json_path = tmp_path / "nokey.json"
    json_path.write_text(json.dumps({"source_type": "journal"}), encoding="utf-8")

    with pytest.raises(ValueError, match="missing 'citation_key'"):
        load_citation(txt_path, tmp_path)


def test_load_citation_rejects_missing_source_type(tmp_path: Path) -> None:
    """load_citation should fail when source_type is missing."""
    txt_path = tmp_path / "notype.txt"
    txt_path.write_text("content", encoding="utf-8")
    json_path = tmp_path / "notype.json"
    json_path.write_text(json.dumps({"citation_key": "key1"}), encoding="utf-8")

    with pytest.raises(ValueError, match="cannot infer source_type"):
        load_citation(txt_path, tmp_path)


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


# --- normalize_flat_citation tests ---


def test_normalize_flat_citation_renames_cite_key() -> None:
    """cite_key should be renamed to citation_key."""
    flat: dict[str, object] = {"cite_key": "k1", "source_type": "blog", "title": "T"}
    result = normalize_flat_citation(flat, Path("test.json"))
    assert result["citation_key"] == "k1"
    assert "cite_key" not in result


def test_normalize_flat_citation_infers_journal_from_doi() -> None:
    """Flat citation with doi should infer source_type=journal."""
    flat: dict[str, object] = {"citation_key": "k1", "title": "T", "doi": "10.1234/test"}
    result = normalize_flat_citation(flat, Path("test.json"))
    assert result["source_type"] == "journal"
    source_data = result["source_data"]
    assert isinstance(source_data, dict)
    assert source_data["doi"] == "10.1234/test"


def test_normalize_flat_citation_infers_book_from_isbn() -> None:
    """Flat citation with isbn should infer source_type=book."""
    flat: dict[str, object] = {"citation_key": "k1", "title": "T", "isbn": "978-0-13-468599-1"}
    result = normalize_flat_citation(flat, Path("test.json"))
    assert result["source_type"] == "book"


def test_normalize_flat_citation_infers_arxiv_from_url() -> None:
    """Flat citation with arxiv URL should infer source_type=arxiv."""
    flat: dict[str, object] = {"citation_key": "k1", "title": "T", "url": "https://arxiv.org/abs/1234.5678"}
    result = normalize_flat_citation(flat, Path("test.json"))
    assert result["source_type"] == "arxiv"


def test_normalize_flat_citation_infers_youtube_from_url() -> None:
    """Flat citation with youtube URL should infer source_type=youtube."""
    flat: dict[str, object] = {"citation_key": "k1", "title": "T", "url": "https://youtube.com/watch?v=abc"}
    result = normalize_flat_citation(flat, Path("test.json"))
    assert result["source_type"] == "youtube"


def test_normalize_flat_citation_passes_through_nested() -> None:
    """Already-nested citation (with source_type and common) should pass through."""
    nested: dict[str, object] = {"citation_key": "k1", "source_type": "journal", "common": {"title": "T"}, "source_data": {}}
    result = normalize_flat_citation(nested, Path("test.json"))
    assert result == nested


def test_normalize_flat_citation_renames_fields() -> None:
    """journal should be renamed to journal_name, number to issue."""
    flat: dict[str, object] = {"citation_key": "k1", "source_type": "journal", "journal": "Nature", "number": "42"}
    result = normalize_flat_citation(flat, Path("test.json"))
    source_data = result["source_data"]
    assert isinstance(source_data, dict)
    assert source_data["journal_name"] == "Nature"
    assert source_data["issue"] == "42"


def test_normalize_flat_citation_unknown_fields_raise() -> None:
    """Unrecognized fields should raise ValueError."""
    flat: dict[str, object] = {"citation_key": "k1", "source_type": "journal", "custom_field": "value"}
    with pytest.raises(ValueError, match="unrecognized citation fields"):
        normalize_flat_citation(flat, Path("test.json"))


def test_normalize_flat_citation_preserves_provided_source_type() -> None:
    """When source_type is already provided in flat format, it should be preserved."""
    flat: dict[str, object] = {"citation_key": "k1", "source_type": "blog", "title": "My Post", "blog_name": "My Blog"}
    result = normalize_flat_citation(flat, Path("test.json"))
    assert result["source_type"] == "blog"
    source_data = result["source_data"]
    assert isinstance(source_data, dict)
    assert source_data["blog_name"] == "My Blog"


def test_normalize_flat_citation_book_publisher_in_source_data() -> None:
    """Book publisher should be in source_data, not common."""
    flat: dict[str, object] = {"citation_key": "k1", "source_type": "book", "title": "T", "publisher": "Pub"}
    result = normalize_flat_citation(flat, Path("test.json"))
    source_data = result["source_data"]
    assert isinstance(source_data, dict)
    assert source_data["publisher"] == "Pub"
    common = result["common"]
    assert isinstance(common, dict)
    assert "publisher" not in common


def test_normalize_flat_citation_raises_when_source_type_undetermined() -> None:
    """Should raise ValueError when source_type cannot be inferred."""
    flat: dict[str, object] = {"citation_key": "k1", "title": "T"}
    with pytest.raises(ValueError, match="cannot infer source_type"):
        normalize_flat_citation(flat, Path("test.json"))


# --- infer_source_type tests ---


def test_infer_source_type_from_doi() -> None:
    """doi field should infer journal."""
    assert infer_source_type({"doi": "10.1234/test"}, Path("t.json")) == "journal"


def test_infer_source_type_from_podcast_name() -> None:
    """podcast_name field should infer podcast."""
    assert infer_source_type({"podcast_name": "My Pod"}, Path("t.json")) == "podcast"


def test_infer_source_type_from_arxiv_url() -> None:
    """arxiv.org URL should infer arxiv."""
    assert infer_source_type({"url": "https://arxiv.org/abs/2301.00001"}, Path("t.json")) == "arxiv"


def test_infer_source_type_raises_when_undetermined() -> None:
    """Should raise ValueError when no inference rule matches."""
    with pytest.raises(ValueError, match="cannot infer source_type"):
        infer_source_type({"title": "T"}, Path("t.json"))


# --- incremental update (ledger) tests ---


def test_full_ingest_writes_ledger(tmp_path: Path) -> None:
    """Full ingest records every indexed file in the committed ledger."""
    input_dir = _make_corpus_input(tmp_path)
    (input_dir / "a.txt").write_text("alpha", encoding="utf-8")
    (input_dir / "b.txt").write_text("beta", encoding="utf-8")

    client = FakeIndexingClient()
    ingest_files(client=client, corpus=CORPUS, input_dir=input_dir, data_dir=tmp_path)  # type: ignore[arg-type]

    assert client.destroyed
    assert ledger.load_indexed(tmp_path, CORPUS) == {"a.txt", "b.txt"}


def test_full_ingest_clears_stale_ledger_before_indexing(tmp_path: Path) -> None:
    """Full ingest wipes a pre-existing ledger so it reflects only this run."""
    input_dir = _make_corpus_input(tmp_path)
    (input_dir / "a.txt").write_text("alpha", encoding="utf-8")
    # Stale entry from a previous corpus state that no longer has a file.
    ledger.record_indexed(tmp_path, CORPUS, "gone.txt")
    ledger.commit(tmp_path, CORPUS)

    client = FakeIndexingClient()
    ingest_files(client=client, corpus=CORPUS, input_dir=input_dir, data_dir=tmp_path)  # type: ignore[arg-type]

    assert ledger.load_indexed(tmp_path, CORPUS) == {"a.txt"}


def test_update_skips_already_indexed_and_does_not_destroy(tmp_path: Path) -> None:
    """Incremental update indexes only new files and never destroys the index."""
    input_dir = _make_corpus_input(tmp_path)
    (input_dir / "a.txt").write_text("alpha", encoding="utf-8")
    (input_dir / "b.txt").write_text("beta", encoding="utf-8")
    # a.txt was indexed in a prior run.
    ledger.record_indexed(tmp_path, CORPUS, "a.txt")
    ledger.commit(tmp_path, CORPUS)

    client = FakeIndexingClient()
    ingest_files(client=client, corpus=CORPUS, input_dir=input_dir, data_dir=tmp_path, incremental=True)  # type: ignore[arg-type]

    assert not client.destroyed
    assert len(client.indexed) == 1
    assert client.indexed[0] == "beta"
    assert ledger.load_indexed(tmp_path, CORPUS) == {"a.txt", "b.txt"}


def test_update_with_empty_ledger_indexes_all(tmp_path: Path) -> None:
    """With no prior ledger, update indexes everything and records it, without destroying."""
    input_dir = _make_corpus_input(tmp_path)
    (input_dir / "a.txt").write_text("alpha", encoding="utf-8")
    (input_dir / "b.txt").write_text("beta", encoding="utf-8")

    client = FakeIndexingClient()
    ingest_files(client=client, corpus=CORPUS, input_dir=input_dir, data_dir=tmp_path, incremental=True)  # type: ignore[arg-type]

    assert not client.destroyed
    assert len(client.indexed) == 2
    assert ledger.load_indexed(tmp_path, CORPUS) == {"a.txt", "b.txt"}


def test_update_skips_subdirectory_paths(tmp_path: Path) -> None:
    """Ledger identity is the path relative to the inbox, including subdirectories."""
    input_dir = _make_corpus_input(tmp_path)
    sub = input_dir / "topic"
    sub.mkdir()
    (sub / "a.txt").write_text("alpha", encoding="utf-8")
    (input_dir / "b.txt").write_text("beta", encoding="utf-8")
    ledger.record_indexed(tmp_path, CORPUS, "topic/a.txt")
    ledger.commit(tmp_path, CORPUS)

    client = FakeIndexingClient()
    ingest_files(client=client, corpus=CORPUS, input_dir=input_dir, data_dir=tmp_path, incremental=True)  # type: ignore[arg-type]

    assert client.indexed == ["beta"]
    assert ledger.load_indexed(tmp_path, CORPUS) == {"topic/a.txt", "b.txt"}


def test_update_after_crash_skips_files_recorded_before_failure(tmp_path: Path) -> None:
    """A failed update leaves its log behind so a re-run skips the files it already indexed."""
    input_dir = _make_corpus_input(tmp_path)
    (input_dir / "a.txt").write_text("good", encoding="utf-8")
    (input_dir / "b.txt").write_text("bad", encoding="utf-8")
    (input_dir / "c.txt").write_text("also good", encoding="utf-8")

    # First run aborts on b.txt; a.txt has already been indexed and recorded.
    failing_client = FakeIndexingClient(fail_on={"bad"})
    with pytest.raises(RuntimeError, match="simulated failure for: bad"):
        ingest_files(client=failing_client, corpus=CORPUS, input_dir=input_dir, data_dir=tmp_path, incremental=True)  # type: ignore[arg-type]
    assert failing_client.indexed == ["good"]
    assert "a.txt" in ledger.load_indexed(tmp_path, CORPUS)

    # Second run must skip a.txt (recorded in the log) rather than re-index it.
    client = FakeIndexingClient()
    ingest_files(client=client, corpus=CORPUS, input_dir=input_dir, data_dir=tmp_path, incremental=True)  # type: ignore[arg-type]

    assert "good" not in client.indexed  # a.txt was skipped
    assert sorted(client.indexed) == ["also good", "bad"]
    assert ledger.load_indexed(tmp_path, CORPUS) == {"a.txt", "b.txt", "c.txt"}
