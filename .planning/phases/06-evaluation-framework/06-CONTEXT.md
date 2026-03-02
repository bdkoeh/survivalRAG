# Phase 6: Evaluation Framework - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Quantitatively validate retrieval quality, citation faithfulness, hallucination refusal, and safety warning surfacing against a golden query dataset. Proves the system works, not just demos well. Does NOT include UI for viewing results or automated CI pipeline setup.

</domain>

<decisions>
## Implementation Decisions

### Golden Dataset Design
- Extend existing benchmark.py's auto-generation approach to bootstrap the golden dataset from real corpus chunks
- Each query entry contains: expected chunk IDs AND a list of key facts/keywords the answer must contain
- Queries tagged by category (medical, water, shelter, navigation, etc.) for per-domain evaluation drill-down
- Dataset must include realistic user queries per EVAL-06: lay language, typos, emotional phrasing (benchmark.py already generates lay_language, medical_terminology, and typo_variant types)

### Metric Thresholds & Scoring
- Graded scoring per query (numeric score, not binary pass/fail)
- Aggregate scores compared against roadmap thresholds: 85% retrieval recall, 90% citation faithfulness, 100% refusal
- On failure: report results AND highlight specific failing queries with details (expected vs actual)
- Non-zero exit code when aggregate thresholds not met (CI-friendly)
- Single-run results only -- no historical trend tracking

### Hallucination & Refusal Testing
- Broad categories of out-of-scope queries: completely off-topic (sports, politics), medical diagnosis requests, harmful/dangerous requests, queries outside the knowledge base (advanced surgery, exotic diseases)
- In-scope fabrication testing NOT in scope here -- citation faithfulness (EVAL-04) covers that separately
- Refusal test is pass/fail: out-of-scope query must be refused, period

### Runner & Reporting
- Output: terminal summary table (human-readable) + detailed JSON results file
- Assume environment is ready (Ollama running, models loaded) -- fail with clear error if not, same pattern as ask.py and generate.py

### Claude's Discretion
- Golden dataset file format (JSONL vs YAML)
- Threshold configurability (hardcoded vs env vars)
- Refusal verification method (canned message check vs any refusal signal)
- Number of out-of-scope refusal queries
- Invocation method (python -m pipeline.evaluate vs standalone script)
- Whether to support selectable test suites (--retrieval, --citation, etc.) or always run everything

</decisions>

<specifics>
## Specific Ideas

No specific requirements -- open to standard approaches. The existing benchmark.py with its query type distribution (lay_language, medical_terminology, typo_variant) and Recall@5 evaluation provides a strong foundation to extend.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pipeline/benchmark.py`: Auto-generates query-document pairs from corpus chunks via LLM, evaluates Recall@5 with cosine similarity. Has query type distribution (lay_language, medical_terminology, typo_variant) and configurable thresholds.
- `pipeline/generate.py`: `answer()` and `answer_stream()` full-pipeline entry points (query -> retrieve -> prompt -> generate -> verify). `verify_citations()` with fuzzy matching via SequenceMatcher. `extract_citations()` for parsing citations from response text.
- `pipeline/retrieve.py`: Hybrid retrieval with BM25 + vector search + RRF fusion. Cosine similarity threshold filtering. Category pre-filtering support.
- `pipeline/prompt.py`: `REFUSAL_MESSAGE` constant for canned refusal. `collect_safety_warnings()` for extracting warnings from chunk metadata.

### Established Patterns
- Module-level state with `init()` function called at startup (retrieve.py, generate.py, embed.py all follow this)
- Environment variable configuration with sensible defaults (SURVIVALRAG_MODEL, SURVIVALRAG_RELEVANCE_THRESHOLD, etc.)
- Locked safe parameters for medical content (temperature 0.2, tight top-p/top-k) -- not user-configurable

### Integration Points
- `gen.answer(query_text, mode, category)` is the full pipeline entry point -- eval suite calls this
- `retrieve.retrieve(query_text, category, max_results)` for testing retrieval independently
- `gen.verify_citations(response_text, chunks)` for testing citation faithfulness independently
- ChromaDB at `./data/chroma` for chunk storage
- `processed/benchmark/` directory already used for benchmark output

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope.

</deferred>

---

*Phase: 06-evaluation-framework*
*Context gathered: 2026-03-02*
