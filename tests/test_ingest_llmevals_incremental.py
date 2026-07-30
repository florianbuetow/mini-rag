"""Incremental ingestion regression coverage using the llmevals corpus."""

import shutil
from pathlib import Path

from minirag.ingestion import ledger
from scripts.ingest import ingest_files

CORPUS = "llmevals"
LLMEVALS_SEED_DIR = Path(__file__).resolve().parents[1] / "tests_e2e" / "seed_data" / CORPUS / "txt"


class RecordingIndexingClient:
    """Record index mutations without requiring a running mini-rag service."""

    def __init__(self) -> None:
        self.destroyed = False
        self.source_paths: list[str] = []

    def destroy_index(self, corpus: str) -> None:
        assert corpus == CORPUS
        self.destroyed = True

    def index_document(
        self,
        corpus: str,
        text: str,
        citation: dict[str, object] | None = None,
        source_path: str = "",
    ) -> tuple[int, list[int]]:
        assert corpus == CORPUS
        assert text.strip()
        assert citation is not None
        self.source_paths.append(source_path)
        document_id = len(self.source_paths)
        return (document_id, [document_id])


def test_llmevals_update_indexes_only_files_that_arrive_after_initial_ingest(tmp_path: Path) -> None:
    """A completed llmevals ingest is remembered across later update runs."""
    input_dir = tmp_path / "input" / CORPUS / "txt"
    shutil.copytree(LLMEVALS_SEED_DIR, input_dir)
    original_paths = {path.name for path in input_dir.glob("*.txt")}

    initial_client = RecordingIndexingClient()
    ingest_files(client=initial_client, corpus=CORPUS, input_dir=input_dir, data_dir=tmp_path)  # type: ignore[arg-type]

    assert initial_client.destroyed
    assert set(initial_client.source_paths) == original_paths
    assert ledger.load_indexed(tmp_path, CORPUS) == original_paths

    new_path = input_dir / "le_win_rate.txt"
    new_path.write_text(
        "Win rate measures how often one system is preferred over another in pairwise evaluation.",
        encoding="utf-8",
    )

    update_client = RecordingIndexingClient()
    ingest_files(client=update_client, corpus=CORPUS, input_dir=input_dir, data_dir=tmp_path, incremental=True)  # type: ignore[arg-type]

    assert not update_client.destroyed
    assert update_client.source_paths == [new_path.name]
    assert ledger.load_indexed(tmp_path, CORPUS) == original_paths | {new_path.name}

    no_op_client = RecordingIndexingClient()
    ingest_files(client=no_op_client, corpus=CORPUS, input_dir=input_dir, data_dir=tmp_path, incremental=True)  # type: ignore[arg-type]

    assert not no_op_client.destroyed
    assert no_op_client.source_paths == []
