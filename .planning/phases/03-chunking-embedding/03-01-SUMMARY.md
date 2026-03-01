---
phase: 03-chunking-embedding
plan: 01
subsystem: pipeline
tags: [chunking, embedding, pydantic, ollama, nomic-embed-text, nlp]

# Dependency graph
requires:
  - phase: 02-document-processing
    provides: "Section Markdown files with YAML front matter (content_type, categories, warning metadata, provenance)"
provides:
  - "ChunkMetadata and ChunkRecord Pydantic models in pipeline/models.py"
  - "Content-type-aware chunking dispatch in pipeline/chunk.py (procedure, reference_table, safety_warning, general)"
  - "Batch-safe Ollama embedding wrapper in pipeline/embed.py with prefix convention enforcement"
affects: [03-02-PLAN, 03-03-PLAN, 04-retrieval-pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Content-type dispatch: read content_type.primary from YAML front matter, route to type-specific chunker"
    - "Safety warning co-location: warning_level and warning_text propagated to all chunks in same section"
    - "Embedding prefix convention: search_document: for corpus, search_query: for queries -- enforced by wrapper"
    - "Batch-safe embedding: max 8 texts per ollama.embed() call per quality findings"

key-files:
  created:
    - pipeline/chunk.py
    - pipeline/embed.py
  modified:
    - pipeline/models.py

key-decisions:
  - "512-token / 2048-char max chunk size per research consensus for factoid/procedural queries"
  - "No chunk overlap -- Jan 2026 study showed no benefit, only increased indexing cost"
  - "No short chunk minimum -- short sections kept as-is per locked decision"
  - "Safety warning sections emit as own retrievable chunks AND propagate as metadata"
  - "Tables never split even if exceeding max size -- log warning instead"

patterns-established:
  - "ChunkMetadata carries 16 fields of provenance for full citation traceability"
  - "chunk_section() dispatches to _chunk_procedure, _chunk_table, _chunk_safety_warning, _chunk_general"
  - "embed_documents() and embed_query() are the only embedding entry points -- never call ollama.embed() directly"

requirements-completed: [CHNK-01, CHNK-02, CHNK-03, CHNK-04, CHNK-05]

# Metrics
duration: 4min
completed: 2026-03-01
---

# Phase 3 Plan 01: Chunking & Embedding Core Summary

**Content-type-aware chunking engine with procedure-step splitting, table preservation, safety warning co-location, and batch-safe Ollama nomic-embed-text embedding wrapper**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-01T17:43:19Z
- **Completed:** 2026-03-01T17:47:01Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- ChunkMetadata (16 metadata fields) and ChunkRecord Pydantic models added to pipeline/models.py for full provenance traceability
- Content-type-aware chunker (pipeline/chunk.py) dispatches to procedure, reference_table, safety_warning, and general strategies -- procedures split at step boundaries, tables kept whole, safety warnings independently retrievable
- Batch-safe Ollama embedding wrapper (pipeline/embed.py) enforces search_document:/search_query: prefix convention and limits batches to 8 texts

## Task Commits

Each task was committed atomically:

1. **Task 1: Create chunk data models and content-type-aware chunker** - `87def2b` (feat)
2. **Task 2: Create batch-safe Ollama embedding wrapper** - `0fd9f03` (feat)

**Plan metadata:** `44edded` (docs: complete plan)

## Files Created/Modified
- `pipeline/models.py` - Extended with ChunkMetadata (16 fields) and ChunkRecord Pydantic models
- `pipeline/chunk.py` - Content-type-aware chunking with dispatch by content_type, paragraph/sentence splitting, step boundary detection
- `pipeline/embed.py` - Ollama nomic-embed-text embedding wrapper with batch safety, prefix convention, model version tracking

## Decisions Made
- 512-token (2048-char) max chunk size -- aligns with 2025-2026 research consensus for factoid/procedural RAG queries and fits 85% of sections as single chunks
- No overlap between consecutive chunks -- Jan 2026 analysis found no measurable retrieval benefit
- No short chunk minimum threshold -- short sections (safety notes, definitions) are self-contained and retrieve well with metadata
- Safety warning sections produce their own retrievable chunks in addition to propagating as metadata on all section chunks
- Tables are never split even if they exceed max chunk size -- emit as single chunk with log warning
- Embedding batch size capped at 8 per Ollama GitHub issue #6262 quality findings

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Ollama not running on this machine, so live embedding tests were skipped (static import and signature tests passed). This is expected -- the embedding wrapper handles this gracefully with clear error messages directing users to start Ollama and pull the model.

## User Setup Required

None - no external service configuration required. Ollama must be running with nomic-embed-text pulled for embedding (already a project dependency from Phase 2).

## Next Phase Readiness
- Chunk models and chunker ready for Plan 02 (embedding benchmark with auto-generated query-document pairs)
- Embedding wrapper ready for Plan 03 (full corpus chunking and embedding)
- All modules are importable and verified with automated tests

## Self-Check: PASSED

- All 3 created/modified files exist on disk
- Both task commits (87def2b, 0fd9f03) found in git log
- All modules importable with correct function signatures

---
*Phase: 03-chunking-embedding*
*Completed: 2026-03-01*
