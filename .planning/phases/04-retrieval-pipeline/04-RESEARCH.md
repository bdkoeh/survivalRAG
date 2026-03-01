# Phase 4: Retrieval Pipeline - Research

**Researched:** 2026-03-01
**Domain:** Vector similarity search, hybrid retrieval (BM25 + dense), prompt assembly for RAG
**Confidence:** HIGH

## Summary

Phase 4 builds the retrieval pipeline that connects user queries to the embedded knowledge base and assembles structured prompts for downstream LLM response generation. The core stack is ChromaDB (embedded, persistent mode) for vector similarity search, bm25s for keyword-based BM25 retrieval, and a custom Reciprocal Rank Fusion (RRF) implementation to combine both ranked result lists. ChromaDB v1.5+ natively supports array metadata fields with `$contains` filtering, which maps directly to the multi-category OR-logic requirement.

The key architectural decisions are already locked by CONTEXT.md: always-on hybrid search (every query runs both BM25 and vector), RRF for fusion, in-memory BM25 index rebuilt at startup, fixed cosine similarity threshold for refusal, and safety warnings always injected into prompts even when their source chunks are not retrieved. The prompt assembly module (`pipeline/prompt.py`) is separated from retrieval logic.

**Primary recommendation:** Use ChromaDB >= 1.5.0 with cosine distance space and bm25s (not rank_bm25, which is unmaintained). Build a thin retrieval module (`pipeline/retrieve.py`) that runs both searches, fuses via RRF, applies threshold filtering, and hands results to a separate prompt assembly module (`pipeline/prompt.py`). Store categories as array metadata in ChromaDB for clean `$contains` filtering.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Fixed cosine similarity score cutoff -- a single threshold value determines whether chunks are relevant
- Threshold is system-level configuration only (env var or config file) -- not adjustable per query
- When no chunks pass the threshold, the system refuses without calling the LLM
- Always-on hybrid search: every query runs both BM25 keyword and vector similarity
- Reciprocal Rank Fusion (RRF) combines the two ranked lists -- no need to normalize different score scales
- BM25 index is built in-memory at application startup from chunk text, rebuilt on each restart
- Strict pre-filter: when a category is specified, only chunks tagged with that category are searched
- Multi-category filtering with OR logic: user can pass multiple categories and get chunks matching any of them
- Default when no filter specified: search all categories
- Categories are internal filtering metadata -- not surfaced in retrieval results (downstream phases handle display)
- Retrieved chunks ordered by relevance score, highest first (primacy bias benefit for small LLMs)
- Each chunk in the prompt includes: document name, section heading, page number
- Safety warnings from chunk metadata are always injected into the prompt, even if the warning chunk itself wasn't retrieved -- safety-first
- Prompt assembly lives in a dedicated module (pipeline/prompt.py), separate from retrieval logic

