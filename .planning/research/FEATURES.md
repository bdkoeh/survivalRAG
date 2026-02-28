# Feature Landscape

**Domain:** Offline survival/medical RAG knowledge base
**Researched:** 2026-02-28
**Overall confidence:** MEDIUM-HIGH

## Table Stakes

Features users expect. Missing = product feels incomplete or untrustworthy.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Source-cited responses** | Every competitor (Perplexity, Google AI Search, MedRAG) cites sources. For medical/survival content, uncited answers are dangerous. Users must be able to verify. | Medium | Must include document name, section, and ideally page number. Appended source list is minimum; inline citations are better. |
| **Retrieval-grounded answers** | The entire value proposition. SurvivalNet, Doom Box, READI Console all fail here -- they place PDFs next to LLMs with no retrieval pipeline. Without RAG, the LLM falls back on training data, which for medical content can be lethally wrong. | High | Core pipeline: chunking, embedding, vector search, context injection. This is the product. |
| **Offline-capable after setup** | Target users (preppers, disaster responders, off-grid communities) need this to work without internet. SurvivalNet, Doom Box, READI Console all advertise "offline" as primary feature. | Medium | All components (LLM, embeddings, vector DB, UI) must be local. No external API calls at runtime. |
| **Web chat interface** | Standard interaction model. AnythingLLM, RAGFlow, every RAG product ships a web UI. READI Console serves via local WiFi hotspot to any device browser. | Medium | Must work on mobile browsers too -- users may connect from phones/tablets via local network. |
| **Safety-first refusal** | Medical/survival domain demands it. When retrieved context is insufficient or ambiguous, the system must say "I don't have enough information" rather than guess. Small LLMs (7B and under) are known to hallucinate medical procedures even with RAG. | Medium | Requires careful prompt engineering, confidence thresholds, and explicit system instructions. Not just a prompt -- needs to be tested extensively. |
| **Preservation of safety warnings** | Source documents (military field manuals, CDC guides) contain critical safety warnings. Stripping or summarizing them away could cause harm. | Low | Chunking strategy must keep warnings co-located with procedures. Prompt must instruct LLM to surface warnings. |
| **Field-manual-style output** | Users in emergency situations need concise, actionable steps -- not conversational prose. Military field manuals use numbered steps, bullet points, direct imperatives for a reason. | Low | Achieved through system prompt engineering and few-shot examples. Constrain output format to numbered steps, bullets, direct language. |
| **Easy deployment** | Non-technical users are a primary audience. READI Console and SurvivalNet sell as plug-and-play. Doom Box ships pre-configured. If SurvivalRAG requires command-line expertise to set up, it loses the accessibility advantage. | Medium | Docker with bundled Ollama + default model. `docker compose up` then open browser. Single-command setup. |
| **Document provenance manifest** | Legal requirement for public domain content distribution. Every document needs source URL, license type, distribution statement, verification date. Users and contributors need to verify licensing. | Low | JSON/YAML manifest file shipped with the knowledge base. Not a runtime feature -- a distribution artifact. |
| **Basic category/topic filtering** | Users asking about water purification should not get results about wound care. SurvivalNet organizes by category. READI Console has separate libraries. Every RAG product with domain-specific content implements some form of topic scoping. | Medium | Metadata tags on chunks (medical, water, shelter, food, navigation, fire, etc.) with pre-filter before vector search. |

## Differentiators

