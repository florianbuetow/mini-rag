"""Unit tests for word chunking."""

import pytest

from minirag.ingestion.chunker import ChunkSpan, chunk_text


def test_chunk_text_splits_with_overlap() -> None:
    """Chunker should split words with configured overlap."""
    text = "one two three four five six seven eight nine ten"
    chunks = chunk_text(text=text, chunk_size=4, overlap=0.5)

    assert [chunk.text for chunk in chunks] == [
        "one two three four",
        "three four five six",
        "five six seven eight",
        "seven eight nine ten",
        "nine ten",
    ]


def test_chunk_text_spans_reference_original_text() -> None:
    """Spans point at the exact region of the original text including whitespace."""
    text = "one  two\nthree four five"
    chunks = chunk_text(text=text, chunk_size=3, overlap=0.0)

    assert [chunk.text for chunk in chunks] == ["one two three", "four five"]
    assert chunks[0].char_start == 0
    assert text[chunks[0].char_start : chunks[0].char_end] == "one  two\nthree"
    assert text[chunks[1].char_start : chunks[1].char_end] == "four five"
    assert chunks[1].char_end == len(text)


def test_chunk_text_span_boundaries_exclude_surrounding_whitespace() -> None:
    """Chunk spans start at the first word and end at the last word of the chunk."""
    text = "  alpha   beta\n\ngamma  "
    chunks = chunk_text(text=text, chunk_size=2, overlap=0.0)

    assert [chunk.text for chunk in chunks] == ["alpha beta", "gamma"]
    assert text[chunks[0].char_start : chunks[0].char_end] == "alpha   beta"
    assert text[chunks[1].char_start : chunks[1].char_end] == "gamma"


def test_chunk_text_overlapping_spans_are_monotonic_and_bounded() -> None:
    """Overlapping chunks produce monotonically increasing, in-bounds spans."""
    text = "one two three four five six seven eight nine ten"
    chunks = chunk_text(text=text, chunk_size=4, overlap=0.5)

    assert isinstance(chunks[0], ChunkSpan)
    for chunk in chunks:
        assert 0 <= chunk.char_start < chunk.char_end <= len(text)
    starts = [chunk.char_start for chunk in chunks]
    assert starts == sorted(starts)


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
