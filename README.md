# The Unofficial Guide — Project 1

---

## Domain

My system covers off-campus housing experiences for Cornell University students, focusing on apartment reviews, neighborhood comparisons, lease guidance, tenant rights, and landlord feedback. This knowledge is valuable because official university resources provide only general procedural guidance — they describe *how* to search for housing but rarely capture the practical realities that affect daily student life: maintenance responsiveness, noise levels, security deposit disputes, which bus routes actually run late, or whether a specific apartment complex has a history of flooded basements. Students making $800–$1,200/month housing decisions deserve to ask specific questions and get answers grounded in the experiences of people who actually lived there.

---

## Document Sources

| # | Source | Type | URL or file path |
|---|--------|------|-----------------|
| 1 | Cornell Ithaca Neighborhoods Guide | Cornell official page | https://scl.cornell.edu/residential-life/housing/campus-living/housing-search-process/ithaca-neighborhoods |
| 2 | Cornell Signing the Lease Guide | Cornell official page | https://scl.cornell.edu/residential-life/housing/campus-living/housing-search-process/signing-lease |
| 3 | Cornell Rental Listings & Resources | Cornell official page | https://scl.cornell.edu/residential-life/housing/campus-living/housing-search-process/rental-listings-resources |
| 4 | Cornell Grad Tips: Renting & Tenant Rights | Cornell grad school article | https://www.gradschool.cornell.edu/announcements/grad-tips-renting/ |
| 5 | Cornell Safe Living Environments | Cornell official page | https://scl.cornell.edu/residential-life/housing/campus-living/housing-search-process/safe-living-environments |
| 6 | Supporting the Journey to Off-Campus Living (news article) | Cornell news | https://scl.cornell.edu/news-events/news/supporting-journey-campus-living-cornells-comprehensive-housing-resources |
| 7 | Cornell Off-Campus Living overview | Cornell official page | https://scl.cornell.edu/residential-life/housing/campus-living |
| 8 | r/Cornell — Housing Situation at Cornell (Auden Ithaca) | Reddit thread | documents/clean/auden.txt |
| 9 | r/ithaca — Moving to Titus Towers | Reddit thread | documents/clean/titus_towers.txt |
| 10 | r/Cornell — Housing: northeast Ithaca vs downtown? | Reddit thread | documents/clean/north_vs_downtown.txt |
| 11 | r/Cornell — Where to live in Ithaca? | Reddit thread | documents/clean/where_to_live.txt |

Sources 1–7 were fetched automatically by `ingest.py` using requests + BeautifulSoup. Sources 8–11 were saved manually as plain-text files because Reddit blocks automated scraping.

---

## Chunking Strategy

**Chunk size:** 400 characters

**Overlap:** 80 characters (step size = 320 characters)

**Why these choices fit my documents:** My corpus is mixed — short Reddit opinion threads (300–600 words per reply) and longer structured Cornell guides (1,000–6,000 characters each). At 400 characters, each chunk is large enough to capture a full review opinion or a complete factual sentence with surrounding context, but small enough for retrieval to return topically focused results rather than entire page sections. The 80-character overlap prevents key facts near chunk boundaries from being lost; without it, a sentence that straddles two chunks could be truncated in retrieval, making the model answer "I don't know" when the information is there.

Both chunk start and end boundaries are snapped to the nearest word boundary (space or newline), so no chunk begins or ends mid-word. Chunks shorter than 50 characters are discarded to avoid storing stray headings or punctuation artifacts.

**Preprocessing before chunking:** Each document was cleaned with `clean_text()` in `ingest.py`: HTML entities decoded, non-breaking spaces normalized to regular spaces, carriage returns normalized to `\n`, consecutive blank lines collapsed to a single blank line, and leading/trailing whitespace stripped. For Cornell web pages, a content container was located first (`<article>`, `<main>`, or matching `<div>` IDs) and boilerplate elements (`<nav>`, `<footer>`, `<aside>`, elements with class/id names matching `sidebar`, `cookie`, `banner`, etc.) were stripped before text extraction.

**Final chunk count:** 106 chunks across 11 documents.

---

## Embedding Model

**Model used:** `all-MiniLM-L6-v2` via the `sentence-transformers` library, running entirely locally with no API key or rate limits.

**Why this model:** It is the standard default for local RAG projects — it produces 384-dimensional embeddings that are small enough to embed 106 chunks in under 5 seconds on CPU, and its cosine similarity scores on short English text are consistently reliable for semantic search. The ChromaDB collection was created with `hnsw:space: cosine` so distances are true cosine distances (0 = identical, 1 = orthogonal).

