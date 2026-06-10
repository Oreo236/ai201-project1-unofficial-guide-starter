"""
Generation layer for the Cornell off-campus housing RAG pipeline.

ask(question) → {"answer": str, "sources": list[str], "chunks": list[dict]}

Retrieves the top-k most relevant chunks from ChromaDB, builds a strict
grounding prompt, calls Groq (llama-3.3-70b-versatile), and returns the
response with programmatic source attribution — the model is never trusted
to produce the source list itself.
"""

import os
import sys
from dotenv import load_dotenv
from groq import Groq

from embed import retrieve

load_dotenv()

GROQ_MODEL = "llama-3.3-70b-versatile"
TOP_K = 5

# The grounding instruction is in the system prompt so it cannot be overridden
# by user input (prompt injection) and applies to every turn.
_SYSTEM_PROMPT = """\
You are a helpful assistant that answers questions about off-campus housing
for Cornell University students.

STRICT RULES:
1. Answer ONLY using the information in the DOCUMENTS provided by the user.
2. Do NOT draw on your training knowledge about Cornell, Ithaca, or housing
   in general — even if you believe it is accurate.
3. If the documents do not contain enough information to answer the question,
   respond with exactly this sentence and nothing else:
   "I don't have enough information in my documents to answer that question."
4. When documents contain differing opinions, report both perspectives
   without picking a side.
5. Keep answers concise and factual. Do not add caveats or advice beyond
   what the documents say.\
"""


def ask(question: str, k: int = TOP_K) -> dict:
    """
    End-to-end RAG: retrieve chunks → generate grounded answer.

    Returns a dict with:
        answer   – LLM response (grounded in retrieved chunks)
        sources  – deduplicated list of source filenames (programmatic, not LLM-generated)
        chunks   – raw retrieval hits (text, source, distance) for inspection
    """
    chunks = retrieve(question, k=k)

    if not chunks:
        return {
            "answer": "I don't have enough information in my documents to answer that question.",
            "sources": [],
            "chunks": [],
        }

    # Label each chunk by its source so the model can reference documents by number.
    context_parts = []
    for i, c in enumerate(chunks, 1):
        context_parts.append(f"[Document {i}: {c['source']}]\n{c['text']}")
    context = "\n\n".join(context_parts)

    user_message = (
        f"DOCUMENTS:\n{context}\n\n"
        f"QUESTION: {question}\n\n"
        "Answer the question using ONLY the information in the DOCUMENTS above."
    )

    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.1,   # low temperature keeps answers factual and stable
        max_tokens=600,
    )

    answer = response.choices[0].message.content.strip()

    # Build the source list programmatically — never rely on the LLM to list sources.
    seen: set[str] = set()
    sources: list[str] = []
    for c in chunks:
        src = c["source"]
        if src not in seen:
            seen.add(src)
            sources.append(src)

    return {"answer": answer, "sources": sources, "chunks": chunks}


# ── quick CLI test ─────────────────────────────────────────────────────────────

_TEST_QUESTIONS = [
    "What are the characteristics of the Collegetown neighborhood for Cornell students?",
    "What should Cornell students ask a landlord before signing a lease?",
    "What neighborhoods are recommended for Cornell graduate students without a car?",
    # Out-of-scope — the system should decline, not hallucinate.
    "What is the best pizza place near Cornell campus?",
]


def _run_cli_test() -> None:
    for q in _TEST_QUESTIONS:
        print(f"\n{'=' * 70}")
        print(f"Q: {q}")
        print("-" * 70)
        result = ask(q)
        print(f"A: {result['answer']}")
        print(f"\nSources ({len(result['sources'])}): {', '.join(result['sources'])}")
        top = result["chunks"][0] if result["chunks"] else None
        if top:
            print(f"Top chunk distance: {top['distance']:.4f}")


if __name__ == "__main__":
    if "GROQ_API_KEY" not in os.environ:
        print("ERROR: GROQ_API_KEY not set. Copy .env.example to .env and add your key.")
        sys.exit(1)
    _run_cli_test()
