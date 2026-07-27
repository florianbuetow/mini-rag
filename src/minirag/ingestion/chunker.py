"""Word-based text chunking utilities."""

import re
from typing import NamedTuple

_WORD_PATTERN = re.compile(r"\S+")


class ChunkSpan(NamedTuple):
    """Chunk text plus its [char_start, char_end) span in the original document text."""

    text: str
    char_start: int
    char_end: int


def chunk_text(text: str, chunk_size: int, overlap: float) -> list[ChunkSpan]:
    """Split text into overlapping word chunks with source spans.

    Args:
        text: Full document text to split.
        chunk_size: Number of words per chunk.
        overlap: Fractional overlap in [0.0, 1.0).

    Returns:
        Ordered list of chunk spans; span offsets reference ``text``.

    Raises:
        ValueError: If input text or chunk parameters are invalid.
    """
    if text.strip() == "":
        raise ValueError("text must not be empty or whitespace only")

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")

    if overlap < 0.0:
        raise ValueError("overlap must be greater than or equal to 0.0")

    if overlap >= 1.0:
        raise ValueError("overlap must be less than 1.0")

    step_float = float(chunk_size) * (1.0 - overlap)
    step = int(step_float)

    if step <= 0:
        raise ValueError("overlap produces a non-positive chunk step")

    word_matches = list(_WORD_PATTERN.finditer(text))
    if len(word_matches) == 0:
        raise ValueError("text must contain at least one word")

    chunks: list[ChunkSpan] = []
    start_index = 0
    while start_index < len(word_matches):
        end_index = start_index + chunk_size
        chunk_matches = word_matches[start_index:end_index]
        if len(chunk_matches) == 0:
            break
        chunks.append(
            ChunkSpan(
                text=" ".join(match.group(0) for match in chunk_matches),
                char_start=chunk_matches[0].start(),
                char_end=chunk_matches[-1].end(),
            )
        )
        start_index = start_index + step

    return chunks