### Claude's Discretion
- Refusal message wording and delivery mechanism (hard canned message vs LLM-generated)
- Maximum number of chunks to include in prompt context
- Whether medical terminology needs a synonym/abbreviation expansion map for BM25, or if the embedding model handles it sufficiently
- Exact cosine similarity threshold value (to be tuned against the benchmark from Phase 3)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RETR-01 | User query is embedded and matched against the knowledge base via vector similarity search | ChromaDB `collection.query(query_embeddings=...)` with cosine distance space; Ollama nomic-embed-text with `search_query:` prefix for query embedding |
| RETR-02 | User can optionally filter retrieval by content category | ChromaDB array metadata with `$contains` operator for single category, `$or` + `$contains` for multi-category OR logic; strict pre-filter via `where` parameter |
| RETR-03 | Chunks below a relevance threshold are discarded -- if no chunks pass, the system returns "insufficient context" without calling the LLM | ChromaDB returns cosine distances; convert to similarity via `1 - distance`; compare against configured threshold; return canned refusal message when no chunks pass |
| RETR-04 | Hybrid search (BM25 keyword + vector similarity) is available for medical terminology accuracy | bm25s library for in-memory BM25 index; RRF (k=60) to fuse BM25 and vector ranked lists; always-on per CONTEXT.md decision |
| RETR-05 | Retrieved context is assembled into a prompt with source metadata for citation | Dedicated `pipeline/prompt.py` module; chunks ordered by RRF score (highest first); each chunk block includes source_document, section_header, page_number from ChunkMetadata; safety warnings injected from chunk warning_text metadata |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| chromadb | >= 1.5.0 | Embedded vector database with persistent local storage | Native array metadata `$contains` for category filtering; cosine distance space; pre-computed embedding support; Rust-core backend (4x perf vs older Python); MIT license |
| bm25s | >= 0.3.0 | BM25 keyword search with in-memory index | Pure Python + NumPy; 10-1000x faster than rank_bm25; actively maintained (Feb 2026); MIT license; in-memory index support |
| ollama | >= 0.6.1 | Embedding queries via nomic-embed-text | Already in requirements.txt; same library used for Phase 2 classification |
| pydantic | >= 2.0 | Query/result schemas | Already in requirements.txt; established project pattern |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| numpy | (transitive via bm25s) | RRF score computation, array operations | Score merging, threshold comparison |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| bm25s | rank_bm25 0.2.2 | rank_bm25 is unmaintained (last release Feb 2022); significantly slower; bm25s is a drop-in replacement with better performance |
| ChromaDB PersistentClient | FAISS + SQLite | FAISS has no built-in metadata filtering; would need custom metadata layer; ChromaDB handles both vector search and metadata filtering in one package |
| Custom RRF | LangChain EnsembleRetriever | Adds heavy dependency for a 15-line function; RRF is trivial to implement correctly |

**Installation:**
```bash
pip install "chromadb>=1.5.0" "bm25s>=0.3.0"
```

Add to requirements.txt:
```
chromadb>=1.5.0
bm25s>=0.3.0
```

## Architecture Patterns

### Recommended Project Structure
```
pipeline/
├── models.py         # Existing: ChunkMetadata, ChunkRecord, ContentType, CategoryLiteral
├── retrieve.py       # NEW: Vector search, BM25 search, RRF fusion, threshold filtering
├── prompt.py         # NEW: Context assembly, safety warning injection, prompt formatting
├── ingest.py         # NEW: Load chunks into ChromaDB from Phase 3 JSONL output
└── ...               # Existing pipeline modules
```

### Pattern 1: Retrieval Module (pipeline/retrieve.py)
**What:** Single module that encapsulates all retrieval logic -- vector search, BM25 search, RRF fusion, threshold filtering, and category pre-filtering.
**When to use:** Every query goes through this module.
**Example:**
```python
# Source: ChromaDB docs + CONTEXT.md decisions
import chromadb
import bm25s
import numpy as np
from typing import Optional
from pipeline.models import ChunkMetadata

# --- Initialization ---
client = chromadb.PersistentClient(path="./data/chroma")
collection = client.get_or_create_collection(
    name="survivalrag",
    configuration={"hnsw": {"space": "cosine"}}
)

# BM25 index built at startup
bm25_index: bm25s.BM25 = None  # initialized in build_bm25_index()

def build_bm25_index(chunk_texts: list[str]) -> bm25s.BM25:
    """Build in-memory BM25 index from all chunk texts. Called at startup."""
    retriever = bm25s.BM25()
    corpus_tokens = bm25s.tokenize(chunk_texts)
    retriever.index(corpus_tokens)
    return retriever

# --- Query ---
def retrieve(
    query: str,
    categories: Optional[list[str]] = None,
    n_results: int = 10,
    threshold: float = 0.3,
) -> list[dict]:
    """Run hybrid search, fuse with RRF, filter by threshold."""
    # 1. Embed query via Ollama
    query_embedding = embed_query(query)  # uses search_query: prefix

    # 2. Build category filter
    where_filter = None
    if categories:
        if len(categories) == 1:
            where_filter = {"categories": {"$contains": categories[0]}}
        else:
            where_filter = {
                "$or": [{"categories": {"$contains": c}} for c in categories]
            }

    # 3. Vector search via ChromaDB
    vector_results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results * 2,  # over-fetch for fusion
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    # 4. BM25 search (with same category filtering applied post-hoc)
    bm25_results = bm25_search(query, n_results * 2, categories)

    # 5. RRF fusion
    fused = reciprocal_rank_fusion(vector_results, bm25_results, k=60)

    # 6. Threshold filtering (cosine similarity = 1 - cosine distance)
    passed = [r for r in fused if r["similarity"] >= threshold]

    # 7. Return top-n or refusal
    if not passed:
        return []  # caller checks empty list -> refusal

    return passed[:n_results]
```