Features that set SurvivalRAG apart. Not expected (competitors lack them), but highly valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Actual retrieval pipeline (the core differentiator)** | No competitor in the survival/prepper space has a real RAG pipeline. SurvivalNet = PDFs on a drive. Doom Box = 100GB knowledge dump + generic LLM. READI Console = Ollama + AnythingLLM + unstructured PDFs. None connect documents to the LLM through structured retrieval. SurvivalRAG does. | High | This is the reason the project exists. Vector search over properly chunked, embedded, domain-specific content. |
| **Pre-built, curated knowledge base** | MedRAG provides pipeline code but no data. RAG frameworks (LlamaIndex, LangChain) provide tooling but no data. Users of SurvivalNet/Doom Box/READI get raw PDFs with no processing. SurvivalRAG ships ready-to-query embedded content. Zero user effort to go from install to first answer. | High | Document sourcing, licensing verification, OCR cleanup, chunking, embedding -- all done before distribution. This is the hard, valuable work. |
| **Content-type-aware chunking** | Procedures, reference tables, safety warnings, and narrative descriptions all need different chunking strategies. Naive fixed-size chunking loses context on procedures (step 3 gets separated from step 1) and breaks tables. | Medium | Procedures: chunk by complete procedure. Tables: keep table intact. Safety warnings: co-locate with related procedure. Requires per-content-type processing rules. |
| **Hybrid search (vector + BM25)** | Pure vector search struggles with exact medical terminology, drug names, and specific field manual designations (e.g., "FM 21-76"). BM25 keyword search handles these well. Combining both is standard in production RAG (2025 best practice). ChromaDB 1.5.x supports BM25 natively. | Medium | BM25 for keyword matching + vector similarity for semantic search, merged with reciprocal rank fusion. Significantly improves retrieval for domain-specific terminology. |
| **Confidence indicators on responses** | When retrieved context is weak (low similarity scores, few matches), surface that to the user. "I found limited information on this topic -- verify with other sources." Goes beyond simple refusal to graduated confidence. | Medium | Use retrieval similarity scores as heuristic. Low scores or few retrieved chunks = lower confidence flagged to user. Not LLM-based scoring (too expensive for local models) -- similarity-score-based. |
| **CLI interface** | Power users, scripters, and future Meshtastic integration all benefit from a CLI. Most consumer RAG products lack this. Critical for automation and integration into other tools. | Low | Simple stdin/stdout interface via Typer + Rich. Query in, formatted answer out. Can be built on same FastAPI backend as web UI. |
| **Retrieval quality evaluation suite** | Ship a test suite of real survival/medical queries with expected answers. Allows users and contributors to validate retrieval quality after any changes. MedRAG's MIRAGE benchmark is the reference model. | Medium | Golden dataset of ~50-100 query-answer pairs covering each content category. Automated scoring using RAGAS metrics (faithfulness, context recall, context precision). |
| **LLM-agnostic configuration** | Default bundled model for zero-config, but configurable to point at external Ollama instance, llama.cpp server, or other OpenAI-compatible endpoint. Users with better hardware can use larger, more capable models. | Low | Abstract the LLM interface behind a provider config. Support Ollama API (default), OpenAI-compatible API endpoint. Environment variable for Ollama URL. |
| **Knowledge base versioning** | As content is updated (new documents, improved OCR, better chunking), users need a clear version number and changelog. Critical for trust in a safety-critical domain. | Low | Semantic versioning for the knowledge base (e.g., KB v1.0.0). Changelog documenting what was added/changed/removed. Ships as metadata with the Docker image. |

## Anti-Features

Features to explicitly NOT build. Each would add complexity without proportional value, or would actively harm the product.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **User document ingestion pipeline (v1)** | Adds massive complexity: OCR, format handling, chunking, embedding, licensing questions. Delays shipping the core value (the pre-built knowledge base). Every user's documents will have different quality, licensing, and formatting. | Ship pre-built only for v1. Users who want custom docs can use AnythingLLM or similar tools alongside SurvivalRAG. Revisit in v2 after the core KB is proven. |
| **Medical diagnosis or triage** | This is a reference tool, not a diagnostic system. Any attempt at diagnosis creates liability, false confidence, and potential harm. Military field manuals and CDC guides provide procedures, not differential diagnosis. | Explicitly state in system prompt and UI: "This is a reference tool. It does not diagnose conditions. Seek professional medical help." |
| **Multi-model orchestration / agentic RAG** | Agent-based RAG (2025 trend) adds latency, complexity, and unpredictability. On small local LLMs, agent loops are slow and error-prone. A simple retrieve-then-generate pipeline is reliable and fast. | Single-pass retrieval + generation. No agent loops, no tool use, no multi-step reasoning. Keep it simple and predictable. |
| **Real-time document updates** | Knowledge base changes should be versioned releases, not live updates. Real-time sync adds complexity and makes reproducibility impossible. Content changes in a safety-critical domain need review before deployment. | Versioned releases of the knowledge base. New version = new Docker image tag. Users pull updates explicitly. |
| **User accounts / authentication** | This is a local tool. Adding auth adds deployment friction and complexity for zero benefit in the primary use case (single-user or household). | No auth. Whoever has network access to the Docker container can use it. Document this clearly. |
| **Telemetry / analytics** | Privacy-first, offline tool for people who explicitly want to avoid cloud dependencies. Any telemetry, even opt-in, undermines trust with the target audience. | Zero telemetry. Zero phone-home. Document this as a commitment. |
| **Compact/ultra-short response modes (v1)** | Mesh radio integration is out of scope for v1. Building compressed response modes before the core knowledge base is proven is premature optimization. | Full response mode only. Compact and ultra-short modes are part of the future Meshtastic milestone. |
| **Community contribution framework (v1)** | Accepting community content requires quality review processes, licensing verification workflows, and moderation infrastructure. This is a v2 concern after core quality is established. | Tier 1 content only for v1. Document the path to community contributions but do not build the infrastructure yet. |
| **Non-English content** | Adds embedding model complexity, chunking challenges, and doubles QA effort per language. English-language US government documents are the core content. | English only for v1. Note international expansion as a future direction. |
| **Knowledge graph / GraphRAG** | Trending in 2025 RAG research, but adds significant complexity (entity extraction, relationship modeling, graph database). Overkill for a curated document collection of manageable size. Standard vector search with metadata filtering handles this content well. | Vector search + BM25 hybrid. Consider GraphRAG only if cross-document relationships become a retrieval problem after v1 launch. |
| **Voice interface** | Adds speech-to-text and text-to-speech dependencies, increases resource requirements, and is not needed for the primary use case. | Text-only for v1. The CLI and web chat interfaces cover the core use cases. |
| **Fine-tuned custom LLM** | Training a custom model is expensive, hard to maintain, and unnecessary when RAG provides grounded answers from retrieved context. Medical fine-tuned models may actually be worse for RAG because they are more likely to generate from parametric medical knowledge rather than citing retrieved context. | Use RAG with a strong general-purpose instruction-following model (Llama 3.1 8B). System prompts handle domain-specific behavior. |

