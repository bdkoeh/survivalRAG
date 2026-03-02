---
phase: 04-retrieval-pipeline
plan: 01
subsystem: retrieval
tags: [chromadb, bm25s, rrf, cosine-similarity, hybrid-search, vector-search]

# Dependency graph
requires:
  - phase: 03-chunking-embedding
    provides: JSONL chunk files with pre-computed 768-dim nomic-embed-text embeddings and metadata
provides:
  - ChromaDB ingestion pipeline for loading JSONL chunks with array metadata
  - Hybrid retrieval engine with vector search, BM25, and RRF fusion
  - Category pre-filtering with $contains and $or logic
  - Cosine similarity threshold filtering with configurable refusal path
affects: [05-response-generation, 06-evaluation, 04-02]

# Tech tracking
tech-stack:
  added: [chromadb>=1.5.0, bm25s>=0.3.0]
  patterns: [hybrid-search-always-on, rrf-fusion-k60, threshold-refusal, category-array-metadata]

key-files:
  created:
    - pipeline/ingest.py
    - pipeline/retrieve.py
    - pipeline/_chromadb_compat.py
  modified:
    - requirements.txt

key-decisions:
  - "Python 3.14 pydantic v1 compat shim created for ChromaDB -- patches type inference to avoid ConfigError"
  - "Cosine similarity threshold set to 0.25 (configurable via SURVIVALRAG_RELEVANCE_THRESHOLD env var)"
  - "Default max results set to 5 chunks (configurable via SURVIVALRAG_MAX_CHUNKS env var)"
  - "BM25 results category-filtered post-hoc BEFORE RRF fusion to prevent wrong-category leakage"
  - "BM25-only results excluded from final output since they lack ChromaDB metadata for response"

patterns-established:
  - "Hybrid search pattern: every query runs both BM25 keyword and vector similarity search, fused via RRF"
  - "Category filtering pattern: $contains for single category, $or array for multi-category, None for all"
  - "Threshold refusal pattern: empty list return triggers caller refusal without LLM call"
  - "ChromaDB compat pattern: import pipeline._chromadb_compat before chromadb on Python 3.14+"

requirements-completed: [RETR-01, RETR-02, RETR-03, RETR-04]

# Metrics
duration: 5min
completed: 2026-03-02
---

# Phase 4 Plan 1: Ingestion & Retrieval Summary

**ChromaDB ingestion pipeline and hybrid retrieval engine with always-on BM25 + vector search, RRF fusion (k=60), category pre-filtering via $contains, and cosine similarity threshold refusal**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-02T00:58:03Z
- **Completed:** 2026-03-02T01:03:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- ChromaDB ingestion module loads Phase 3 JSONL files with pre-computed embeddings and array metadata
- Hybrid retrieval engine runs BM25 + vector search on every query with RRF fusion
- Category pre-filtering uses ChromaDB $contains operator with $or logic for multi-category
- Cosine similarity threshold filtering returns empty list for refusal path (no LLM call)
- BM25 results filtered by category before RRF fusion to prevent wrong-category leakage

## Task Commits

Each task was committed atomically:

1. **Task 1: Create ChromaDB ingestion module and update requirements** - `ed4beb6` (feat)
2. **Task 2: Create hybrid retrieval module with RRF fusion and threshold filtering** - `a15d7e0` (feat)

## Files Created/Modified
- `pipeline/ingest.py` - ChromaDB ingestion: get_collection(), load_jsonl(), chunk_to_chroma_id(), chunk_metadata_to_dict(), ingest_chunks(), ingest_directory(), get_all_chunks_for_bm25()
- `pipeline/retrieve.py` - Hybrid retrieval: init(), build_bm25_index(), retrieve(), reciprocal_rank_fusion(), _vector_search(), _bm25_search(), _build_category_filter()
- `pipeline/_chromadb_compat.py` - Python 3.14 compatibility shim patching pydantic v1 type inference for ChromaDB
- `requirements.txt` - Added chromadb>=1.5.0 and bm25s>=0.3.0

## Decisions Made
- Created `pipeline/_chromadb_compat.py` shim for Python 3.14 + pydantic v1 compatibility -- ChromaDB 1.5.2 uses pydantic v1 BaseSettings which fails to infer types for validator-annotated fields on Python 3.14. The shim patches `_set_default_and_type` to fall back to `Any` instead of raising ConfigError.
- Cosine similarity threshold defaulted to 0.25 (conservative, favoring recall over precision for safety-critical survival/medical content). Configurable via `SURVIVALRAG_RELEVANCE_THRESHOLD` env var.
- Max results defaulted to 5 chunks to fit within small LLM context windows (4K-8K). Configurable via `SURVIVALRAG_MAX_CHUNKS` env var.
- BM25-only results (those without vector search metadata) are excluded from final RRF output since they lack the text and metadata needed for prompt assembly.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created Python 3.14 compatibility shim for ChromaDB**
- **Found during:** Task 1 (ChromaDB ingestion module)
- **Issue:** ChromaDB 1.5.2 uses pydantic v1 BaseSettings which crashes on Python 3.14 with `ConfigError: unable to infer type for attribute "chroma_server_nofile"`. The project venv runs Python 3.14.3.
- **Fix:** Created `pipeline/_chromadb_compat.py` that monkey-patches pydantic v1's `ModelField._set_default_and_type` to fall back to `Any` type inference instead of raising. Must be imported before chromadb.
- **Files modified:** pipeline/_chromadb_compat.py (created), pipeline/ingest.py (import added), pipeline/retrieve.py (import added)
- **Verification:** All module imports succeed, ChromaDB PersistentClient creates collections, full ingestion and retrieval tests pass
- **Committed in:** ed4beb6 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential fix for Python 3.14 compatibility. No scope creep. The shim is minimal (35 lines) and only activates on Python >= 3.14.

## Issues Encountered
- ChromaDB 1.5.2 is the latest version and has no Python 3.14 support yet. The pydantic v1 compatibility layer in chromadb/config.py fails because pydantic v1 cannot infer types for fields with validators defined before the field on Python 3.14+. The monkey-patch approach was chosen over downgrading Python since the rest of the project runs on 3.14.

## User Setup Required
None - no external service configuration required. ChromaDB runs as an embedded database with local persistent storage.

## Next Phase Readiness
- Ingestion and retrieval modules ready for Plan 04-02 (prompt assembly, safety warning injection)
- Full end-to-end retrieval requires Ollama running with nomic-embed-text for embed_query() calls
- BM25 index built in-memory at startup -- requires application restart after knowledge base changes

## Self-Check: PASSED

All files verified present. All commits verified in git log.

---
*Phase: 04-retrieval-pipeline*
*Completed: 2026-03-02*