### Pattern 2: Reciprocal Rank Fusion
**What:** Combine two ranked lists using only rank positions, not raw scores.
**When to use:** Every query (always-on hybrid search per CONTEXT.md).
**Example:**
```python
# Source: Original RRF paper (Cormack et al. 2009), k=60 is standard
def reciprocal_rank_fusion(
    vector_results: dict,
    bm25_results: list[tuple[str, float]],
    k: int = 60,
) -> list[dict]:
    """Fuse vector and BM25 ranked lists using RRF.

    RRF score = sum(1 / (k + rank)) across all lists where doc appears.
    k=60 empirically optimal (insensitive to exact value).
    """
    scores: dict[str, float] = {}
    metadata_map: dict[str, dict] = {}
    text_map: dict[str, str] = {}

    # Vector results (ChromaDB column-major format)
    for rank, (doc_id, distance, doc, meta) in enumerate(zip(
        vector_results["ids"][0],
        vector_results["distances"][0],
        vector_results["documents"][0],
        vector_results["metadatas"][0],
    )):
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
        metadata_map[doc_id] = meta
        text_map[doc_id] = doc
        # Store cosine similarity for threshold check
        metadata_map[doc_id]["_similarity"] = 1 - distance

    # BM25 results
    for rank, (doc_id, bm25_score) in enumerate(bm25_results):
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
        # metadata/text already stored if also in vector results

    # Sort by RRF score descending
    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)

    return [
        {
            "id": doc_id,
            "rrf_score": scores[doc_id],
            "similarity": metadata_map.get(doc_id, {}).get("_similarity", 0),
            "text": text_map.get(doc_id, ""),
            "metadata": metadata_map.get(doc_id, {}),
        }
        for doc_id in sorted_ids
        if doc_id in metadata_map  # only return docs with full metadata
    ]
```

### Pattern 3: Prompt Assembly (pipeline/prompt.py)
**What:** Assemble retrieved chunks into a structured prompt with source metadata and safety warnings.
**When to use:** After retrieval, before LLM call.
**Example:**
```python
# Source: CONTEXT.md decisions
def assemble_prompt(
    query: str,
    retrieved_chunks: list[dict],
    safety_warnings: list[dict],
) -> str:
    """Build structured prompt with context, metadata, and safety warnings.

    Chunks ordered by relevance (highest first) for primacy bias benefit.
    Safety warnings always injected even if their source chunk wasn't retrieved.
    """
    parts = []

    # System instruction
    parts.append("You are a survival and emergency preparedness reference tool.")
    parts.append("Answer ONLY from the provided context. If the context is insufficient, say so.")
    parts.append("Cite your sources by document name and page number.")
    parts.append("")

    # Safety warnings (always first -- safety-first principle)
    if safety_warnings:
        parts.append("=== SAFETY WARNINGS (MUST be included in response) ===")
        for w in safety_warnings:
            parts.append(f"WARNING [{w['source_document']}]: {w['warning_text']}")
        parts.append("")

    # Retrieved context (ordered by relevance score, highest first)
    parts.append("=== REFERENCE CONTEXT ===")
    for i, chunk in enumerate(retrieved_chunks, 1):
        meta = chunk["metadata"]
        parts.append(f"--- Source {i}: {meta['source_document']}, "
                     f"Section: {meta['section_header']}, "
                     f"Page: {meta['page_number']} ---")
        parts.append(chunk["text"])
        parts.append("")

    # User query
    parts.append(f"=== QUESTION ===")
    parts.append(query)

    return "\n".join(parts)
```

