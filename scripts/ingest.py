"""Ingest all text files from a corpus input directory into mini-rag."""

import argparse
import json
import logging
from pathlib import Path
from typing import cast

from minirag.clients.indexing import IndexingClient
from minirag.config import Config

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure script logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def resolve_input_dir(data_dir: Path, corpus: str) -> Path:
    """Resolve and validate input text directory for a corpus."""
    input_dir = data_dir / "input" / corpus / "txt"
    if not input_dir.exists():
        raise FileNotFoundError(f"input directory not found: {input_dir}")

    if not input_dir.is_dir():
        raise ValueError(f"input path is not a directory: {input_dir}")

    return input_dir


_COMMON_FIELDS = {"title", "author", "year", "month", "day", "url", "urldate", "note"}

_SOURCE_DATA_FIELDS: dict[str, set[str]] = {
    "journal": {"journal_name", "journal", "volume", "issue", "number", "pages", "doi"},
    "arxiv": {"arxiv_id", "journal_name", "journal", "volume", "pages", "doi"},
    "book": {"publisher", "edition", "isbn", "chapter", "pages"},
    "youtube": {"platform", "channel", "timestamp", "duration", "howpublished"},
    "blog": {"blog_name", "platform"},
    "engineering_blog": {"blog_name", "platform"},
    "podcast": {"podcast_name", "episode", "timestamp", "duration"},
    "conference": {"conference_name", "location", "speaker"},
    "documentation": {"project", "version", "section"},
    "report": {"organization", "report_number"},
}

_FIELD_RENAMES: dict[str, str] = {
    "journal": "journal_name",
    "number": "issue",
}


_FIELD_TO_SOURCE_TYPE: dict[str, str] = {
    "doi": "journal",
    "journal": "journal",
    "isbn": "book",
    "podcast_name": "podcast",
    "conference_name": "conference",
    "blog_name": "blog",
    "report_number": "report",
}


def infer_source_type_from_url(url: str) -> str | None:
    """Infer source_type from URL patterns."""
    if "arxiv.org" in url:
        return "arxiv"
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    return None


def infer_source_type(data: dict[str, object], json_path: Path) -> str:
    """Infer source_type from flat citation fields. Raises ValueError if undetermined."""
    url = data.get("url")
    if isinstance(url, str):
        result = infer_source_type_from_url(url)
        if result is not None:
            return result

    for field, source_type in _FIELD_TO_SOURCE_TYPE.items():
        if field in data and data[field] is not None:
            return source_type

    raise ValueError(f"cannot infer source_type from citation fields in {json_path}")


def normalize_flat_citation(flat: dict[str, object], json_path: Path) -> dict[str, object]:
    """Convert a flat citation dict into the nested format.

    Flat format: {cite_key, title, author, year, doi, journal, ...}
    Nested format: {citation_key, source_type, common: {...}, source_data: {...}}

    If the input already has both source_type and common keys, it is returned
    as-is (assumed already nested). The cite_key field is renamed to
    citation_key if present.
    """
    flat = dict(flat)

    if "cite_key" in flat and "citation_key" not in flat:
        flat["citation_key"] = flat.pop("cite_key")

    if "source_type" in flat and "common" in flat:
        return flat

    source_type = str(flat["source_type"]) if "source_type" in flat else infer_source_type(flat, json_path)
    allowed_source_fields = _SOURCE_DATA_FIELDS.get(source_type, set())

    common: dict[str, object] = {}
    source_data: dict[str, object] = {}
    reserved = {"citation_key", "source_type", "common", "source_data"}
    unknown_fields: list[str] = []

    for key, value in flat.items():
        if key in reserved:
            continue
        if key in _COMMON_FIELDS:
            common[key] = value
        elif key in allowed_source_fields:
            target_key = _FIELD_RENAMES.get(key, key)
            source_data[target_key] = value
        else:
            common[key] = value
            unknown_fields.append(key)

    if unknown_fields:
        logger.warning("Unrecognized citation fields moved to common for %s: %s", json_path, unknown_fields)

    return {
        "citation_key": flat.get("citation_key", ""),
        "source_type": source_type,
        "common": common,
        "source_data": source_data,
    }


