"""Unit tests for scripts/pdf2txt.py."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

# Import the module under test — scripts/ is on pythonpath via pytest config
from scripts.pdf2txt import convert_corpus, convert_file


@pytest.fixture()
def mock_parser() -> MagicMock:
    parser = MagicMock()
    parser.parse.return_value = SimpleNamespace(text="Extracted PDF text content")
    return parser


class TestConvertFile:
    def test_writes_extracted_text(self, tmp_path: Path, mock_parser: MagicMock):
        pdf_path = tmp_path / "input.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")
        txt_path = tmp_path / "output.txt"

        convert_file(mock_parser, pdf_path, txt_path)

        mock_parser.parse.assert_called_once_with(pdf_path, ocr_enabled=True)
        assert txt_path.read_text(encoding="utf-8") == "Extracted PDF text content"

    def test_raises_on_parse_error(self, tmp_path: Path, mock_parser: MagicMock):
        pdf_path = tmp_path / "bad.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")
        txt_path = tmp_path / "output.txt"

        mock_parser.parse.side_effect = RuntimeError("parse failed")
        with pytest.raises(RuntimeError, match="parse failed"):
            convert_file(mock_parser, pdf_path, txt_path)

    def test_empty_text_still_written(self, tmp_path: Path, mock_parser: MagicMock):
        pdf_path = tmp_path / "empty.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")
        txt_path = tmp_path / "output.txt"

        mock_parser.parse.return_value = SimpleNamespace(text="")
        convert_file(mock_parser, pdf_path, txt_path)

        assert txt_path.read_text(encoding="utf-8") == ""


class TestConvertCorpus:
    def test_converts_all_pdfs(self, tmp_path: Path, mock_parser: MagicMock):
        pdf_dir = tmp_path / "pdf"
        pdf_dir.mkdir()
        txt_dir = tmp_path / "txt"

        (pdf_dir / "a.pdf").write_bytes(b"%PDF")
        (pdf_dir / "b.pdf").write_bytes(b"%PDF")

        count = convert_corpus(mock_parser, pdf_dir, txt_dir)

        assert count == 2
        assert (txt_dir / "a.txt").exists()
        assert (txt_dir / "b.txt").exists()

    def test_returns_zero_for_empty_dir(self, tmp_path: Path, mock_parser: MagicMock):
        pdf_dir = tmp_path / "pdf"
        pdf_dir.mkdir()
        txt_dir = tmp_path / "txt"

        count = convert_corpus(mock_parser, pdf_dir, txt_dir)

        assert count == 0
        assert not txt_dir.exists()

    def test_copies_json_citation_sidecar(self, tmp_path: Path, mock_parser: MagicMock):
        pdf_dir = tmp_path / "pdf"
        pdf_dir.mkdir()
        txt_dir = tmp_path / "txt"

        (pdf_dir / "doc.pdf").write_bytes(b"%PDF")
        citation = {"citation_key": "doc1", "source_type": "book"}
        (pdf_dir / "doc.json").write_text(json.dumps(citation), encoding="utf-8")

        convert_corpus(mock_parser, pdf_dir, txt_dir)

        json_dest = txt_dir / "doc.json"
        assert json_dest.exists()
        assert json.loads(json_dest.read_text(encoding="utf-8")) == citation

    def test_no_json_sidecar_is_fine(self, tmp_path: Path, mock_parser: MagicMock):
        pdf_dir = tmp_path / "pdf"
        pdf_dir.mkdir()
        txt_dir = tmp_path / "txt"

        (pdf_dir / "doc.pdf").write_bytes(b"%PDF")

        convert_corpus(mock_parser, pdf_dir, txt_dir)

        assert (txt_dir / "doc.txt").exists()
        assert not (txt_dir / "doc.json").exists()

    def test_skips_symlinks_and_dotfiles(self, tmp_path: Path, mock_parser: MagicMock):
        pdf_dir = tmp_path / "pdf"
        pdf_dir.mkdir()
        txt_dir = tmp_path / "txt"

        real = pdf_dir / "real.pdf"
        real.write_bytes(b"%PDF")
        (pdf_dir / "._hidden.pdf").write_bytes(b"%PDF")
        link = pdf_dir / "link.pdf"
        link.symlink_to(real)

        count = convert_corpus(mock_parser, pdf_dir, txt_dir)

        assert count == 1
        assert (txt_dir / "real.txt").exists()
        assert not (txt_dir / "._hidden.txt").exists()
        assert not (txt_dir / "link.txt").exists()

    def test_handles_nested_subdirectories(self, tmp_path: Path, mock_parser: MagicMock):
        pdf_dir = tmp_path / "pdf"
        sub = pdf_dir / "sub"
        sub.mkdir(parents=True)
        txt_dir = tmp_path / "txt"

        (sub / "nested.pdf").write_bytes(b"%PDF")

        count = convert_corpus(mock_parser, pdf_dir, txt_dir)

        assert count == 1
        assert (txt_dir / "sub" / "nested.txt").exists()
