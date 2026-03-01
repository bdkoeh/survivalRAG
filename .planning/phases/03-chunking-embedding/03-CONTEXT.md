# Phase 3: Chunking & Embedding - Context

**Gathered:** 2026-02-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Processed section files (Markdown with YAML front matter from Phase 2) are chunked with content-type awareness and embedded with a validated model. Output is JSONL files containing chunked text, embedding vectors, and full metadata -- the ready-to-query knowledge base that Phase 4 loads into ChromaDB.

</domain>

<decisions>
## Implementation Decisions

### Chunking strategy
- Hybrid splitting: prefer semantic boundaries (paragraph breaks, sub-headings) but enforce a max chunk size -- if content exceeds the limit, split at sentence boundaries
- Small sections that fit within the max size stay as single chunks
- Short chunks are kept as-is (no merging with neighbors) -- some short sections like safety notes and definitions are self-contained
- For `procedure` sections: detect numbered steps (1., 2., 3. or a., b., c.) and chunk at step boundaries -- a multi-step procedure becomes multiple chunks, each a complete step
- For `reference_table` sections: keep as single chunks with headers preserved (per CHNK-02)

### Safety warning co-location
- Full warning text + warning level (warning/caution/note) stored as metadata on every related chunk
- If a section has multiple warnings (e.g., a WARNING and a CAUTION), all warnings are attached to all chunks in that section
- All warnings on all chunks in the same section -- simple rule, nothing missed

### Embedding model benchmarking
- Benchmark nomic-embed-text only (primary candidate, already in deployment spec for Phase 8)
- Run via Ollama (already a project dependency from Phase 2)
- Auto-generate 50+ benchmark query-document pairs from actual Tier 1 content (take a chunk, generate a realistic query it should answer -- include lay language, medical terminology, and typo variants)
- Pass threshold: Recall@5 >= 85% (matches Phase 6 retrieval recall target)

### Storage format
- Output as intermediate JSONL files in `processed/chunks/` -- one JSONL file per source document
- Each line contains: chunked text, pre-computed embedding vector, and full metadata
- Follows the pipeline progression: `sources/` -> `processed/sections/` -> `processed/chunks/`
- Phase 4 loads JSONL into ChromaDB -- phases stay decoupled and intermediate state is debuggable

### Claude's Discretion
- Optimal chunk size (tokens) based on best practices and actual content distribution in Tier 1 documents
- How to determine "related chunks" scope for safety warning duplication (same-section vs proximity-based)
- Whether standalone safety warning sections also become their own retrievable chunks (in addition to existing as metadata)
- Failure path if nomic-embed-text doesn't pass the benchmark (auto-try alternatives or stop)
- Short chunk minimum threshold (if any)
- Overlap strategy between consecutive chunks (if any)

</decisions>

<specifics>
## Specific Ideas

No specific requirements -- open to standard approaches

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pipeline/models.py`: `ContentType` enum (procedure, reference_table, safety_warning, general), `WarningLevel` enum, `SectionMetadata` with warning_level/warning_text fields -- chunk metadata can extend this
- `pipeline/clean.py`: Text cleaning already handles whitespace normalization and preserves safety blocks -- chunker can reuse normalization
- `pipeline/extract.py` + `pipeline/split.py`: Section splitting logic and Docling integration patterns
- `requirements.txt`: Already has `ollama>=0.6.1` and `pydantic>=2.0` -- embedding via Ollama and chunk models via Pydantic follow existing patterns

### Established Patterns
- Pydantic models for all data schemas (section metadata, classification results)
- YAML front matter on Markdown files for metadata
- Ollama as the local model runtime (used for classification in Phase 2, will use for embeddings)
- Per-document output structure (`processed/sections/{doc-id}/`)
- Pipeline modules as separate Python files in `pipeline/` with an orchestrator script

### Integration Points
- **Input**: `processed/sections/{doc-id}/*.md` -- Markdown files with YAML front matter (content_type, categories, warning_level, warning_text, provenance)
- **Output**: `processed/chunks/{doc-id}.jsonl` -- one JSONL file per source document
- **Embedding API**: Ollama embeddings endpoint (consistent with existing Ollama usage)
- **Downstream**: Phase 4 reads JSONL files and loads into ChromaDB

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 03-chunking-embedding*
*Context gathered: 2026-02-28*