**Production tradeoff reflection:** In a production deployment I would weigh several tradeoffs. Context length is the first: `all-MiniLM-L6-v2` has a hard cap of 256 tokens, which fits my 400-character chunks (roughly 80–100 tokens) but would silently truncate any chunk longer than that. Models like `text-embedding-3-large` (OpenAI) or `embed-english-v3.0` (Cohere) support up to 8,000 tokens, which would matter if I moved to larger document types like PDF leases. Domain specificity is the second: general-purpose sentence embedding models were not trained on Cornell-specific terminology, apartment building names, or local neighborhood slang. A domain-fine-tuned model or a hybrid approach (BM25 + dense retrieval) would likely outperform on proper-noun-heavy queries like "Auden Ithaca" or "Collegetown Terrace." Latency is less of a concern for this use case since users are asking single questions, not making hundreds of API calls per second.

---

## Grounded Generation

**System prompt grounding instruction:**

The system prompt given to the LLM at every request is:

> You are a helpful assistant that answers questions about off-campus housing for Cornell University students.
>
> STRICT RULES:
> 1. Answer ONLY using the information in the DOCUMENTS provided by the user.
> 2. Do NOT draw on your training knowledge about Cornell, Ithaca, or housing in general — even if you believe it is accurate.
> 3. If the documents do not contain enough information to answer the question, respond with exactly this sentence and nothing else: "I don't have enough information in my documents to answer that question."
> 4. When documents contain differing opinions, report both perspectives without picking a side.
> 5. Keep answers concise and factual. Do not add caveats or advice beyond what the documents say.

Rule 2 explicitly forbids using training knowledge, not just "prefer documents" — this is intentional. In testing, a softer instruction ("use the documents") produced answers that blended retrieved text with model training knowledge, making it impossible to attribute what came from where.

The user message wraps the top-5 retrieved chunks in a labeled `DOCUMENTS:` block, with each chunk tagged `[Document N: source_filename.txt]` so the model can reference specific sources. Temperature is set to 0.1 for factual, low-variance outputs.

**How source attribution is surfaced in the response:**

Source attribution is built programmatically in `query.py` — after the LLM returns its answer, the code iterates over the `chunks` list returned by `retrieve()`, deduplicates filenames in order, and returns them as a `sources` list. This list is never generated by the LLM; the model cannot accidentally omit a source or fabricate one. The Gradio interface displays this list separately in a "Retrieved from" panel alongside the answer.

---

## Evaluation Report

| # | Question | Expected answer | System response (summarized) | Retrieval quality | Response accuracy |
|---|----------|-----------------|------------------------------|-------------------|-------------------|
| 1 | What do students say about living at Auden Ithaca apartments? | Mixed experiences: unreliable email contact, laundry outage 1–2 months, $40/month parking, small rooms ~$750/month, inconsistent shuttle, rated 7/10 | "One student gives Auden a rating of 7/10." | Off-target (top chunk from Cornell news article, not from auden.txt) | Inaccurate (technically true but drastically incomplete) |
| 2 | What are the pros and cons of living in Collegetown vs downtown Ithaca? | Collegetown: walkable, expensive, loud, undergrad-heavy. Downtown: late bus service, more independent feel, preferred by grad students | Collegetown: popular, noisy, uphill walks. Downtown: "mostly residential, less convenient without cars" — contradicts expected answer | Partially relevant | Partially accurate |
| 3 | What should Cornell students ask a landlord before signing a lease? | Ask about repair responsibilities, emergency contact method, how long previous tenants stayed, why they left, and how security deposit was handled | "Suggests printing the Lease Signing Checklist but specific questions are not listed in the documents" | Relevant (correct page retrieved) | Partially accurate (honest about the gap, but the checklist content exists in the corpus) |
| 4 | What resources does Cornell offer students with landlord problems? | Off-Campus Living, City of Ithaca Building Department, Community Dispute Resolution Center, NYS AG's office, NYS Tenants Rights Guide | Cornell Off-Campus Living helps with all issues, refers to right resources, NYS Tenants Rights Guide available online and in-office | Relevant | Partially accurate (misses specific external offices) |
| 5 | What neighborhoods are recommended for Cornell grad students without a car? | Downtown (Seneca/Green bus routes, late service); University Park/Gaslight Village (flat bike ride, one bus to campus); Fall Creek (loved but needs car) | Collegetown and downtown have good walkability and transit; some grad students take bus from farther neighborhoods | Partially relevant | Partially accurate (correct direction, low specificity) |

---

## Failure Case Analysis

**Question that failed:** Q1 — "What do students say about living at Auden Ithaca apartments?"

**What the system returned:** "One student gives Auden a rating of 7/10." — a single fragment from the corpus, missing nearly all the detail that exists in `auden.txt`.