def load_citation(txt_path: Path) -> dict[str, object]:
    """Load citation JSON for a text file, or auto-generate one.

    Looks for a .json file with the same stem in the same directory.
    If found, validates citation_key and source_type are present.
    If not found, auto-generates a minimal citation.

    Flat-format JSON files (with cite_key instead of citation_key, and no
    source_type/common/source_data nesting) are automatically normalized
    into the expected nested format.
    """
    json_path = txt_path.with_suffix(".json")
    stem = txt_path.stem

    if json_path.exists():
        raw = json_path.read_text(encoding="utf-8")
        try:
            raw_parsed: object = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed citation JSON in {json_path}: {exc}") from exc

        if not isinstance(raw_parsed, dict):
            raise ValueError(f"citation JSON must be an object in {json_path}")

        parsed: dict[str, object] = cast(dict[str, object], raw_parsed)
        parsed = normalize_flat_citation(parsed, json_path)

        citation_key = parsed.get("citation_key")
        if not isinstance(citation_key, str) or citation_key.strip() == "":
            raise ValueError(f"citation JSON missing 'citation_key' in {json_path}")

        source_type = parsed.get("source_type")
        if not isinstance(source_type, str) or source_type.strip() == "":
            raise ValueError(f"citation JSON missing 'source_type' in {json_path}")

        logger.info("Loaded citation from %s (key=%s, type=%s)", json_path.name, citation_key, source_type)
        return parsed

    auto_citation: dict[str, object] = {
        "citation_key": stem,
        "source_type": "text_file",
        "common": {"title": txt_path.name},
        "source_data": {},
    }
    logger.debug("Auto-generated citation for %s (key=%s)", txt_path.name, stem)
    return auto_citation


def ingest_files(client: IndexingClient, corpus: str, input_dir: Path, data_dir: Path) -> None:
    """Destroy existing index and ingest all .txt files in sorted order.

    Fails immediately if any file fails to index.
    """
    text_files = sorted(
        [f for f in input_dir.rglob("*.txt") if not f.is_symlink() and not f.name.startswith("._")],
        key=lambda file_path: file_path.name,
    )

    logger.info("Found %d text file(s) in %s for corpus=%s", len(text_files), input_dir, corpus)

    if len(text_files) == 0:
        logger.warning("No .txt files found, nothing to ingest")
        return

    logger.info("Destroying existing index for corpus=%s before ingestion", corpus)
    client.destroy_index(corpus)

    total_chunks = 0
    indexed_count = 0
    skipped_count = 0
    num_files = len(text_files)
    for i, file_path in enumerate(text_files, start=1):
        relative_path = file_path.relative_to(data_dir)
        try:
            file_size = file_path.stat().st_size
            file_text = file_path.read_text(encoding="utf-8")
            if not file_text.strip():
                skipped_count += 1
                remaining = num_files - indexed_count - skipped_count
                logger.warning(
                    "[%d/%d] Skipping %s (empty content) — %d indexed, %d remaining", i, num_files, relative_path, indexed_count, remaining
                )
                continue
            citation = load_citation(file_path)
            _document_id, chunk_ids = client.index_document(corpus, file_text, citation=citation)
            indexed_count += 1
            total_chunks += len(chunk_ids)
            remaining = num_files - indexed_count - skipped_count
            logger.info(
                "[%d/%d] Indexed %s (%d bytes, %d chunks) — %d indexed, %d remaining",
                i,
                num_files,
                relative_path,
                file_size,
                len(chunk_ids),
                indexed_count,
                remaining,
            )
        except Exception:
            logger.exception("[%d/%d] Failed to index %s", i, num_files, relative_path)
            raise

    logger.info("Summary: %d file(s) indexed, %d skipped, %d chunk(s) total", indexed_count, skipped_count, total_chunks)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Ingest text files into a mini-rag corpus")
    parser.add_argument("--corpus", required=True, help="Name of the corpus to ingest into")
    parser.add_argument("--config", default=None, help="Path to config file (default: config.yaml in project root)")
    return parser.parse_args()


def main() -> None:
    """Load config and run ingestion."""
    configure_logging()
    args = parse_args()
    corpus: str = args.corpus

    project_root = Path(__file__).resolve().parent.parent
    config_path = Path(args.config).resolve() if args.config else project_root / "config.yaml"
    config = Config.from_yaml(config_path)
    data_dir = config.resolve_data_dir(project_root)
    input_dir = resolve_input_dir(data_dir, corpus)

    service_config = config.get_service_config()
    client = IndexingClient(host=service_config.host, port=service_config.port, http_client=None)

    ingest_files(client=client, corpus=corpus, input_dir=input_dir, data_dir=data_dir)
    logger.info("Ingestion completed for corpus=%s", corpus)


if __name__ == "__main__":
    main()
