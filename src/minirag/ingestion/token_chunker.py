"""Token-budget text chunking for token-limited embedding models.

Unlike the word-based :func:`minirag.ingestion.chunker.chunk_text`, this chunker
counts tokens with ``tiktoken`` and slices on token boundaries, so every chunk stays
within a model's token window even when the input contains no whitespace.
"""

import tiktoken

from minirag.ingestion.chunker import ChunkSpan

_ENCODING_CACHE: dict[str, tiktoken.Encoding] = {}


def _get_encoding(encoding_name: str) -> tiktoken.Encoding:
    """Return a cached tiktoken encoding by name."""
    cached = _ENCODING_CACHE.get(encoding_name)
    if cached is not None:
        return cached
    encoding = tiktoken.get_encoding(encoding_name)
    _ENCODING_CACHE[encoding_name] = encoding
    return encoding


def _validated_step(text: str, max_tokens: int, overlap: float) -> int:
    """Validate chunk parameters and return the token step between windows."""
    if text.strip() == "":
        raise ValueError("text must not be empty or whitespace only")

    if max_tokens <= 0:
        raise ValueError("max_tokens must be greater than 0")

    if overlap < 0.0:
        raise ValueError("overlap must be greater than or equal to 0.0")

    if overlap >= 1.0:
        raise ValueError("overlap must be less than 1.0")

    step = int(float(max_tokens) * (1.0 - overlap))
    if step <= 0:
        raise ValueError("overlap produces a non-positive chunk step")

    return step


def chunk_text_by_tokens(text: str, max_tokens: int, overlap: float) -> list[ChunkSpan]:
    """Split text into overlapping chunks, each within a token budget, with source spans.

    Token counts use the ``cl100k_base`` encoding as a stable, offline approximation
    of the embedding model's tokenizer.

    Args:
        text: Full document text to split.
        max_tokens: Maximum tokens per chunk (the token budget, already reduced by
            any safety fraction by the caller).
        overlap: Fractional overlap in [0.0, 1.0).

    Returns:
        Ordered list of chunk spans, each with a token count <= ``max_tokens``;
        span offsets reference ``text``.

    Raises:
        ValueError: If input text or chunk parameters are invalid.
    """
    step = _validated_step(text, max_tokens, overlap)

    encoding = _get_encoding("cl100k_base")
    tokens = encoding.encode(text)
    if len(tokens) == 0:
        raise ValueError("text must contain at least one token")

    # Token boundaries as byte offsets into the UTF-8 encoding of ``text``. BPE is
    # lossless over bytes, so the per-token byte lengths partition ``text_bytes``.
    text_bytes = text.encode("utf-8")
    token_byte_offsets = [0]
    for token in tokens:
        token_byte_offsets.append(token_byte_offsets[-1] + len(encoding.decode_single_token_bytes(token)))

    def byte_to_char_offset(byte_offset: int) -> int:
        # A token boundary can fall inside a multibyte character; snap down to the
        # character start so span offsets always index valid character positions.
        while 0 < byte_offset < len(text_bytes) and (text_bytes[byte_offset] & 0xC0) == 0x80:
            byte_offset -= 1
        return len(text_bytes[:byte_offset].decode("utf-8"))

    chunks: list[ChunkSpan] = []
    start_index = 0
    while start_index < len(tokens):
        window = tokens[start_index : start_index + max_tokens]
        if len(window) == 0:
            break

        chunk = encoding.decode(window)
        # Decoding a token slice can, at multibyte boundaries, re-encode to slightly
        # more tokens than the slice; trim defensively so the budget always holds.
        while len(window) > 1 and len(encoding.encode(chunk)) > max_tokens:
            window = window[:-1]
            chunk = encoding.decode(window)

        chunks.append(
            ChunkSpan(
                text=chunk,
                char_start=byte_to_char_offset(token_byte_offsets[start_index]),
                char_end=byte_to_char_offset(token_byte_offsets[start_index + len(window)]),
            )
        )
        start_index = start_index + step

    return chunks