**Root cause (tied to a specific pipeline stage):** This is a retrieval failure caused by a semantic mismatch in the embedding model. The query contains the proper noun "Auden Ithaca" — a specific apartment complex — but `all-MiniLM-L6-v2` does not have a meaningful embedding for this name. Instead, the model encodes the query based on the generic semantic meaning of the surrounding words ("students," "living," "apartments"), which causes it to match on any housing-related text. The top-ranked chunk (cosine distance 0.3059) came from `cornell_off_campus_news.txt`, a Cornell news article that mentions housing resources generally and contains a brief reference to Auden — not from `auden.txt`, the document that contains four detailed student reviews. The `auden.txt` chunks scored lower despite being the most directly relevant source, because their content (shuttle schedules, parking prices, laundry complaints) shares less semantic overlap with the high-level query phrasing than the Cornell news article's summary language does.

The model then received only a partial mention of Auden from the news article and accurately reported only what that chunk said — the 7/10 rating — while the rich detail in `auden.txt` was never surfaced.

**What I would change to fix it:**

1. **Increase k and filter by relevance**: Raising `k` from 5 to 8 would increase the chance that `auden.txt` chunks appear in the context even if not top-ranked, at the cost of diluting context with loosely related material.
2. **BM25 hybrid retrieval**: Adding a keyword-based BM25 retrieval pass alongside the dense embedding pass would ensure that documents containing the exact string "Auden" are always retrieved, regardless of semantic distance. Hybrid retrieval is the standard fix for proper-noun and entity lookup failures.
3. **Document-level metadata filtering**: Storing a "building name" metadata field on chunks and adding a pre-filter step that routes proper-noun queries directly to the matching document before semantic ranking.

---

## Spec Reflection

**One way the spec helped during implementation:**

The Chunking Strategy section of `planning.md` — specifically the decision to use 400-character chunks with 80-character overlap and word-boundary snapping — saved significant debugging time during implementation. When the initial chunk count exploded to 394 after adding word-boundary snapping (caused by a stall-at-EOF bug where the step size collapsed to 1 near the end of each document), having the spec's chunk size and overlap as fixed reference points made it immediately obvious that something was wrong and gave a concrete target to validate against (106 chunks, not 394). Without a written spec, it would have been easy to assume the inflated count was correct.

**One way the implementation diverged from the spec, and why:**

The spec listed four planned manual document sources — `cayuga_apartments.txt`, `ithaca_reviews.txt`, `reddit_cornellhousing.txt`, and `reddit_ithaca.txt`. In practice, these were replaced with four different Reddit threads: `auden.txt`, `titus_towers.txt`, `north_vs_downtown.txt`, and `where_to_live.txt`. The divergence happened because ApartmentRatings pages for Ithaca are very thin (some buildings have 2–3 reviews total), and the named Reddit threads were richer, more specific, and more directly answerable against the evaluation plan questions. The spec was updated to reflect this change before proceeding to chunking, which kept the implementation and documentation in sync even though the source list changed.

---

## AI Usage

**Instance 1 — Ingestion and HTML cleaning pipeline**

- *What I gave the AI:* The Documents section of `planning.md` (12 sources with URLs and collection methods), the Milestone 3 requirements, and a note that Reddit/ApartmentRatings sources are pre-saved `.txt` files while Cornell pages should be fetched via requests + BeautifulSoup.
- *What it produced:* A complete `ingest.py` with `fetch_cornell()`, `clean_text()`, and `load_manual()` functions. The initial version applied `_strip_boilerplate()` to the full page soup — which caused a bug where any Cornell page whose `<body>` tag had a class containing "sidebar" was wiped entirely, returning only 65 characters of content.
- *What I changed or overrode:* I directed the AI to restructure `fetch_cornell()` to call `_find_main_content(soup)` first and only then strip boilerplate within that container, never on the full body. This two-phase approach (locate content, then clean within it) fixed the blank-page bug. I also had the AI add `\xa0` (non-breaking space) decoding to `clean_text()` after spotting it in a chunk during the quality audit.

**Instance 2 — Chunk boundary bug in chunk.py**

- *What I gave the AI:* The `chunk_text()` function, the symptom (chunk count jumped from 109 to 394 after adding word-boundary snapping), and a debug trace showing `start=999, end=1078, chunk_len=79, step=1` — confirming an infinite crawl near the end of each document.
- *What it produced:* An explanation of the root cause: when the remaining text is shorter than the overlap (80 chars), `step = end - start - overlap` becomes negative or near-zero, causing the loop to advance by 1 character per iteration. The fix was `start += max(step, end - start - overlap)` where `step = chunk_size - overlap = 320`, guaranteeing a minimum advance equal to the intended stride.
- *What I changed or overrode:* I verified the fix by re-running the chunk count (back to 106) and manually inspecting 5 representative chunks before accepting it. I also kept the word-boundary forward-snap for `start` that the AI had introduced, since it correctly prevents chunks from beginning mid-word.
