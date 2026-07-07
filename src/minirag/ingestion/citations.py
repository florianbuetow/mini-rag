"""Citation loading and normalization for the ingestion pipeline.

Resolves the citation metadata (and citation key) for each input text file,
either from a sibling ``.json`` sidecar or by auto-generating a minimal record.
Shared by the ingestion script and the ledger backfill so both derive identical
citation keys for the same file.
"""

import json
import logging
from pathlib import Path
from typing import cast

logger = logging.getLogger(__name__)


def resolve_input_dir(data_dir: Path, corpus: str) -> Path:
    """Resolve and validate input text directory for a corpus."""
    input_dir = data_dir / "input" / corpus / "txt"
    if not input_dir.exists():
        raise FileNotFoundError(f"input directory not found: {input_dir}")

    if not input_dir.is_dir():
        raise ValueError(f"input path is not a directory: {input_dir}")

    return input_dir


_COMMON_FIELDS = {"title", "author", "year", "month", "day", "url", "urldate", "note", "publication_date"}

_SOURCE_DATA_FIELDS: dict[str, set[str]] = {
    "journal": {"journal_name", "journal", "volume", "issue", "number", "pages", "doi"},
    "arxiv": {"arxiv_id", "journal_name", "journal", "volume", "issue", "number", "pages", "doi", "publisher"},
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


def _split_citation_fields(
    flat: dict[str, object], allowed_source_fields: set[str]
) -> tuple[dict[str, object], dict[str, object], list[str]]:
    """Route flat citation fields into common, source_data, and unknown buckets."""
    reserved = {"citation_key", "source_type", "common", "source_data"}
    common: dict[str, object] = {}
    source_data: dict[str, object] = {}
    unknown_fields: list[str] = []

    for key, value in flat.items():
        if key in reserved:
            continue
        if key in _COMMON_FIELDS:
            common[key] = value
        elif key in allowed_source_fields:
            if key in _FIELD_RENAMES:
                source_data[_FIELD_RENAMES[key]] = value
            else:
                source_data[key] = value
        else:
            unknown_fields.append(key)

    return (common, source_data, unknown_fields)


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
    allowed_source_fields: set[str] = set()
    if source_type in _SOURCE_DATA_FIELDS:
        allowed_source_fields = _SOURCE_DATA_FIELDS[source_type]

    common, source_data, unknown_fields = _split_citation_fields(flat, allowed_source_fields)

    if unknown_fields:
        unknown_list = ", ".join(sorted(unknown_fields))
        raise ValueError(f"unrecognized citation fields in {json_path}: {unknown_list}")

    citation_key_value: object = ""
    if "citation_key" in flat:
        citation_key_value = flat["citation_key"]

    return {
        "citation_key": citation_key_value,
        "source_type": source_type,
        "common": common,
        "source_data": source_data,
    }


def load_citation(txt_path: Path, input_dir: Path) -> dict[str, object]:
    """Load citation JSON for a text file, or auto-generate one.

    Looks for a .json file with the same stem in the same directory.
    If found, validates citation_key and source_type are present.
    If not found, auto-generates a minimal citation using the relative
    path from ``input_dir`` (without extension) as the citation key.
    This ensures uniqueness even when multiple files share the same stem
    across different subdirectories.

    Flat-format JSON files (with cite_key instead of citation_key, and no
    source_type/common/source_data nesting) are automatically normalized
    into the expected nested format.

    Args:
        txt_path: Absolute path to the .txt file.
        input_dir: The corpus input directory (parent of all txt files).
    """
    json_path = txt_path.with_suffix(".json")

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

    relative = txt_path.relative_to(input_dir).with_suffix("")
    citation_key = str(relative)
    auto_citation: dict[str, object] = {
        "citation_key": citation_key,
        "source_type": "text_file",
        "common": {"title": txt_path.name},
        "source_data": {},
    }
    logger.debug("Auto-generated citation for %s (key=%s)", txt_path.name, citation_key)
    return auto_citation
