"""
Text and code chunking utilities.
Splits documents into overlapping chunks for embedding.
"""
from typing import List


def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> List[str]:
    """
    Split text into overlapping word-based chunks.
    chunk_size: max words per chunk
    overlap: words shared between consecutive chunks
    """
    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk.strip())
        start += chunk_size - overlap

    # Skip tiny chunks (less than 50 chars)
    return [c for c in chunks if len(c.strip()) > 50]


def chunk_code(code: str, max_lines: int = 50) -> List[str]:
    """
    Split code by lines, keeping logical blocks together.
    Last 10 lines overlap for context continuity.
    """
    lines = code.split("\n")
    chunks = []
    current = []

    for line in lines:
        current.append(line)
        if len(current) >= max_lines:
            chunks.append("\n".join(current))
            current = current[-10:]  # keep last 10 lines as overlap

    if current:
        chunks.append("\n".join(current))

    return [c for c in chunks if c.strip()]