### Pattern 4: Safety Warning Injection
**What:** Collect safety warnings associated with retrieved chunks (from chunk metadata warning_text field) and always inject them into the prompt.
**When to use:** During prompt assembly, after retrieval.
**Example:**
```python
# Source: CONTEXT.md -- safety warnings always injected, CLAUDE.md -- safety-first principle
def collect_safety_warnings(
    retrieved_chunks: list[dict],
    all_chunk_metadata: dict[str, dict],  # doc_id -> metadata
) -> list[dict]:
    """Collect safety warnings from retrieved chunks AND their sibling chunks.

    Per CONTEXT.md: safety warnings from chunk metadata are always injected
    into the prompt, even if the warning chunk itself wasn't retrieved.

    Strategy: For each retrieved chunk, look up all chunks from the same
    source_document + section_header and collect any warning_text present.
    """
    warnings = []
    seen = set()

    for chunk in retrieved_chunks:
        meta = chunk["metadata"]
        # Warning on the retrieved chunk itself
        if meta.get("warning_text") and meta["warning_text"] not in seen:
            warnings.append({
                "source_document": meta["source_document"],
                "section_header": meta["section_header"],
                "warning_level": meta.get("warning_level", "warning"),
                "warning_text": meta["warning_text"],
            })
            seen.add(meta["warning_text"])

        # Sibling chunks from the same section may have warnings too
        # (looked up from ChromaDB metadata query)

    return warnings
```

### Anti-Patterns to Avoid
- **Normalizing BM25 scores to [0,1] before fusion:** RRF uses ranks, not scores. Normalizing adds complexity and can distort results. Use RRF specifically because it avoids score normalization.
- **Using ChromaDB's default L2 distance:** nomic-embed-text is optimized for cosine similarity. Always configure `hnsw.space = "cosine"` at collection creation time. This cannot be changed after creation.
- **Storing categories as boolean metadata fields:** ChromaDB >= 1.5.0 supports array metadata with `$contains`. Use `categories: ["medical", "first_aid"]` not `is_medical: true, is_first_aid: true`.
- **Calling the LLM when no chunks pass threshold:** The refusal path must short-circuit before any LLM call. Return a canned message directly.
- **Splitting retrieval and fusion across modules:** Keep vector search, BM25 search, and RRF fusion in one module (`retrieve.py`). They are tightly coupled and always run together.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Vector similarity search | Custom HNSW or brute-force search | ChromaDB with `hnsw.space=cosine` | HNSW is complex; ChromaDB handles indexing, persistence, metadata filtering |
| BM25 scoring | Custom TF-IDF / term frequency code | bm25s library | BM25 has non-trivial term weighting (k1, b parameters); bm25s handles tokenization and scoring correctly |
| Embedding generation | Custom model loading / inference | Ollama Python client (already in use) | Ollama handles model management, GPU allocation, batching |
| Metadata filtering on vectors | Custom post-filter on returned results | ChromaDB `where` parameter (pre-filter) | ChromaDB integrates filtering into the HNSW search; post-filtering wastes retrieval budget |

**Key insight:** The retrieval pipeline is an integration layer, not an algorithms layer. Each component (vector search, BM25, embeddings) has a mature library. The implementation work is wiring them together correctly with RRF fusion and threshold logic.

## Common Pitfalls

