# Research Summary: SurvivalRAG

**Domain:** Pre-built survival/medical RAG knowledge base (Docker, offline, local LLM)
**Researched:** 2026-02-28
**Overall confidence:** HIGH

## Executive Summary

The survival/prepper AI space has zero real RAG products. Existing products (SurvivalNet $100-$700, Doom Box $720, READI Console $299+) all place raw PDFs next to generic LLMs with no retrieval pipeline connecting them. RAG frameworks (LlamaIndex, LangChain) provide tooling but ship no data. MedRAG provides a medical RAG architecture reference but no usable data. SurvivalRAG's actual retrieval pipeline over properly chunked, embedded, cited public domain content is the core differentiator — not one feature among many, but the reason the project exists.

The 2026 Python RAG stack is mature and well-documented. LlamaIndex for orchestration, ChromaDB (embedded) for vectors, nomic-embed-text v1.5 for embeddings, Llama 3.1 8B as default LLM, FastAPI + Gradio for the backend/UI, and Docker Compose (two containers: app + Ollama) for deployment. This stack follows Docker's own official RAG guide and is the consensus pattern across multiple production references.

The highest-risk work is document processing — not the software. OCR quality from scanned military PDFs, licensing verification (Distribution Statement A required — ITAR violations carry 20 years/$1M penalties), and content-type-aware chunking that preserves safety warnings are all foundational. If OCR produces garbage or chunking severs safety warnings from procedures, everything downstream fails. A 2025 clinical study found structure-aware chunking achieved 87% accuracy vs. 13% for fixed-size chunking (p = 0.001).

Small LLMs hallucinate medical content even with RAG — a 2025 radiology study measured 8% hallucination at baseline, dropping to 0% only with careful RAG implementation. Additionally, 57% of RAG citations lack faithfulness (post-rationalization). Safety-first prompt engineering, citation verification, and a comprehensive evaluation framework must be built alongside the pipeline, not after.

## Key Findings

**Stack:** Python + LlamaIndex + ChromaDB (embedded) + nomic-embed-text v1.5 + Llama 3.1 8B via Ollama + FastAPI + Gradio + Docker Compose (two containers). Docling for PDF extraction (PyMuPDF is AGPL — hard blocker for MIT/Apache project).

**Architecture:** Build-time ingestion (maintainer pipeline) → runtime read-only (user-facing). Two Docker containers (app + Ollama). Content-type-aware chunking for procedures, tables, safety warnings. ChromaDB embedded/persistent within the app container.

**Critical pitfall:** OCR corruption of medical dosages/safety warnings from scanned PDFs, chunking that severs safety warnings from procedures, and LLM hallucination of medical procedures despite RAG grounding. All three are safety failures, not quality issues.

## Research Conflicts Resolved

| Topic | STACK.md | ARCHITECTURE.md | Resolution |
|-------|----------|-----------------|------------|
| PDF extraction | Docling (MIT-compatible) | PyMuPDF4LLM (AGPL) | **Docling.** PyMuPDF is AGPL-3.0, incompatible with MIT/Apache project license. Hard blocker. |
| Web UI | Gradio (Python-native chat UI) | Static HTML/JS (zero dependencies) | **Gradio.** Faster to build, built-in ChatInterface with streaming, mobile-responsive. Eliminates frontend dev work. |
| Default LLM | Llama 3.1 8B | llama3.2:3b | **Llama 3.1 8B.** Better instruction-following and citation compliance. 3B is a "lite" option for CPU-only. |

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Project Foundation** — Scaffolding, dependencies, Docker skeleton, config system
   - Addresses: development environment, dependency management
   - Avoids: scope creep from premature feature work

2. **Document Collection & Licensing** — Source Tier 1 PDFs, verify Distribution Statement A per-document, create provenance manifests
   - Addresses: licensing verification (blocker risk), provenance tracking
   - Avoids: ITAR violations, including restricted documents
   - Research flag: Needs per-document verification from armypubs.army.mil

3. **Document Processing Pipeline** — PDF extraction (Docling), OCR, text cleaning, content-type classification, content-type-aware chunking with safety-warning preservation
   - Addresses: OCR quality, chunking strategy, safety warning co-location
   - Avoids: corrupted text, severed safety warnings
   - Research flag: Docling is newer — needs hands-on validation with military PDFs