## Feature Dependencies

```
Document Processing Pipeline
  -> Chunked + Embedded Knowledge Base
    -> Vector Search / Retrieval Pipeline
      -> RAG Response Generation (with citations, safety, formatting)
        -> Web Chat UI
        -> CLI Interface

Category Metadata Tagging (during processing)
  -> Category Filtering (during retrieval)

Hybrid Search (BM25 + Vector)
  -> Improved retrieval for medical terminology

Document Provenance Manifest
  -> Knowledge Base Versioning

Retrieval Quality Evaluation Suite
  -> Confidence Indicators (uses similarity score thresholds from eval)

Docker Packaging
  -> Bundled Ollama + Default Model
    -> Zero-Config Deployment
```

Key ordering constraints:
- Document processing must be complete before any retrieval features work
- Category metadata must be assigned during processing, not retrofitted
- Evaluation suite should be built alongside the retrieval pipeline, not after
- Docker packaging is the last step before distribution

## MVP Recommendation

### Must Ship (Phase 1 - Core)

1. **Pre-built knowledge base** from Tier 1 documents -- this is the product
2. **Retrieval-grounded responses** with vector search -- the core differentiator
3. **Source citations** on every response -- non-negotiable for safety domain
4. **Safety-first refusal** when context is insufficient
5. **Field-manual-style formatting** via prompt engineering
6. **Web chat interface** -- primary interaction model
7. **Docker deployment** with bundled Ollama + default model
8. **Document provenance manifest** -- legal requirement

### Should Ship (Phase 1 - Enhanced)

9. **Basic category filtering** (medical, water, shelter, food, fire, navigation)
10. **CLI interface** for power users
11. **Hybrid search** (BM25 + vector) for medical terminology accuracy
12. **LLM-agnostic configuration** (point at external Ollama/llama.cpp)

### Ship Soon After (Phase 2)

13. **Confidence indicators** on responses
14. **Retrieval quality evaluation suite** with golden dataset
15. **Knowledge base versioning** with changelog
16. **Content-type-aware chunking** improvements

### Defer

- **User document ingestion**: v2, after core KB is proven
- **Community contribution framework**: v2, after quality processes established
- **Compact/ultra-short response modes**: Meshtastic milestone
- **Non-English content**: future expansion
- **Voice interface**: not in current scope

## Competitor Feature Matrix

| Feature | SurvivalNet | Doom Box | READI Console | MedRAG | AnythingLLM | **SurvivalRAG** |
|---------|-------------|----------|---------------|--------|-------------|-----------------|
| Pre-built survival content | PDFs on USB | 100GB knowledge dump | Wikipedia + 50K books + maps | No data | No data | Curated, chunked, embedded |
| RAG retrieval pipeline | No | No | No (generic Ollama) | Yes (code only) | Yes (generic) | Yes (domain-optimized) |
| Source citations | No | No | No | Yes | Partial | Yes (required) |
| Safety guardrails | No | No | No | N/A | No | Yes (explicit) |
| Offline capable | Yes | Yes | Yes | No (cloud) | Yes (desktop) | Yes |
| Easy deployment | Plug-and-play hardware | Pre-configured hardware | Pre-configured hardware | Developer setup | Docker/Desktop | Docker pull + open browser |
| Category filtering | Manual file browsing | No | Separate libraries | Corpus selection | Workspaces | Metadata-based retrieval filter |
| Field-manual formatting | N/A | N/A | N/A | Clinical QA style | Generic | Concise, actionable steps |
| Medical terminology search | N/A | Generic search | Generic search | Specialized | Generic | Hybrid search (planned) |
| Price | $100-$700 | $720 | $299+ | Free (code) | Free (self-host) | **Free** |

## Sources

- [SurvivalNet](https://thesurvivalnet.com/) - Product page with feature descriptions
- [LandStruck Doom Box](https://landstruck.com/product/offline-ai-computer-the-doom-box/) - Product specifications
- [R.E.A.D.I. Console](https://readiconsole.com/) - Product features and specs
- [MedRAG GitHub](https://github.com/Teddy-XiongGZ/MedRAG) - Toolkit features and benchmarks
- [AnythingLLM](https://anythingllm.com/) - Feature documentation
- [RAGAS Framework](https://docs.ragas.io/en/latest/concepts/metrics/) - Evaluation metrics
- [ChromaDB BM25 Support](https://www.trychroma.com/) - Hybrid search capabilities
- [Chunking Strategies for RAG (Weaviate)](https://weaviate.io/blog/chunking-strategies-for-rag)
- [Document Chunking: 9 Strategies Tested](https://langcopilot.com/posts/2025-10-11-document-chunking-for-rag-practical-guide)