### Pitfall 1: ChromaDB Distance vs. Similarity Confusion
**What goes wrong:** ChromaDB returns cosine _distance_ (lower = more similar), but the threshold check needs cosine _similarity_ (higher = more similar). Developers compare the wrong direction and either accept irrelevant chunks or reject everything.
**Why it happens:** ChromaDB always returns distances, even when configured for cosine space. The API names the field "distances" not "similarities".
**How to avoid:** Always convert: `similarity = 1 - distance`. A distance of 0.3 means similarity of 0.7. Set threshold on the _similarity_ scale (e.g., 0.3 means chunks with similarity < 0.3 are rejected).
**Warning signs:** All queries return "insufficient context" (threshold inverted) or irrelevant results pass (threshold compared against distance instead of similarity).

### Pitfall 2: BM25 Category Filtering Mismatch
**What goes wrong:** ChromaDB pre-filters by category, but BM25 searches the full corpus. Results after RRF fusion include BM25-only results from wrong categories.
**Why it happens:** BM25 index is built from all chunks regardless of category. Category filtering only happens in the ChromaDB vector search path.
**How to avoid:** Apply category filtering to BM25 results _before_ RRF fusion. Maintain a mapping from chunk ID to categories, and filter BM25 results by checking this mapping.
**Warning signs:** Querying "medical" category returns results tagged only with "food" or "shelter".

### Pitfall 3: Over-fetching Destroys Small LLM Context Window
**What goes wrong:** Including too many chunks fills the small LLM's context window with marginally relevant content, causing the model to ignore the most relevant chunks or hallucinate.
**Why it happens:** Defaulting to 10+ chunks when the LLM only has 4K-8K context. Each chunk may be 500-1000 tokens.
**How to avoid:** Default to 5 chunks maximum. Monitor total token count of assembled prompt. Leave room for the LLM's response. The `n_results` parameter should be tunable.
**Warning signs:** LLM responses ignore clearly relevant retrieved content, or responses are truncated.

### Pitfall 4: BM25 Index Stale After Knowledge Base Update
**What goes wrong:** ChromaDB is updated with new chunks, but the in-memory BM25 index still contains only the old corpus. Hybrid search misses new content on the BM25 path.
**Why it happens:** BM25 index is built at startup; adding chunks to ChromaDB doesn't automatically rebuild it.
**How to avoid:** Document that BM25 index requires application restart after knowledge base updates. For v1, this is acceptable since content updates are rare (curated corpus). Provide a `rebuild_bm25_index()` function for future use.
**Warning signs:** New documents appear in vector search results but not in hybrid results.

### Pitfall 5: Forgetting search_query: Prefix on Query Embeddings
**What goes wrong:** Query embeddings are generated without the `search_query:` prefix, causing poor similarity scores against document embeddings that used `search_document:` prefix.
**Why it happens:** nomic-embed-text requires task-specific prefixes. Documents were embedded with `search_document:` in Phase 3, but the query embedding path forgets to add `search_query:`.
**How to avoid:** The `embed_query()` function in retrieve.py must always prepend `search_query: ` to the query text before calling Ollama. This is a different prefix than what embed.py uses for documents.
**Warning signs:** All similarity scores are uniformly low (0.1-0.3) even for obvious matches.

### Pitfall 6: Safety Warning Injection Creates Duplicates
**What goes wrong:** The same safety warning appears multiple times in the prompt because multiple retrieved chunks from the same section all carry the same warning_text metadata.
**Why it happens:** ChunkMetadata.warning_text is duplicated across all chunks from a section (by design in CHNK-04).
**How to avoid:** Deduplicate warnings by warning_text content before injecting into the prompt. Use a set to track seen warning texts.
**Warning signs:** Prompt contains the same WARNING block repeated 3-5 times, wasting context window.

## Code Examples

Verified patterns from official sources:

