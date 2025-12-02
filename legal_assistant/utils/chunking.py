from typing import List


def chunk_text(
    text: str,
    max_words: int = 200,
    overlap: int = 50,
) -> List[str]:
    """
    Very simple word-based chunker.

    - Splits text into chunks of up to `max_words`
    - Consecutive chunks overlap by `overlap` words
    - This is a rough approximation of token-based chunking, good enough for a prototype
    """
    words = text.split()
    if not words:
        return []

    chunks: List[str] = []
    start = 0
    n = len(words)

    while start < n:
        end = min(start + max_words, n)
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words))

        if end == n:
            break

        # Move start forward with overlap
        start = max(0, end - overlap)

    return chunks
