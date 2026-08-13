"""Text-content checks used by ingestion and indexing."""

import re

# A document (or chunk) with no word character carries no embeddable content.
# `\w` excludes whitespace, zero-width spaces (U+200B), and punctuation, so this
# catches blank video transcripts that `str.strip()` leaves looking non-empty.
_WORD_CHARACTER = re.compile(r"\w")


def has_ingestible_text(text: str) -> bool:
    """Return whether text contains content worth indexing."""
    return _WORD_CHARACTER.search(text) is not None
