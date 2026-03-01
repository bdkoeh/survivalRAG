# Phase 3: Chunking & Embedding - Research

**Researched:** 2026-02-28
**Domain:** Content-type-aware text chunking and vector embedding for survival/medical RAG
**Confidence:** HIGH

## Summary

Phase 3 takes the 2,207 section Markdown files (with YAML front matter) produced by Phase 2 and converts them into chunked, embedded JSONL files ready for Phase 4 to load into ChromaDB. The pipeline reads each section, applies content-type-aware splitting (procedure step boundaries, tables kept whole, safety warnings co-located), generates 768-dimensional embeddings via Ollama's nomic-embed-text model, and writes per-document JSONL files to `processed/chunks/`.

The corpus is manageable: ~3.9 MB of section files, median section ~1,250 bytes (~210 tokens of content after stripping YAML front matter). Approximately 85% of sections already fit within a single 512-token chunk, meaning the chunker's primary job is handling the ~15% of larger sections through content-type-aware splitting. The embedding step is straightforward -- Ollama's Python library provides a batch `embed()` API, and nomic-embed-text is already in the deployment spec.

The critical risk area is the embedding benchmark: CHNK-06 requires 50+ query-document pairs with Recall@5 >= 85% before proceeding. This must be automated since manually crafting 50+ pairs for medical/survival terminology is time-consuming and error-prone. Auto-generating pairs from actual corpus content (using Ollama's LLM to create realistic queries per chunk) is the established approach.

**Primary recommendation:** Use a simple Python chunker (no external chunking library needed) that reads section front matter to determine content_type and applies type-specific splitting rules. Embed via `ollama.embed()` with `search_document:` prefix on chunks and `search_query:` prefix on benchmark queries. Output JSONL with pre-computed 768-dim vectors.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Hybrid splitting: prefer semantic boundaries (paragraph breaks, sub-headings) but enforce a max chunk size -- if content exceeds the limit, split at sentence boundaries
- Small sections that fit within the max size stay as single chunks
- Short chunks are kept as-is (no merging with neighbors) -- some short sections like safety notes and definitions are self-contained
- For `procedure` sections: detect numbered steps (1., 2., 3. or a., b., c.) and chunk at step boundaries -- a multi-step procedure becomes multiple chunks, each a complete step
- For `reference_table` sections: keep as single chunks with headers preserved (per CHNK-02)
- Full warning text + warning level (warning/caution/note) stored as metadata on every related chunk
- If a section has multiple warnings (e.g., a WARNING and a CAUTION), all warnings are attached to all chunks in that section
- All warnings on all chunks in the same section -- simple rule, nothing missed
- Benchmark nomic-embed-text only (primary candidate, already in deployment spec for Phase 8)
- Run via Ollama (already a project dependency from Phase 2)
- Auto-generate 50+ benchmark query-document pairs from actual Tier 1 content (take a chunk, generate a realistic query it should answer -- include lay language, medical terminology, and typo variants)
- Pass threshold: Recall@5 >= 85% (matches Phase 6 retrieval recall target)
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

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CHNK-01 | Procedures are chunked at procedure boundaries -- never split mid-step | Chunker reads `content_type.primary == "procedure"` from YAML front matter, detects numbered step patterns (1., 2., a., b.), splits at step boundaries. Steps exceeding max chunk size get sentence-boundary fallback. |
| CHNK-02 | Reference tables are kept as single chunks with headers preserved | Chunker reads `content_type.primary == "reference_table"`, emits entire section as one chunk. Tables in corpus are well under 2K token limit (verified from section size distribution). |
| CHNK-03 | Safety warnings are never stripped, summarized, or separated from their associated procedure | Chunker reads `warning_level` and `warning_text` from YAML front matter and carries them forward to every chunk's metadata. Warning text is never modified. |
| CHNK-04 | Safety warnings are duplicated as metadata on related chunks so they surface even when the warning chunk itself is not retrieved | All chunks from the same section inherit the section's `warning_level` and `warning_text` fields. Same-section scope is the locked decision. |
| CHNK-05 | Every chunk has metadata: source_document, page_number, section_header, content_type, category, source_url, license, distribution_statement, verification_date | Metadata fields mapped from existing `SectionMetadata` model. Chunk Pydantic model extends with chunk-specific fields (chunk_index, chunk_total, embedding_model). |
| CHNK-06 | Embedding model is benchmarked against 50+ domain-specific query-document pairs before full corpus processing | Auto-generate pairs using Ollama LLM from sampled chunks. Evaluate Recall@5 with cosine similarity. Pass threshold: >= 85%. |
| CHNK-07 | All chunks are embedded using the same model version, recorded in metadata | `embedding_model` and `embedding_model_version` fields on every chunk JSONL record. Version queried from Ollama API at start of run. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| ollama (Python) | >= 0.6.1 | Embedding generation via `ollama.embed()` | Already a project dependency, used for classification in Phase 2. Provides batch embed API. |
| nomic-embed-text | v1.5 (Ollama) | Embedding model, 768-dim, 2K context window via Ollama | Locked decision from CONTEXT.md. In deployment spec for Phase 8. Outperforms OpenAI ada-002 on MTEB. |
| pydantic | >= 2.0 | Chunk metadata schema validation | Already a project dependency. Established pattern from `pipeline/models.py`. |
| pyyaml | >= 6.0 | Read YAML front matter from section files | Already a project dependency. Used throughout pipeline. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| numpy | any | Cosine similarity calculation for benchmark | Only needed for embedding benchmark evaluation. Likely already installed (pandas dependency). |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom Python chunker | LangChain RecursiveCharacterTextSplitter | LangChain adds a heavy dependency for simple logic. Our content-type-aware splitting requires custom rules anyway. Custom is correct here. |
| Character-count chunking | Token-count chunking with BERT tokenizer | Token counting is more accurate but requires `tokenizers` library (~10MB). Character-based with 4:1 ratio is sufficient given our generous margins. |
| numpy cosine similarity | scipy.spatial.distance.cosine | numpy is lighter; we only need simple dot product on L2-normalized vectors (which Ollama returns). |

**Installation:**
```bash
# No new dependencies needed -- all already in requirements.txt
# ollama>=0.6.1, pydantic>=2.0, pyyaml>=6.0
# numpy is already installed as a transitive dependency of pandas (from docling)
```

## Architecture Patterns

### Recommended Project Structure
```
pipeline/
├── models.py          # EXTEND: Add ChunkMetadata, ChunkRecord Pydantic models
├── chunk.py           # NEW: Content-type-aware chunking logic
├── embed.py           # NEW: Ollama embedding wrapper with batch support
├── chunk_all.py       # NEW: Orchestrator script (reads sections/, writes chunks/)
├── benchmark.py       # NEW: Embedding benchmark (auto-generate pairs, evaluate Recall@5)
├── extract.py         # (existing)
├── clean.py           # (existing)
├── split.py           # (existing)
├── writer.py          # (existing)
└── extract_all.py     # (existing)

processed/
├── sections/{doc-id}/*.md   # INPUT: Phase 2 output
├── chunks/{doc-id}.jsonl    # OUTPUT: One JSONL per source document
└── benchmark/               # Benchmark results and query-document pairs
    ├── pairs.jsonl           # Auto-generated query-document pairs
    └── results.json          # Benchmark scores
```

### Pattern 1: Content-Type-Aware Chunking Dispatch
**What:** Read `content_type.primary` from section YAML front matter and dispatch to type-specific chunking functions.
**When to use:** Every section file processed.
**Example:**
```python
# Source: Project CONTEXT.md locked decisions
def chunk_section(content: str, metadata: dict) -> list[dict]:
    """Dispatch to content-type-specific chunker."""
    content_type = metadata.get("content_type", {}).get("primary", "general")

    if content_type == "procedure":
        return chunk_procedure(content, metadata)
    elif content_type == "reference_table":
        return chunk_table(content, metadata)
    elif content_type == "safety_warning":
        return chunk_safety_warning(content, metadata)
    else:  # general
        return chunk_general(content, metadata)
```

### Pattern 2: Nomic-Embed-Text Prefix Convention
**What:** nomic-embed-text requires task-type prefixes: `search_document:` for corpus text, `search_query:` for user queries.
**When to use:** Every embedding call. This is critical -- omitting the prefix degrades retrieval quality.
**Example:**
```python
# Source: https://huggingface.co/nomic-ai/nomic-embed-text-v1.5
import ollama

def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed document chunks with the required prefix."""
    prefixed = [f"search_document: {t}" for t in texts]
    response = ollama.embed(model="nomic-embed-text", input=prefixed)
    return response["embeddings"]

def embed_query(query: str) -> list[float]:
    """Embed a search query with the required prefix."""
    response = ollama.embed(model="nomic-embed-text", input=f"search_query: {query}")
    return response["embeddings"][0]
```

### Pattern 3: JSONL Output with Embedded Vectors
**What:** Each JSONL line contains the chunk text, its 768-dim embedding vector, and full metadata.
**When to use:** Writing chunk output files.
**Example:**
```python
import json

def write_chunk_jsonl(output_path: str, chunks: list[dict]):
    """Write chunks with embeddings to JSONL file."""
    with open(output_path, "w") as f:
        for chunk in chunks:
            # chunk = {
            #   "text": "...",
            #   "embedding": [0.123, -0.456, ...],  # 768 floats
            #   "metadata": {
            #       "source_document": "FM-21-76",
            #       "page_number": 42,
            #       "section_header": "Water Procurement",
            #       "content_type": "procedure",
            #       "category": ["water"],
            #       "source_url": "https://...",
            #       "license": "US Government Work - Public Domain",
            #       "distribution_statement": "Distribution Statement A: ...",
            #       "verification_date": "2026-02-28",
            #       "chunk_index": 0,
            #       "chunk_total": 3,
            #       "embedding_model": "nomic-embed-text",
            #       "embedding_model_version": "v1.5",
            #       "warning_level": "warning",
            #       "warning_text": "WARNING: Do not drink untreated water..."
            #   }
            # }
            f.write(json.dumps(chunk) + "\n")
```

### Pattern 4: Benchmark Auto-Generation
**What:** Sample chunks from the corpus, use Ollama LLM to generate realistic queries per chunk, then evaluate Recall@5.
**When to use:** Before full corpus embedding (CHNK-06).
**Example:**
```python
import ollama
import random

def generate_query_for_chunk(chunk_text: str) -> str:
    """Use LLM to generate a realistic search query for a chunk."""
    response = ollama.chat(model="llama3.1:8b", messages=[{
        "role": "user",
        "content": f"""Given this survival/medical reference text, generate ONE realistic
search query that a person would type to find this information. Use plain language,
not exact phrases from the text. Vary between: lay person language, medical terminology,
and include occasional typos.

Text: {chunk_text[:500]}

Query:"""
    }])
    return response["message"]["content"].strip()
```

### Anti-Patterns to Avoid
- **Splitting tables across chunks:** Tables lose meaning when split. The locked decision keeps them whole. Our largest table sections are well under the 2K token limit.
- **Stripping YAML front matter metadata:** The front matter IS the metadata source for chunks. Read it, carry it forward, never discard it.
- **Using `ollama.embeddings()` (deprecated):** The current API is `ollama.embed()`. The older `embeddings()` function may still work but `embed()` supports batch input.
- **Omitting the `search_document:` / `search_query:` prefix:** nomic-embed-text is trained with task-type prefixes. Omitting them significantly degrades retrieval quality.
- **Large batch sizes for embedding:** Ollama has a known issue where batch sizes > 8 can degrade embedding quality with certain parallelism settings. Use batch size of 8 or embed one at a time.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Embedding generation | Custom model loading / sentence-transformers | `ollama.embed()` | Ollama handles model management, GPU/CPU optimization, and is already a project dependency. No need to manage PyTorch directly. |
| Cosine similarity | Manual dot product loops | `numpy.dot()` on L2-normalized vectors | Ollama returns L2-normalized vectors, so cosine similarity = dot product. numpy handles this efficiently. |
| YAML front matter parsing | Regex-based parsing | `pyyaml` with `---` delimiter split | YAML parsing has edge cases (multiline strings, special chars). pyyaml handles all of them. |
| JSON serialization of numpy arrays | Custom float conversion | `json.dumps(embedding, default=float)` or `.tolist()` | numpy float32 is not JSON serializable by default. Use `.tolist()` on the embedding vector before serialization. |

**Key insight:** This phase is glue code between Phase 2's section files and Phase 4's ChromaDB. The chunking logic is domain-specific (content-type-aware splitting rules) and SHOULD be custom. The embedding is a simple API call. Don't over-engineer either side.

## Common Pitfalls

### Pitfall 1: nomic-embed-text Prefix Omission
**What goes wrong:** Embeddings generated without `search_document:` / `search_query:` prefixes produce significantly lower retrieval quality.
**Why it happens:** Developers test with direct text input and it "works" -- but the model was trained to expect these prefixes and optimizes embedding space by task type.
**How to avoid:** Wrap all embedding calls in helper functions that always prepend the correct prefix. Never call `ollama.embed()` directly from chunking code.
**Warning signs:** Benchmark Recall@5 below 70% despite good chunk quality.

### Pitfall 2: Ollama Batch Embedding Quality Degradation
**What goes wrong:** Large batch sizes (16+) produce embeddings with lower cosine similarity to individually-generated embeddings.
**Why it happens:** Known Ollama issue (#6262) related to parallelism settings. Batch sizes 2-8 show cosine similarity ~0.9999 vs individual; batch 16+ drops to ~0.94-0.96.
**How to avoid:** Use batch size <= 8. For ~2,200 sections producing ~3,000 estimated chunks, this means ~375 batches -- still fast (minutes, not hours).
**Warning signs:** Inconsistent retrieval results between development (small test set) and full corpus.

### Pitfall 3: Context Window Truncation
**What goes wrong:** Chunks exceeding 2,048 tokens are silently truncated by nomic-embed-text (via Ollama), producing embeddings that don't represent the full chunk.
**Why it happens:** Ollama's nomic-embed-text model has a 2K token context window. The HuggingFace model card says 8,192, but Ollama's GGUF quantization uses 2K.
**How to avoid:** Target 512 tokens max per chunk. With our median section at ~210 tokens, only the largest sections need splitting. Even the 512-token target leaves 4x margin below the 2K limit.
**Warning signs:** Long chunks (especially table-of-contents sections or large reference tables) producing poor retrieval scores.

### Pitfall 4: Safety Warning Metadata Size
**What goes wrong:** Warning text duplicated across many chunks inflates JSONL file sizes significantly.
**Why it happens:** Some sections have multiple long warnings (WARNING + CAUTION + NOTE), each potentially hundreds of characters.
**How to avoid:** This is acceptable -- safety warnings MUST be preserved (project principle). The total corpus is small (~3.9 MB sections, estimated ~15-30 MB JSONL with embeddings). Storage is not a constraint.
**Warning signs:** None -- this is expected behavior, not a problem to solve.

### Pitfall 5: Benchmark Bias from Auto-Generated Queries
**What goes wrong:** LLM-generated queries may be too "clean" or too similar to source text, inflating Recall scores.
**Why it happens:** The LLM naturally echoes the source document's language patterns.
**How to avoid:** Prompt the LLM explicitly for variation: lay person queries, medical jargon, typos, emotional phrasing. Sample from diverse document types. Include negative examples (queries that should NOT match).
**Warning signs:** Recall@5 >= 95% with auto-generated pairs but poor real-world retrieval quality.

## Code Examples

### Reading Section Files with YAML Front Matter
```python
# Source: Established pipeline pattern from pipeline/writer.py
import yaml
from pathlib import Path

def read_section_file(filepath: Path) -> tuple[dict, str]:
    """Read a section Markdown file, returning (metadata_dict, content_str)."""
    text = filepath.read_text(encoding="utf-8")

    # Split at YAML front matter delimiters
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            metadata = yaml.safe_load(parts[1])
            content = parts[2].strip()
            return metadata, content

    # No front matter -- return empty metadata and full text
    return {}, text
```

### Procedure Step Detection and Splitting
```python
# Source: CONTEXT.md locked decision for procedure chunking
import re

def chunk_procedure(content: str, metadata: dict, max_tokens: int = 512) -> list[str]:
    """Split procedure content at step boundaries.

    Detects numbered steps (1., 2., a., b.) and splits at each step.
    Steps exceeding max_tokens are further split at sentence boundaries.
    """
    # Pattern matches: "1.", "2.", "a.", "b.", "1)", "a)", etc.
    step_pattern = re.compile(r"^(\d+[\.\)]\s|[a-z][\.\)]\s)", re.MULTILINE)

    # Find all step boundaries
    matches = list(step_pattern.finditer(content))

    if not matches:
        # No numbered steps found -- fall back to general chunking
        return chunk_general(content, metadata, max_tokens)

    chunks = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        step_text = content[start:end].strip()

        if estimate_tokens(step_text) <= max_tokens:
            chunks.append(step_text)
        else:
            # Step too long -- split at sentence boundaries
            chunks.extend(split_at_sentences(step_text, max_tokens))

    # Include any preamble text before the first step
    if matches[0].start() > 0:
        preamble = content[:matches[0].start()].strip()
        if preamble:
            chunks.insert(0, preamble)

    return chunks
```

### Embedding with Batch Safety
```python
# Source: Ollama Python library + GitHub issue #6262 batch quality findings
import ollama

BATCH_SIZE = 8  # Safe batch size per Ollama issue #6262

def embed_chunks(texts: list[str], model: str = "nomic-embed-text") -> list[list[float]]:
    """Embed a list of texts in safe batches with search_document prefix."""
    all_embeddings = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        prefixed = [f"search_document: {t}" for t in batch]
        response = ollama.embed(model=model, input=prefixed)
        all_embeddings.extend(response["embeddings"])

    return all_embeddings
```

### Token Estimation Without Heavy Dependencies
```python
def estimate_tokens(text: str) -> int:
    """Estimate token count using character-based heuristic.

    BERT tokenizer averages ~4 characters per token for English prose.
    This is conservative (overestimates) which is safer for chunk sizing.
    """
    return len(text) // 4
```

## Discretion Recommendations

These are areas marked as Claude's Discretion in CONTEXT.md, with research-backed recommendations:

### Optimal Chunk Size: 512 tokens (~2,048 characters)
**Rationale:** Industry consensus for 2025-2026 converges on 256-512 tokens as the sweet spot for factoid/procedural queries (our primary use case). A 512-token target:
- Fits 85% of existing sections as single chunks (no splitting needed)
- Leaves 4x margin below nomic-embed-text's 2K token context window
- Aligns with the "recursive 512-token splitting" approach that ranked #1 at 69% accuracy in a February 2026 benchmark of 7 strategies
- Is large enough to preserve meaningful context for survival procedures

### Safety Warning Scope: Same-section (locked decision confirmed)
**Rationale:** The CONTEXT.md locks this as "all warnings on all chunks in the same section." This is correct and simple. Proximity-based approaches (e.g., "within N chunks") add complexity without clear benefit since the Phase 2 section splitter already groups related content by section headers.

### Standalone Safety Warning Sections: Yes, emit as retrievable chunks
**Rationale:** Safety warning sections (where `content_type.primary == "safety_warning"`) should be their own retrievable chunks. This ensures they surface in search results when users query directly for warnings (e.g., "water purification warnings"). They also exist as metadata on related chunks, providing dual coverage.

### Failure Path if nomic-embed-text Fails Benchmark: Stop and report
**Rationale:** Auto-trying alternative models without user input could mask deeper issues (bad chunks, wrong evaluation methodology). If nomic-embed-text fails Recall@5 >= 85%, the pipeline should:
1. Print detailed failure report (per-query scores, worst performers)
2. Suggest investigation steps (inspect failed queries, check chunk quality)
3. Exit non-zero so the user can decide next steps
This aligns with the project principle of "when context is insufficient, say so -- never guess."

### Short Chunk Minimum: No minimum threshold
**Rationale:** The CONTEXT.md explicitly states "Short chunks are kept as-is (no merging with neighbors) -- some short sections like safety notes and definitions are self-contained." This is correct. Short chunks with strong metadata still retrieve well. Merging would violate section boundaries and risk mixing safety warnings across topics.

### Overlap Strategy: No overlap between consecutive chunks
**Rationale:** A January 2026 systematic analysis found that overlap provided no measurable benefit and only increased indexing cost. Our content is already well-structured (Phase 2 section splitting preserves semantic boundaries), and our chunk sizes are relatively small. Overlap would add storage cost without retrieval benefit.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fixed-size character splitting | Content-type-aware semantic splitting | 2024-2025 | Preserves procedural integrity, tables, safety warnings |
| 1,024 token chunks | 256-512 token chunks | 2025-2026 | Better retrieval for factoid queries; "context cliff" at ~2,500 tokens |
| 10-20% chunk overlap | No overlap | Jan 2026 study | Overlap showed no measurable benefit, only increased indexing cost |
| Semantic chunking (embedding-based splitting) | Recursive character splitting with structure awareness | Feb 2026 benchmark | Semantic chunking produced 43-token fragments at 54% accuracy vs recursive at 69% |
| `ollama.embeddings()` | `ollama.embed()` | Ollama 0.2.0+ | New API supports batch input, L2-normalized output |

**Deprecated/outdated:**
- `ollama.embeddings()`: Replaced by `ollama.embed()` which supports batch input
- Sentence-level semantic chunking: Produces fragments too small for reliable retrieval

## Open Questions

1. **Exact nomic-embed-text context window via Ollama**
   - What we know: HuggingFace model card says 8,192 tokens. Ollama model page says 2K context. There are reports of crashes when num_ctx > 2048 for v1.5.
   - What's unclear: Whether the Ollama-served model actually supports > 2,048 tokens or silently truncates.
   - Recommendation: Target 512 tokens per chunk (well under either limit). Verify empirically during benchmark by testing a 1,500-token chunk and checking if the embedding changes when truncated to 500 tokens.

2. **Ollama embed() return type structure**
   - What we know: Returns `{"embeddings": [[float, ...], ...]}`. Vectors are L2-normalized.
   - What's unclear: Whether the Python library returns a dict or a typed object with `.embeddings` attribute.
   - Recommendation: Test both access patterns (`response["embeddings"]` and `response.embeddings`) and use whichever works. LOW risk -- trivial to fix.

3. **BERT tokenizer accuracy for token estimation**
   - What we know: nomic-embed-text uses BERT tokenizer (bert-base-uncased). Character-based estimation (~4 chars/token) is approximate.
   - What's unclear: Whether medical/military terminology tokenizes significantly differently (acronyms like "FM-21-76", chemical names like "sodium hypochlorite").
   - Recommendation: Use character-based estimation for chunking (conservative, overestimates). If benchmark reveals issues, add `tokenizers` library for precise counting. MEDIUM priority -- affects edge cases only.

## Sources

### Primary (HIGH confidence)
- [Ollama Embedding Docs](https://docs.ollama.com/capabilities/embeddings) - embed() API, batch support, L2-normalized output
- [nomic-ai/nomic-embed-text-v1.5 HuggingFace](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5) - 768 dimensions, prefix requirements (search_document:/search_query:), Matryoshka dimensions, MTEB scores
- [Ollama nomic-embed-text model page](https://ollama.com/library/nomic-embed-text) - 274MB model size, 2K context window (Ollama-specific)
- [Ollama Python library](https://github.com/ollama/ollama-python) - embed() function signature, batch input support, AsyncClient

### Secondary (MEDIUM confidence)
- [Ollama batch embedding quality issue #6262](https://github.com/ollama/ollama/issues/6262) - Batch sizes 16+ degrade quality; 2-8 safe. Root cause: parallelism settings.
- [Firecrawl: Best Chunking Strategies for RAG 2026](https://www.firecrawl.dev/blog/best-chunking-strategies-rag) - Recursive 512-token splitting ranked #1 at 69% accuracy; semantic chunking at 54%.
- [LangCopilot: Document Chunking for RAG (2025)](https://langcopilot.com/posts/2025-10-11-document-chunking-for-rag-practical-guide) - Overlap showed no measurable benefit (Jan 2026 analysis); 256-512 token sweet spot.
- [Milvus: Optimal chunk size for RAG](https://milvus.io/ai-quick-reference/what-is-the-optimal-chunk-size-for-rag-applications) - Factoid queries: 256-512 tokens; analytical queries: 1024+.
- [NVIDIA: Finding the Best Chunking Strategy](https://developer.nvidia.com/blog/finding-the-best-chunking-strategy-for-accurate-ai-responses/) - Content-aware chunking outperforms naive splitting.
- [ArXiv: Domain Specification of Embedding Models in Medicine (2025)](https://arxiv.org/pdf/2507.19407) - nomic-embed-text performs comparably to specialized medical models on biomedical terminology.

### Tertiary (LOW confidence)
- Nomic-embed-text context window behavior via Ollama (2K vs 8K) - contradictory sources; empirical verification needed.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already in project, APIs verified against official docs
- Architecture: HIGH - Content-type-aware dispatch pattern is well-established; JSONL output is standard
- Chunking strategy: HIGH - Locked decisions from CONTEXT.md are well-supported by 2025-2026 research
- Embedding benchmark: MEDIUM - Auto-generation methodology is established but requires empirical validation on this corpus
- Pitfalls: HIGH - Ollama batch issue verified via GitHub issue; prefix requirement verified via HuggingFace model card

**Research date:** 2026-02-28
**Valid until:** 2026-03-28 (stable domain, slow-moving ecosystem)
