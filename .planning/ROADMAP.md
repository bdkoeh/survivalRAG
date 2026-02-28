# Roadmap: SurvivalRAG

## Overview

SurvivalRAG delivers a pre-built, source-cited survival/medical RAG knowledge base as a Docker container. The build progresses through a document pipeline (source, process, chunk, embed) into a retrieval-and-generation backend, validated by an evaluation framework, then wrapped in user interfaces and packaged for zero-config Docker deployment. Document processing quality determines all downstream quality -- the pipeline is ordered so each phase can verify its output before the next phase consumes it.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Content Sourcing & Licensing** - Acquire Tier 1 public domain documents with verified licensing and provenance manifests
- [ ] **Phase 2: Document Processing** - Extract, clean, classify, and tag text from source PDFs
- [ ] **Phase 3: Chunking & Embedding** - Content-type-aware chunking with safety warning preservation, embedding model validation, and corpus embedding
- [ ] **Phase 4: Retrieval Pipeline** - Vector similarity search with category filtering and hybrid search for medical terminology
- [ ] **Phase 5: Response Generation** - Safety-first, source-cited, field-manual-style response generation with hallucination refusal
- [ ] **Phase 6: Evaluation Framework** - Golden query dataset, retrieval quality metrics, hallucination testing, and citation faithfulness validation
- [ ] **Phase 7: User Interfaces** - Web chat UI and CLI with category filtering, citation display, and system status
- [ ] **Phase 8: Docker Packaging & Deployment** - Zero-config Docker Compose deployment with bundled Ollama, offline capability, and health checks

## Phase Details

### Phase 1: Content Sourcing & Licensing
**Goal**: Every Tier 1 source document is acquired, license-verified, and tracked with a provenance manifest -- establishing the legal and documentary foundation for the entire knowledge base
**Depends on**: Nothing (first phase)
**Requirements**: CONT-01, CONT-02, CONT-03, CONT-04, CONT-05
**Success Criteria** (what must be TRUE):
  1. All Tier 1 documents (US Army survival manuals, SF Medical Handbook, FEMA guides, CDC guidelines) are downloaded and stored locally
  2. Every document has a YAML provenance manifest with source URL, license type, distribution statement text, verification date, and processing notes
  3. Every document's Distribution Statement A is verified against an official source (armypubs.army.mil, FEMA.gov, CDC.gov) -- no document with ambiguous status is included
  4. Original source PDFs are retained alongside any processed outputs for audit and re-processing
**Plans**: 2 plans

Plans:
- [x] 01-01-PLAN.md -- Download all Tier 1 source documents with automated scripts and integrity verification
- [x] 01-02-PLAN.md -- Create YAML provenance manifests, exclusion documentation, and final validation

### Phase 2: Document Processing
**Goal**: Raw source PDFs are transformed into clean, classified, categorized text ready for chunking -- with zero corrupted medical dosages, measurements, or safety warnings
**Depends on**: Phase 1
**Requirements**: PROC-01, PROC-02, PROC-03, PROC-04, PROC-05
**Success Criteria** (what must be TRUE):
  1. Both born-digital and scanned PDFs produce clean extracted text (using Docling or validated alternative)
  2. OCR output for scanned Tier 1 medical content has been human-reviewed -- dosages, measurements, and safety warnings are verified correct
  3. Extracted text is free of headers, footers, page numbers, watermarks, and OCR artifacts
  4. Every text section is classified by content type (procedure, reference_table, safety_warning, general) and tagged with a content category (medical, water, shelter, fire, food, navigation, signaling, tools, first_aid)
**Plans**: 2 plans

Plans:
- [ ] 02-01-PLAN.md -- Build PDF extraction pipeline (Docling extraction, section splitting, text cleaning, Markdown output with metadata)
- [ ] 02-02-PLAN.md -- Build classification pipeline (Ollama-based content type and category tagging, dosage validation, verification reports, human review)

### Phase 3: Chunking & Embedding
**Goal**: Processed text is chunked with content-type awareness (procedures never split mid-step, tables kept whole, safety warnings co-located) and embedded with a validated model -- producing the ready-to-query knowledge base
**Depends on**: Phase 2
**Requirements**: CHNK-01, CHNK-02, CHNK-03, CHNK-04, CHNK-05, CHNK-06, CHNK-07
**Success Criteria** (what must be TRUE):
  1. Procedures are chunked at procedure boundaries -- no chunk splits a procedure mid-step
  2. Reference tables exist as single chunks with their headers preserved
  3. Safety warnings are never stripped, summarized, or separated from their procedures -- and are duplicated as metadata on related chunks
  4. Every chunk carries full metadata: source_document, page_number, section_header, content_type, category, source_url, license, distribution_statement, verification_date
  5. The embedding model (nomic-embed-text or validated alternative) is benchmarked against 50+ domain-specific query-document pairs before full corpus processing, and all chunks use the same model version recorded in metadata
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD
- [ ] 03-03: TBD

### Phase 4: Retrieval Pipeline
**Goal**: Users can query the knowledge base and get relevant, category-filtered results via vector similarity and hybrid search -- with automatic refusal when no chunks meet the relevance threshold
**Depends on**: Phase 3
**Requirements**: RETR-01, RETR-02, RETR-03, RETR-04, RETR-05
**Success Criteria** (what must be TRUE):
  1. A user query is embedded and matched against the ChromaDB knowledge base via vector similarity search, returning ranked relevant chunks
  2. Users can filter retrieval results by content category (medical, water, shelter, etc.)
  3. When no chunks pass the relevance threshold, the system returns "insufficient context" without calling the LLM
  4. Hybrid search (BM25 keyword + vector similarity) is available and improves medical terminology retrieval accuracy over vector-only search
  5. Retrieved context is assembled into a structured prompt that includes source metadata for downstream citation
