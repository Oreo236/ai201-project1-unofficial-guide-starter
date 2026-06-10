"""
Embedding and retrieval for the Cornell off-campus housing RAG pipeline.

Loads cleaned chunks from documents/clean/, embeds them with
all-MiniLM-L6-v2 (sentence-transformers), and persists them in a local
ChromaDB collection.  Also exposes retrieve() for use by the generation
layer in Milestone 5.

Run ingest.py and chunk.py first (or just ingest.py — embed.py chunks
on the fly using the same chunk_text() logic).

Usage:
    python embed.py           # build / refresh the vector store
    python embed.py --test    # build + run retrieval test queries
"""

import argparse
import sys
from pathlib import Path

from chromadb import PersistentClient
from sentence_transformers import SentenceTransformer

# Re-use the exact same chunking logic so embed.py stays in sync.
from chunk import chunk_text

# ── paths & constants ──────────────────────────────────────────────────────────
CLEAN_DIR = Path("documents/clean")
CHROMA_DIR = Path("chroma_db")
COLLECTION_NAME = "cornell_housing"
EMBED_MODEL = "all-MiniLM-L6-v2"
DEFAULT_K = 5


# ── module-level singletons (lazy-loaded) ─────────────────────────────────────
_model: SentenceTransformer | None = None
_collection = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print(f"Loading embedding model ({EMBED_MODEL}) …", flush=True)
        _model = SentenceTransformer(EMBED_MODEL)
    return _model


def _get_collection():
    global _collection
    if _collection is None:
        client = PersistentClient(path=str(CHROMA_DIR))
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


# ── public API ─────────────────────────────────────────────────────────────────

def build_index() -> int:
    """
    Embed all chunks and upsert them into ChromaDB.
    Returns the total number of chunks indexed.
    """
    model = _get_model()
    collection = _get_collection()

    all_ids: list[str] = []
    all_texts: list[str] = []
    all_meta: list[dict] = []

    print(f"\nLoading and chunking documents from {CLEAN_DIR} …")
    for path in sorted(CLEAN_DIR.glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        chunks = chunk_text(text)
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{path.stem}__chunk{idx:04d}"
            all_ids.append(chunk_id)
            all_texts.append(chunk)
            all_meta.append({"source": path.name, "chunk_index": idx})
        print(f"  {path.name}: {len(chunks)} chunks")

    total = len(all_texts)
    print(f"\nEmbedding {total} chunks …", flush=True)
    embeddings = model.encode(all_texts, show_progress_bar=True, batch_size=64)

    print("Upserting into ChromaDB …", flush=True)
    # Upsert in batches of 500 to stay within ChromaDB's default limits.
    batch = 500
    for i in range(0, total, batch):
        collection.upsert(
            ids=all_ids[i : i + batch],
            documents=all_texts[i : i + batch],
            embeddings=embeddings[i : i + batch].tolist(),
            metadatas=all_meta[i : i + batch],
        )

    stored = collection.count()
    print(f"\nVector store contains {stored} chunks (collection: '{COLLECTION_NAME}')")
    print(f"Persisted to {CHROMA_DIR}/")
    return total


def retrieve(query: str, k: int = DEFAULT_K) -> list[dict]:
    """
    Return the top-k most relevant chunks for *query*.

    Each result dict has:
        text      – chunk text
        source    – source filename (e.g. 'cornell_signing_lease.txt')
        chunk_index – position within that document
        distance  – cosine distance (lower = more similar; 0 = identical)
    """
    model = _get_model()
    collection = _get_collection()

    query_embedding = model.encode([query])[0].tolist()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        hits.append(
            {
                "text": doc,
                "source": meta["source"],
                "chunk_index": meta["chunk_index"],
                "distance": round(dist, 4),
            }
        )
    return hits


# ── retrieval test ─────────────────────────────────────────────────────────────

TEST_QUERIES = [
    "What are the characteristics of the Collegetown neighborhood for Cornell students?",
    "What should Cornell students ask a landlord before signing a lease?",
    "What neighborhoods are recommended for Cornell graduate students looking for lower rent?",
]


def run_retrieval_test() -> None:
    print("\n" + "=" * 70)
    print("RETRIEVAL TEST — 3 evaluation plan queries")
    print("=" * 70)

    for q in TEST_QUERIES:
        print(f"\nQuery: {q}")
        print("-" * 60)
        hits = retrieve(q, k=DEFAULT_K)
        for rank, hit in enumerate(hits, 1):
            print(
                f"  [{rank}] dist={hit['distance']:.4f}  "
                f"src={hit['source']}  chunk#{hit['chunk_index']}"
            )
            # Print first 200 chars of the chunk for a quick relevance check.
            preview = hit["text"][:200].replace("\n", " ")
            print(f"       {preview!r}")
        print()


# ── entry point ────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Embed chunks into ChromaDB.")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run retrieval test queries after building the index.",
    )
    args = parser.parse_args()

    if not CLEAN_DIR.exists():
        print(f"ERROR: {CLEAN_DIR} not found. Run ingest.py first.")
        return 1

    build_index()

    if args.test:
        run_retrieval_test()

    return 0


if __name__ == "__main__":
    sys.exit(main())