### ChromaDB Collection Setup with Cosine Distance
```python
# Source: https://docs.trychroma.com/docs/collections/configure
# Source: https://cookbook.chromadb.dev/core/collections/
import chromadb

client = chromadb.PersistentClient(path="./data/chroma")
collection = client.get_or_create_collection(
    name="survivalrag",
    configuration={
        "hnsw": {
            "space": "cosine",        # MUST be cosine, not default l2
            "ef_construction": 200,   # Higher = better recall during build
            "ef_search": 100,         # Higher = better recall during query
        }
    }
)
```

### Adding Pre-computed Embeddings with Array Metadata
```python
# Source: https://cookbook.chromadb.dev/core/collections/
# Source: https://cookbook.chromadb.dev/strategies/multi-category-filters/
collection.add(
    ids=["FM-21-76_003_002"],           # doc_section_chunk format
    documents=["Step 1: Find a water source..."],
    embeddings=[[0.1, 0.2, ...]],       # 768-dim from nomic-embed-text
    metadatas=[{
        "source_document": "FM-21-76",
        "source_title": "Survival",
        "section_header": "Water Procurement",
        "page_number": 45,
        "content_type": "procedure",
        "categories": ["water"],            # Array metadata (ChromaDB >= 1.5.0)
        "source_url": "https://...",
        "license": "US Government Work",
        "distribution_statement": "Distribution Statement A",
        "warning_level": None,
        "warning_text": None,
        "chunk_index": 2,
        "chunk_total": 5,
    }],
)
```

### Multi-Category Query with Pre-computed Embedding
```python
# Source: https://docs.trychroma.com/docs/querying-collections/metadata-filtering
# Source: https://cookbook.chromadb.dev/strategies/multi-category-filters/
results = collection.query(
    query_embeddings=[query_embedding],    # Pre-computed via Ollama
    n_results=10,
    where={
        "$or": [
            {"categories": {"$contains": "medical"}},
            {"categories": {"$contains": "first_aid"}},
        ]
    },
    include=["documents", "metadatas", "distances"],
)
# results["distances"][0] contains cosine distances (lower = more similar)
# Convert: similarity = 1 - distance
```

### BM25 Index Build and Query with bm25s
```python
# Source: https://pypi.org/project/bm25s/
import bm25s

# Build index at startup
corpus_texts = [chunk["text"] for chunk in all_chunks]
corpus_ids = [chunk["id"] for chunk in all_chunks]

retriever = bm25s.BM25()
corpus_tokens = bm25s.tokenize(corpus_texts)
retriever.index(corpus_tokens)

# Query
query_tokens = bm25s.tokenize(query)
results, scores = retriever.retrieve(query_tokens, k=20)
# results shape: (1, k) indices into corpus
# scores shape: (1, k) BM25 scores
```

### Cosine Distance to Similarity Conversion
```python
# Source: https://cookbook.chromadb.dev/faq/
# ChromaDB returns cosine DISTANCE, not similarity
# distance = 1 - similarity, so similarity = 1 - distance
similarities = [1 - d for d in results["distances"][0]]

# Threshold check
RELEVANCE_THRESHOLD = 0.3  # Configurable via env/config
passed = [
    (doc_id, sim, doc, meta)
    for doc_id, sim, doc, meta in zip(
        results["ids"][0], similarities,
        results["documents"][0], results["metadatas"][0]
    )
    if sim >= RELEVANCE_THRESHOLD
]
```

