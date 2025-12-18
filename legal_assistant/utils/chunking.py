from typing import List


def _window_words(words: List[str], max_words: int, overlap: int) -> List[str]:
    """Helper: sliding window over a word list with overlap."""
    chunks: List[str] = []
    start = 0
    n = len(words)

    while start < n:
        end = min(start + max_words, n)
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words))

        if end == n:
            break

        start = max(0, end - overlap)

    return chunks


def chunk_text(
    text: str,
    max_words: int = 200,
    overlap: int = 40,
) -> List[str]:
    """
    Hybrid chunker (structure-aware, then sliding window):
    - Normalize newlines and split on blank lines to respect paragraph / email block boundaries.
    - Short paragraphs become single chunks; long paragraphs are windowed with overlap.
    - Overlap is slightly smaller by default (40 words) to reduce redundancy.
    """

    if not text or not text.strip():
        return []

    normalized = text.replace("\r\n", "\n")
    paragraphs = [p.strip() for p in normalized.split("\n\n") if p.strip()]

    chunks: List[str] = []

    for para in paragraphs:
        words = para.split()
        if not words:
            continue

        if len(words) <= max_words:
            chunks.append(" ".join(words))
        else:
            chunks.extend(_window_words(words, max_words=max_words, overlap=overlap))

    return chunks
