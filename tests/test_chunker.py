"""Unit tests for word chunking."""

import pytest

from minirag.ingestion.chunker import chunk_text


def test_chunk_text_splits_with_overlap() -> None:
    """Chunker should split words with configured overlap."""
    text = "one two three four five six seven eight nine ten"
    chunks = chunk_text(text=text, chunk_size=4, overlap=0.5)

    assert chunks == [
        "one two three four",
        "three four five six",
        "five six seven eight",
        "seven eight nine ten",
        "nine ten",
    ]


@pytest.mark.parametrize(
    ("text", "chunk_size", "overlap"),
    [
        ("", 3, 0.1),
        ("   ", 3, 0.1),
        ("one two", 0, 0.1),
        ("one two", -1, 0.1),
        ("one two", 3, -0.1),
        ("one two", 3, 1.0),
    ],
)
def test_chunk_text_invalid_inputs_raise(text: str, chunk_size: int, overlap: float) -> None:
    """Invalid chunk inputs should raise ValueError."""
    with pytest.raises(ValueError):
        chunk_text(text=text, chunk_size=chunk_size, overlap=overlap)
