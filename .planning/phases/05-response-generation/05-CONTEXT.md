# Phase 5: Response Generation - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning

<domain>
## Phase Boundary

The system generates safety-first, source-cited, field-manual-style responses using a local LLM (Ollama). It refuses when context is insufficient, never hallucinate medical procedures, streams token-by-token, and verifies citations post-generation. Three response modes: full (local), compact (mobile/low-bandwidth), and ultra-short (~200 chars for mesh radio).

</domain>

<decisions>
## Implementation Decisions

### LLM model & configuration
- Model is configurable via SURVIVALRAG_MODEL env var -- supports any Ollama-compatible model
- Temperature and generation parameters are locked to safe defaults for medical/survival content (not user-configurable) -- reduces hallucination risk
- Startup validation checks that the configured model is available in Ollama before accepting queries -- fails fast with a clear "run ollama pull <model>" message

### Streaming contract
- Python generator (yield tokens) for streaming -- CLI prints directly, web UI wraps in SSE
- Both `generate_stream()` (generator) and `generate()` (full response) methods provided
- Three response modes: full, compact, ultra (~200 chars for mesh radio)
- Each mode has its own system prompt instructing the LLM on length and style -- single LLM call per query, no post-processing summarization

### Citation verification
- Post-generation verification (after full response complete, not during streaming)
- Fuzzy matching: citation is valid if it's a substring of or closely matches the source_document metadata field -- handles abbreviations and partial titles
- On verification failure: keep the response but append a visible warning ("Note: Some citations could not be verified against source documents.")
- Verification results (pass/fail, which citations matched) both logged AND returned as structured data in the response dict for Phase 6 evaluation framework

### Response formatting
- System prompt instructs field-manual style + light post-processing to catch when small LLMs ignore formatting instructions
- Safety warnings rendered as bold prefix block at top of response, before answer content -- unmissable, field-manual style
- Ultra-short mode (~200 chars): strip citations (no room), keep critical safety warnings -- safety first even at minimum length

### Claude's Discretion
- Default Ollama model when no env var is set
- Exact safe temperature/parameter values
- Citation format in user-facing responses (inline parenthetical vs footnote-style)
- Light post-processor implementation approach
- Compact mode length target

</decisions>

<specifics>
## Specific Ideas

- Ultra mode example style: "Stop bleeding: direct pressure 15min. WARNING: Do NOT remove embedded objects."
- Warning block at top should be unmissable -- field-manual convention
- Model validation message should tell users exactly what command to run (e.g., "run `ollama pull llama3.2:3b`")

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pipeline/prompt.py`: SYSTEM_PROMPT, assemble_prompt(), build_response(), query(), REFUSAL_MESSAGE -- the entire Phase 4 -> Phase 5 contract is built
- `pipeline/retrieve.py`: init(), retrieve() -- hybrid retrieval engine with BM25 + vector + RRF fusion
- `pipeline/embed.py`: embed_query() -- Ollama embedding client (pattern for Ollama HTTP calls)
- `pipeline/_chromadb_compat.py`: Python 3.14 compatibility shim (may need similar for generation deps)

### Established Patterns
- Ollama HTTP API usage via embed.py (requests-based, same pattern for /api/generate)
- Module-level state with init() function (retrieve.py pattern)
- Environment variable configuration (SURVIVALRAG_* prefix established)
- Structured result dicts as inter-module contracts (build_response returns {status, message, prompt, chunks, warnings})

### Integration Points
- `prompt.query()` is the entry point -- returns {status, prompt, chunks, warnings}
- Response module will be called by Phase 7 CLI and web UI
- Phase 6 evaluation framework will consume verification_result from response dict
- `pipeline/__init__.py` exists for package-level imports

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 05-response-generation*
*Context gathered: 2026-03-02*
