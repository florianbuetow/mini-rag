"""Unit tests for token-budget chunking."""

import pytest
import tiktoken

from minirag.ingestion.token_chunker import chunk_text_by_tokens

ENCODING_NAME = "cl100k_base"


def _encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding(ENCODING_NAME)


def _token_len(text: str) -> int:
    return len(_encoding().encode(text))


def _reconstruct(chunks: list[str], step: int) -> list[int]:
    """Merge overlapping chunk token-streams back into one token list."""
    encoding = _encoding()
    rebuilt: list[int] = []
    for index, chunk in enumerate(chunks):
        chunk_tokens = encoding.encode(chunk)
        start = index * step
        new_from = max(0, len(rebuilt) - start)
        rebuilt.extend(chunk_tokens[new_from:])
    return rebuilt


def test_every_chunk_within_budget() -> None:
    """Every produced chunk stays within the token budget."""
    text = " ".join(f"word{i}" for i in range(2000))
    budget = 50

    chunks = chunk_text_by_tokens(text, max_tokens=budget, overlap=0.2)

    assert len(chunks) > 1
    assert all(_token_len(chunk) <= budget for chunk in chunks)


def test_chunk_size_scales_with_window() -> None:
    """A smaller token window yields smaller, more numerous chunks."""
    text = " ".join(f"word{i}" for i in range(1000))

    small = chunk_text_by_tokens(text, max_tokens=20, overlap=0.2)
    large = chunk_text_by_tokens(text, max_tokens=40, overlap=0.2)

    assert all(_token_len(chunk) <= 20 for chunk in small)
    assert all(_token_len(chunk) <= 40 for chunk in large)
    assert len(small) > len(large)


def test_consecutive_chunks_overlap() -> None:
    """Each chunk after the first repeats the tail tokens of its predecessor."""
    encoding = _encoding()
    text = " ".join(f"word{i}" for i in range(500))
    budget = 40
    overlap = 0.25

    chunks = chunk_text_by_tokens(text, max_tokens=budget, overlap=overlap)

    assert len(chunks) >= 3
    overlap_tokens = budget - int(budget * (1.0 - overlap))
    assert overlap_tokens > 0
    first_tokens = encoding.encode(chunks[0])
    second_tokens = encoding.encode(chunks[1])
    assert len(first_tokens) == budget
    assert first_tokens[-overlap_tokens:] == second_tokens[:overlap_tokens]


def test_chunks_cover_entire_document() -> None:
    """The chunks together cover every token of the source document."""
    encoding = _encoding()
    text = " ".join(f"word{i}" for i in range(500))
    budget = 40
    overlap = 0.25

    chunks = chunk_text_by_tokens(text, max_tokens=budget, overlap=overlap)

    step = int(budget * (1.0 - overlap))
    assert _reconstruct(chunks, step) == encoding.encode(text)


def test_whitespace_free_overbudget_is_split() -> None:
    """A whitespace-free over-budget string is split into within-budget chunks."""
    text = "a" * 5000

    chunks = chunk_text_by_tokens(text, max_tokens=50, overlap=0.2)

    assert len(chunks) > 1
    assert all(_token_len(chunk) <= 50 for chunk in chunks)


def test_5000_char_nospace_input_lossless() -> None:
    """A 5000-character no-space input is chunked losslessly within budget."""
    encoding = _encoding()
    text = "a" * 5000
    budget = 50
    overlap = 0.2

    chunks = chunk_text_by_tokens(text, max_tokens=budget, overlap=overlap)

    assert len(chunks) > 1
    assert all(_token_len(chunk) <= budget for chunk in chunks)
    rebuilt = _reconstruct(chunks, int(budget * (1.0 - overlap)))
    assert encoding.decode(rebuilt) == text


def test_short_document_single_chunk() -> None:
    """A document under the budget yields exactly one chunk."""
    text = "just a short sentence"

    chunks = chunk_text_by_tokens(text, max_tokens=512, overlap=0.3)

    assert len(chunks) == 1
    assert _token_len(chunks[0]) <= 512
    assert chunks[0] == text


def test_nonpositive_step_rejected() -> None:
    """An overlap that collapses the step to zero is rejected."""
    with pytest.raises(ValueError, match="non-positive chunk step"):
        chunk_text_by_tokens("alpha beta gamma", max_tokens=1, overlap=0.99)


@pytest.mark.parametrize(
    ("text", "max_tokens", "overlap"),
    [
        ("", 10, 0.1),
        ("   ", 10, 0.1),
        ("hello", 0, 0.1),
        ("hello", -1, 0.1),
        ("hello", 10, -0.1),
        ("hello", 10, 1.0),
    ],
)
def test_invalid_inputs_raise(text: str, max_tokens: int, overlap: float) -> None:
    """Invalid text or chunk parameters are rejected."""
    with pytest.raises(ValueError):
        chunk_text_by_tokens(text, max_tokens=max_tokens, overlap=overlap)