**Plans**: TBD

Plans:
- [ ] 04-01: TBD
- [ ] 04-02: TBD

### Phase 5: Response Generation
**Goal**: The system generates safety-first, source-cited, field-manual-style responses that refuse to guess when context is insufficient and never hallucinate medical procedures
**Depends on**: Phase 4
**Requirements**: RESP-01, RESP-02, RESP-03, RESP-04, RESP-05, RESP-06, RESP-07
**Success Criteria** (what must be TRUE):
  1. Every response cites which source document and section the information came from
  2. Safety warnings from source material are preserved and surfaced in responses -- a query about a medical procedure returns the associated warnings
  3. When retrieved context is insufficient, the system explicitly refuses rather than generating from LLM parametric knowledge
  4. Responses are formatted as concise, actionable steps (field-manual style): numbered steps for procedures, bullets for lists, bold for warnings
  5. The system never provides medical diagnoses -- it identifies itself as a reference tool only
  6. Responses stream token-by-token to reduce perceived latency, and post-generation verification checks that cited sources match retrieved chunks
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD
- [ ] 05-03: TBD

### Phase 6: Evaluation Framework
**Goal**: Retrieval quality, citation faithfulness, hallucination refusal, and safety warning surfacing are quantitatively validated against a golden query dataset -- proving the system works, not just demos well
**Depends on**: Phase 4, Phase 5
**Requirements**: EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05, EVAL-06
**Success Criteria** (what must be TRUE):
  1. A golden query dataset of 50+ survival/medical queries with expected results exists and is runnable as an automated evaluation suite
  2. Retrieval recall exceeds 85% on medical terminology queries
  3. The system refuses 100% of out-of-scope queries in the hallucination test suite (zero hallucinated responses)
  4. Citation faithfulness rate exceeds 90% on the evaluation set -- cited sources actually match retrieved chunks
  5. Medical procedure queries return associated safety warnings in the evaluation set
  6. The evaluation dataset includes realistic user queries (lay language, typos, emotional phrasing), not just developer-crafted queries
**Plans**: TBD

Plans:
- [ ] 06-01: TBD
- [ ] 06-02: TBD
- [ ] 06-03: TBD

### Phase 7: User Interfaces
**Goal**: Non-technical users can interact with the knowledge base through a browser-based chat UI, and power users can query from the command line -- both with category filtering, citation display, and clear disclaimers
**Depends on**: Phase 5
**Requirements**: WEBUI-01, WEBUI-02, WEBUI-03, WEBUI-04, WEBUI-05, WEBUI-06, CLI-01, CLI-02, CLI-03
**Success Criteria** (what must be TRUE):
  1. Opening localhost in a browser after system startup shows a chat interface where users can type queries and receive streamed responses
  2. The web UI displays citations with source document name, section, and page number for every response
  3. A category filter selector in the web UI allows users to scope queries to specific topics (medical, water, shelter, etc.)
  4. A visible disclaimer on the web UI states this is a reference tool, not medical advice, and a system status indicator shows whether the system is ready
  5. Power users can query from the command line (e.g., `survivalrag ask "how to purify water"`) with terminal-formatted markdown output and category filtering via CLI flag
**Plans**: TBD

Plans:
- [ ] 07-01: TBD
- [ ] 07-02: TBD

### Phase 8: Docker Packaging & Deployment
**Goal**: Anyone can `docker compose up` and have a fully functional, offline-capable survival knowledge base -- zero configuration, zero external dependencies after initial pull
**Depends on**: Phase 6, Phase 7
**Requirements**: DEPL-01, DEPL-02, DEPL-03, DEPL-04, DEPL-05, DEPL-06, DEPL-07, DEPL-08
**Success Criteria** (what must be TRUE):
  1. A single `docker compose up` command starts the complete system -- no additional steps, scripts, or configuration required
  2. Docker Compose runs two containers (application with FastAPI + Gradio + ChromaDB embedded, and Ollama) that start and communicate correctly
  3. The Ollama container automatically pulls default models (Llama 3.1 8B + nomic-embed-text) on first startup without user intervention
  4. After initial setup, the system is fully functional offline -- no external API calls at runtime
  5. Users can configure an external Ollama instance or a different LLM model via environment variables, and health checks verify all components before accepting queries
  6. Minimum hardware requirements (16GB RAM, 20GB disk) are documented in the README
**Plans**: TBD

Plans:
- [ ] 08-01: TBD
- [ ] 08-02: TBD
- [ ] 08-03: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Content Sourcing & Licensing | 2/2 | Complete | 2026-02-28 |
| 2. Document Processing | 0/2 | Not started | - |
| 3. Chunking & Embedding | 0/TBD | Not started | - |
| 4. Retrieval Pipeline | 0/TBD | Not started | - |
| 5. Response Generation | 0/TBD | Not started | - |
| 6. Evaluation Framework | 0/TBD | Not started | - |
| 7. User Interfaces | 0/TBD | Not started | - |
| 8. Docker Packaging & Deployment | 0/TBD | Not started | - |