4. **Knowledge Base Assembly** — Embedding generation (nomic-embed-text), ChromaDB ingestion, metadata structure, embedding model validation
   - Addresses: embedding quality for medical terminology, category metadata
   - Avoids: committing to wrong embedding model before validation
   - Research flag: nomic-embed-text medical performance needs empirical testing

5. **Retrieval & Generation Backend** — FastAPI API, query embedding, vector search, category filtering, hybrid search (BM25 + vector), safety-first prompt engineering, citation formatting, response streaming via Ollama
   - Addresses: core RAG pipeline, safety guardrails, citation faithfulness
   - Avoids: LLM hallucination, unfaithful citations
   - Research flag: Highest architectural risk — prompt engineering for small LLM safety

6. **Evaluation Framework** — Golden query dataset (50-100 queries), retrieval quality metrics (RAGAS), hallucination testing, citation faithfulness testing, safety warning surfacing tests, realistic user queries
   - Addresses: "works in demo" gap, production quality validation
   - Avoids: shipping with untested retrieval quality
   - Note: Should be built alongside Phase 5, not after

7. **User Interfaces** — Gradio web chat UI, Typer CLI, category filtering UI, citation display, disclaimer/status indicators
   - Addresses: user experience, accessibility for non-technical users
   - Avoids: over-engineering UI before backend is proven

8. **Docker Packaging & Deployment** — Docker Compose config, Ollama auto-model-pull, pre-built KB volume, health checks, first-run experience, README
   - Addresses: zero-config deployment, offline capability, non-technical user setup
   - Avoids: complex deployment requiring Docker expertise

**Phase ordering rationale:**
- Licensing verification (Phase 2) gates everything — legal blocker
- Document processing (Phase 3) quality determines all downstream quality
- Embedding model must be validated (Phase 4) before full corpus processing — changing requires re-embedding everything
- Evaluation (Phase 6) should be built alongside retrieval (Phase 5), not after
- UI (Phase 7) is skin on top of working backend
- Docker packaging (Phase 8) is last — everything must work before containerizing

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Consensus stack verified across Docker official guide, multiple production references, current package versions confirmed |
| Features | HIGH | Table stakes and differentiators clear from competitor gap analysis — no real RAG exists in survival space |
| Architecture | HIGH | Two-container Docker Compose with embedded ChromaDB follows Docker's official RAG guide pattern |
| Pitfalls | HIGH | Multiple peer-reviewed 2025 studies with quantitative evidence for each critical pitfall |
| Embedding Model | MEDIUM | nomic-embed-text v1.5 is well-benchmarked on general tasks but medical terminology performance needs empirical validation |
| Document Processing | MEDIUM | Docling is newer. OCR quality on old military manuals inherently uncertain. Plan for manual review. |

## Gaps to Address

- **Docling on military PDFs**: Newer than PyMuPDF, less community adoption. Needs hands-on validation with actual Tier 1 documents.
- **nomic-embed-text on medical terminology**: Strong general benchmarks but medical-domain performance needs empirical testing with 50-query domain-specific test set.
- **Minimum viable LLM size**: Llama 3.1 8B recommended, but can 3B produce safe medical responses? Needs testing.
- **Optimal similarity threshold for "insufficient context" refusal**: Must be determined empirically with the actual knowledge base.
- **Category taxonomy granularity**: Too few categories limits usefulness; too many fragments the small corpus.
- **Tier 1 document availability**: Not all listed documents may have born-digital versions. OCR quality of available scans is unknown.
- **LlamaIndex vs direct ChromaDB + Ollama calls**: For a simple retrieve-then-generate pipeline, direct API calls may be simpler. Validate during Phase 5.

## Sources

All sources documented in individual research files:
- `STACK.md` — Technology selection with 25+ verified sources
- `FEATURES.md` — Feature landscape with competitor analysis
- `ARCHITECTURE.md` — Architecture patterns with Docker and RAG references
- `PITFALLS.md` — Domain pitfalls with 30+ peer-reviewed and community sources
