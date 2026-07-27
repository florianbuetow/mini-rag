"""Regression tests for STOP-file ingest control."""

import sys
from pathlib import Path

import pytest

from minirag.ingestion import ledger
from scripts import ingest

CORPUS = "testcorpus"


class StopAfterFirstClient:
    def __init__(self, stop_path: Path | None = None) -> None:
        self.destroyed = False
        self.indexed: list[str] = []
        self._stop_path = stop_path

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
        self.indexed.append(text.strip())
        if self._stop_path is not None and len(self.indexed) == 1:
            self._stop_path.parent.mkdir(parents=True, exist_ok=True)
            self._stop_path.write_text("pause after first", encoding="utf-8")
        doc_id = len(self.indexed)
        return (doc_id, [doc_id])


def _make_input(data_dir: Path) -> Path:
    input_dir = data_dir / "input" / CORPUS / "txt"
    input_dir.mkdir(parents=True)
    return input_dir


def test_stop_requested_prefers_global_then_corpus_stop(tmp_path: Path) -> None:
    corpus_stop = tmp_path / "storage" / CORPUS / "STOP"
    corpus_stop.parent.mkdir(parents=True)
    corpus_stop.write_text("corpus", encoding="utf-8")

    assert ledger.stop_requested(tmp_path, CORPUS) == corpus_stop

    global_stop = tmp_path / "STOP"
    global_stop.write_text("global", encoding="utf-8")

    assert ledger.stop_requested(tmp_path, CORPUS) == global_stop


def test_stop_file_present_at_startup_exits_three_without_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_dir = _make_input(tmp_path)
    (input_dir / "a.txt").write_text("alpha", encoding="utf-8")
    (tmp_path / "STOP").write_text("maintenance", encoding="utf-8")

    class FakeConfig:
        def resolve_data_dir(self, project_root: Path) -> Path:
            del project_root
            return tmp_path

        def get_service_config(self) -> object:
            raise AssertionError("client should not be constructed when STOP exists")

    monkeypatch.setattr(ingest.Config, "from_yaml", lambda _path: FakeConfig())
    monkeypatch.setattr(sys, "argv", ["ingest.py", "--corpus", CORPUS, "--config", str(tmp_path / "config.yaml")])

    with pytest.raises(SystemExit) as exc_info:
        ingest.main()

    assert exc_info.value.code == ingest.STOP_EXIT_CODE
    assert ledger.load_indexed(tmp_path, CORPUS) == set()


def test_stop_created_mid_run_finishes_current_document_and_commits_ledger(tmp_path: Path) -> None:
    input_dir = _make_input(tmp_path)
    (input_dir / "a.txt").write_text("alpha", encoding="utf-8")
    (input_dir / "b.txt").write_text("beta", encoding="utf-8")
    stop_path = tmp_path / "storage" / CORPUS / "STOP"
    client = StopAfterFirstClient(stop_path=stop_path)

    ingest.ingest_files(client=client, corpus=CORPUS, input_dir=input_dir, data_dir=tmp_path, incremental=True)  # type: ignore[arg-type]

    assert client.indexed == ["alpha"]
    assert ledger.load_indexed(tmp_path, CORPUS) == {"a.txt"}
    assert not ledger.log_path(tmp_path, CORPUS).exists()
    assert stop_path.exists()


def test_per_corpus_stop_does_not_halt_different_corpus(tmp_path: Path) -> None:
    input_dir = _make_input(tmp_path)
    (input_dir / "a.txt").write_text("alpha", encoding="utf-8")
    other_stop = tmp_path / "storage" / "other" / "STOP"
    other_stop.parent.mkdir(parents=True)
    other_stop.write_text("other", encoding="utf-8")
    client = StopAfterFirstClient()

    ingest.ingest_files(client=client, corpus=CORPUS, input_dir=input_dir, data_dir=tmp_path, incremental=True)  # type: ignore[arg-type]

    assert client.indexed == ["alpha"]
    assert ledger.load_indexed(tmp_path, CORPUS) == {"a.txt"}
