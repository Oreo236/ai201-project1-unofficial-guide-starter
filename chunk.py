"""
Chunking script for the Cornell off-campus housing RAG pipeline.

Loads cleaned documents from documents/clean/, splits each into
overlapping character-level chunks (400 chars, 80-char overlap),
prints 5 representative samples, and reports the total count.

Run ingest.py before this script.
"""

import sys
from pathlib import Path

CLEAN_DIR = Path("documents/clean")
CHUNK_SIZE = 400
OVERLAP = 80


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> list[str]:
    """Split text into overlapping chunks, snapping both boundaries to whole words."""
    chunks = []
    start = 0
    length = len(text)
    step = chunk_size - overlap

    while start < length:
        end = min(start + chunk_size, length)

        # Snap end back to nearest word boundary (space or newline).
        if end < length:
            boundary = max(text.rfind(" ", start, end), text.rfind("\n", start, end))
            if boundary > start:
                end = boundary

        chunk = text[start:end].strip()
        if len(chunk) >= 50:
            chunks.append(chunk)

        # Always advance by at least the default step so we never stall near EOF.
        start += max(step, end - start - overlap)

        # Snap start forward to the next word boundary so chunks never begin mid-word.
        if start > 0 and start < length and text[start - 1] not in (" ", "\n", "\t", "\r"):
            while start < length and text[start] not in (" ", "\n", "\t", "\r"):
                start += 1
        while start < length and text[start] in (" ", "\n", "\t", "\r"):
            start += 1

    return chunks


def main() -> int:
    if not CLEAN_DIR.exists():
        print(f"ERROR: {CLEAN_DIR} not found. Run ingest.py first.")
        return 1

    all_chunks: list[tuple[str, str]] = []  # (source_filename, chunk_text)

    print("=== Chunking documents ===")
    for path in sorted(CLEAN_DIR.glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        chunks = chunk_text(text)
        for c in chunks:
            all_chunks.append((path.name, c))
        print(f"  {path.name}: {len(chunks)} chunks")

    total = len(all_chunks)
    print(f"\nTotal chunks: {total}")

    if total < 50:
        print("WARNING: Fewer than 50 chunks — documents may be very thin or chunks too large.")
    elif total > 2000:
        print("WARNING: More than 2,000 chunks — chunks may be too small for meaningful retrieval.")
    else:
        print("Chunk count looks healthy (50–2,000 range).")

    if not all_chunks:
        return 1

    # Pick 5 evenly spaced samples so the selection spans the full corpus.
    step = max(1, total // 5)
    samples = [all_chunks[min(i * step, total - 1)] for i in range(5)]

    print("\n=== 5 representative chunks ===\n")
    for i, (source, chunk) in enumerate(samples, 1):
        print(f"--- Chunk {i} (from {source}, {len(chunk)} chars) ---")
        print(chunk)
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
