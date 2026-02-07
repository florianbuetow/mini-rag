"""Word-based text chunking utilities."""


def chunk_text(text: str, chunk_size: int, overlap: float) -> list[str]:
    """Split text into overlapping word chunks.

    Args:
        text: Full document text to split.
        chunk_size: Number of words per chunk.
        overlap: Fractional overlap in [0.0, 1.0).

    Returns:
        Ordered list of chunk strings.

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

    words = text.split()
    if len(words) == 0:
        raise ValueError("text must contain at least one word")

    chunks: list[str] = []
    start_index = 0
    while start_index < len(words):
        end_index = start_index + chunk_size
        chunk_words = words[start_index:end_index]
        if len(chunk_words) == 0:
            break
        chunks.append(" ".join(chunk_words))
        start_index = start_index + step

    return chunks