### Query Embedding with search_query: Prefix
```python
# Source: https://huggingface.co/nomic-ai/nomic-embed-text-v1.5
# Source: https://ollama.com/library/nomic-embed-text
import ollama

def embed_query(query: str, model: str = "nomic-embed-text") -> list[float]:
    """Embed a user query with the search_query: prefix.

    nomic-embed-text requires task-specific prefixes:
    - Documents: 'search_document: <text>'  (used in Phase 3)
    - Queries:   'search_query: <text>'     (used here)
    """
    response = ollama.embed(
        model=model,
        input=f"search_query: {query}",
    )
    return response["embeddings"][0]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| rank_bm25 (pure Python, slow) | bm25s (NumPy-backed, 10-1000x faster) | 2024-2025 | bm25s is actively maintained and dramatically faster; rank_bm25 last updated Feb 2022 |
| ChromaDB with boolean metadata fields | ChromaDB >= 1.5.0 with array metadata + `$contains` | Jan 2026 (ChromaDB 1.5.0) | Cleaner multi-category tagging; no more `is_medical: true` field explosion |
| ChromaDB Python-core | ChromaDB Rust-core backend | 2025 | 4x performance improvement for reads and writes; handles billion-scale embeddings |
| Vector-only retrieval | Hybrid BM25 + vector with RRF | 2024-2025 industry consensus | BM25 features in >50% of biomedical RAG studies; critical for exact medical terminology matching |
| Score normalization for fusion | Reciprocal Rank Fusion (rank-only) | Established pattern | RRF avoids the need to normalize incompatible score scales (BM25 vs cosine) |

**Deprecated/outdated:**
- rank_bm25 0.2.2: Last released Feb 2022, unmaintained. Use bm25s instead.
- ChromaDB `metadata={"hnsw:space": "cosine"}`: Old configuration syntax. Use `configuration={"hnsw": {"space": "cosine"}}` in current versions.
- ChromaDB boolean metadata for categories: Superseded by array metadata with `$contains` in v1.5.0+.

## Discretion Recommendations

### Refusal Message (Claude's Discretion)
**Recommendation:** Use a hard canned message, not LLM-generated.

Rationale: The entire point of the refusal path is to avoid calling the LLM when context is insufficient. An LLM-generated refusal defeats this purpose (costs inference time, could hallucinate). A canned message is instant, deterministic, and honest.

Suggested wording:
```
I don't have enough information in my knowledge base to answer that question reliably.
Try rephrasing your query or broadening the category filter.
```

### Maximum Chunks in Prompt (Claude's Discretion)
**Recommendation:** Default to 5 chunks, configurable via environment variable.

Rationale: With nomic-embed-text producing 768-dim embeddings and chunks averaging 500-800 tokens, 5 chunks consume roughly 2500-4000 tokens of context. This leaves adequate room for the system prompt, safety warnings, and LLM response within a 4K-8K context window (Llama 3.1 8B default). The value should be configurable (`SURVIVALRAG_MAX_CHUNKS=5`) for users with larger context windows.

### Medical Terminology Synonym Expansion for BM25 (Claude's Discretion)
**Recommendation:** Start without a synonym map. Add one later if Phase 6 evaluation reveals gaps.

Rationale: BM25 already handles exact keyword matches well (which is its primary value for medical terms like "tourniquet", "hemostasis", "CPR"). The embedding model (nomic-embed-text) handles semantic similarity for paraphrases ("stop bleeding" matching "hemorrhage control"). A synonym map adds maintenance burden and potential for incorrect expansions. The Phase 6 evaluation (EVAL-02: >85% recall on medical terminology queries) will reveal whether a map is needed.

### Cosine Similarity Threshold Value (Claude's Discretion)
**Recommendation:** Start with 0.25, tune against Phase 3 benchmark.

Rationale: Cosine similarity thresholds for nomic-embed-text typically fall in the 0.2-0.4 range for "relevant" matches on domain-specific content. Starting at 0.25 errs on the side of recall (returning more results) rather than precision. This is safer for a survival/medical reference tool -- it is better to return a marginally relevant chunk than to refuse a valid query. The threshold should be configurable (`SURVIVALRAG_RELEVANCE_THRESHOLD=0.25`) and tuned during Phase 6 evaluation.

## Open Questions

1. **BM25 tokenization strategy for medical abbreviations**
   - What we know: bm25s uses simple whitespace/punctuation tokenization by default. Medical abbreviations like "CPR", "IV", "ABC" are single tokens that match exactly.
   - What's unclear: Whether compound medical terms ("cardiopulmonary resuscitation") need special tokenization to match abbreviations. The source military manuals may use abbreviations inconsistently.
   - Recommendation: Use default tokenization for v1. If Phase 6 evaluation reveals abbreviation mismatches, add a lightweight abbreviation expansion step before BM25 tokenization.

2. **ChromaDB collection migration if schema changes**
   - What we know: ChromaDB HNSW configuration (distance space) cannot be changed after collection creation. Metadata schema is flexible.
   - What's unclear: If the collection needs recreation (e.g., switching from l2 to cosine), what is the migration path?
   - Recommendation: Always create the collection with `space: cosine` from the start. Document a `rebuild_collection()` utility that deletes and recreates the collection from JSONL source files.

3. **BM25 corpus size and startup time**
   - What we know: ~7,915 sections will produce chunks (likely 15,000-30,000 chunks after chunking). bm25s is fast (10-1000x over rank_bm25).
   - What's unclear: Exact startup time for building BM25 index over 15K-30K chunks on typical hardware.
   - Recommendation: Benchmark during implementation. If startup exceeds 5 seconds, consider serializing the BM25 index to disk with `retriever.save()` / `BM25.load()`.

## Sources

### Primary (HIGH confidence)
- [ChromaDB Official Docs - Query and Get](https://docs.trychroma.com/docs/querying-collections/query-and-get) - Query API, return format, include parameters
- [ChromaDB Official Docs - Configure Collections](https://docs.trychroma.com/docs/collections/configure) - HNSW configuration, distance metrics
- [ChromaDB Official Docs - Metadata Filtering](https://docs.trychroma.com/docs/querying-collections/metadata-filtering) - Operators ($in, $or, $and, $contains)
- [ChromaDB Cookbook - Collections](https://cookbook.chromadb.dev/core/collections/) - PersistentClient, add(), query() with pre-computed embeddings
- [ChromaDB Cookbook - Multi-Category Filters](https://cookbook.chromadb.dev/strategies/multi-category-filters/) - Array metadata, $contains for category filtering
- [chromadb PyPI](https://pypi.org/project/chromadb/) - Version 1.5.2 (Feb 27, 2026), Python >= 3.9
- [bm25s PyPI](https://pypi.org/project/bm25s/) - Version 0.3.0 (Feb 17, 2026), Python >= 3.8, MIT license
- [nomic-embed-text-v1.5 HuggingFace](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5) - 768-dim, 8192 context, task prefixes, Apache 2.0
- [nomic-embed-text Ollama](https://ollama.com/library/nomic-embed-text) - 274MB model, Ollama >= 0.1.26

### Secondary (MEDIUM confidence)
- [ChromaDB Cookbook FAQ](https://cookbook.chromadb.dev/faq/) - Distance vs similarity conversion (1 - distance)
- [ParadeDB - What is RRF](https://www.paradedb.com/learn/search-concepts/reciprocal-rank-fusion) - RRF formula, k=60 standard
- [Biomedical RAG Survey](https://arxiv.org/html/2505.01146v1) - BM25 in >50% of biomedical RAG systems, hybrid is standard
- [rank_bm25 GitHub](https://github.com/dorianbrown/rank_bm25) - Maintenance status, last commit 2022

### Tertiary (LOW confidence)
- Cosine similarity threshold range (0.2-0.4): Based on general RAG practitioner reports, not benchmarked against this specific corpus. Will need tuning in Phase 6.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries verified via official docs and PyPI; versions current as of March 2026
- Architecture: HIGH - Patterns derived from locked CONTEXT.md decisions + official API documentation
- Pitfalls: HIGH - Distance/similarity confusion is well-documented; BM25 filtering mismatch is a logical consequence of the architecture; context window limits are well-understood
- Discretion recommendations: MEDIUM - Threshold value and chunk count need empirical tuning in Phase 6

**Research date:** 2026-03-01
**Valid until:** 2026-04-01 (stable domain; ChromaDB and bm25s unlikely to break APIs within 30 days)
