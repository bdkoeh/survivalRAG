# Phase 4: Retrieval Pipeline - Context

**Gathered:** 2026-03-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can query the embedded knowledge base and get relevant, category-filtered results via vector similarity and hybrid search. When no chunks meet the relevance threshold, the system returns "insufficient context" without calling the LLM. Retrieved context is assembled into a structured prompt with source metadata for downstream citation.

Response generation, streaming, citation formatting, and UI are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Relevance threshold & refusal
- Fixed cosine similarity score cutoff -- a single threshold value determines whether chunks are relevant
- Threshold is system-level configuration only (env var or config file) -- not adjustable per query
- When no chunks pass the threshold, the system refuses without calling the LLM

### Hybrid search fusion
- Always-on hybrid search: every query runs both BM25 keyword and vector similarity
- Reciprocal Rank Fusion (RRF) combines the two ranked lists -- no need to normalize different score scales
- BM25 index is built in-memory at application startup from chunk text, rebuilt on each restart

### Category filtering behavior
- Strict pre-filter: when a category is specified, only chunks tagged with that category are searched
- Multi-category filtering with OR logic: user can pass multiple categories and get chunks matching any of them
- Default when no filter specified: search all categories
- Categories are internal filtering metadata -- not surfaced in retrieval results (downstream phases handle display)

### Prompt assembly & context packing
- Retrieved chunks ordered by relevance score, highest first (primacy bias benefit for small LLMs)
- Each chunk in the prompt includes: document name, section heading, page number
- Safety warnings from chunk metadata are always injected into the prompt, even if the warning chunk itself wasn't retrieved -- safety-first
- Prompt assembly lives in a dedicated module (pipeline/prompt.py), separate from retrieval logic

### Claude's Discretion
- Refusal message wording and delivery mechanism (hard canned message vs LLM-generated)
- Maximum number of chunks to include in prompt context
- Whether medical terminology needs a synonym/abbreviation expansion map for BM25, or if the embedding model handles it sufficiently
- Exact cosine similarity threshold value (to be tuned against the benchmark from Phase 3)

</decisions>

<specifics>
## Specific Ideas

- Safety warnings must always surface with related procedures -- this is the core safety-first principle of the project
- The system should feel like querying a well-indexed field manual, not a chatbot that sometimes gets things right
- Categories like "medical" and "first_aid" often overlap -- OR logic for multi-category handles this naturally

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pipeline/models.py`: ContentType enum, CategoryLiteral type, SectionMetadata with full provenance fields -- chunk metadata schema will extend these
- `pipeline/embed.py` (Phase 3): Ollama nomic-embed-text embedding wrapper with batch safety and search_query:/search_document: prefix convention
- `pipeline/chunk.py` (Phase 3): ChunkRecord and ChunkMetadata models with warning_level and warning_text fields for safety co-location

### Established Patterns
- Pydantic models for all data schemas (models.py pattern)
- Ollama as the inference backend (already in requirements.txt)
- YAML front matter on processed section files for metadata
- Pipeline modules are standalone Python files in pipeline/ directory

### Integration Points
- Input: JSONL chunk files with embeddings from Phase 3 (pipeline/chunk.py output)
- Vector store: ChromaDB (specified in roadmap success criteria, not yet in requirements.txt)
- Output: Structured prompt consumed by Phase 5 (Response Generation)
- Embedding queries: Ollama nomic-embed-text via pipeline/embed.py

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 04-retrieval-pipeline*
*Context gathered: 2026-03-01*
