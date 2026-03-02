# Requirements: SurvivalRAG

**Defined:** 2026-02-28
**Core Value:** Every survival/medical answer is grounded in cited public domain source documents -- when context is insufficient, the system says so rather than guessing.

## v1 Requirements

### Content Sourcing & Licensing

- [x] **CONT-01**: All Tier 1 source documents are downloaded from official or verified sources
- [x] **CONT-02**: Every document has verified Distribution Statement A ("Approved for public release; distribution is unlimited") from an official source (armypubs.army.mil, FEMA.gov, CDC.gov)
- [x] **CONT-03**: Every document has a YAML provenance manifest recording: source URL, license type, distribution statement text, verification date, and processing notes
- [x] **CONT-04**: No document with ambiguous or restricted distribution status is included
- [x] **CONT-05**: Source PDFs are retained alongside processed text for audit and re-processing

### Document Processing

- [x] **PROC-01**: PDF text extraction handles both born-digital and scanned documents
- [x] **PROC-02**: OCR output for scanned documents is human-reviewed for Tier 1 medical content -- zero corrupted dosages, measurements, or safety warnings
- [x] **PROC-03**: Extracted text is cleaned of headers/footers, page numbers, watermarks, and OCR artifacts
- [x] **PROC-04**: Each text section is classified by content type: procedure, reference_table, safety_warning, or general
- [x] **PROC-05**: Each text section is tagged with a content category (medical, water, shelter, fire, food, navigation, signaling, tools, first_aid)

### Chunking & Embedding

- [x] **CHNK-01**: Procedures are chunked at procedure boundaries -- never split mid-step
- [x] **CHNK-02**: Reference tables are kept as single chunks with headers preserved
- [x] **CHNK-03**: Safety warnings are never stripped, summarized, or separated from their associated procedure
- [x] **CHNK-04**: Safety warnings are duplicated as metadata on related chunks so they surface even when the warning chunk itself is not retrieved
- [x] **CHNK-05**: Every chunk has metadata: source_document, page_number, section_header, content_type, category, source_url, license, distribution_statement, verification_date
- [x] **CHNK-06**: Embedding model is benchmarked against 50+ domain-specific query-document pairs before full corpus processing
- [x] **CHNK-07**: All chunks are embedded using the same model version, recorded in metadata

### Retrieval Pipeline

- [x] **RETR-01**: User query is embedded and matched against the knowledge base via vector similarity search
- [x] **RETR-02**: User can optionally filter retrieval by content category
- [x] **RETR-03**: Chunks below a relevance threshold are discarded -- if no chunks pass, the system returns "insufficient context" without calling the LLM
- [x] **RETR-04**: Hybrid search (BM25 keyword + vector similarity) is available for medical terminology accuracy
- [ ] **RETR-05**: Retrieved context is assembled into a prompt with source metadata for citation

### Response Generation

- [ ] **RESP-01**: Every response cites which source document and section the information came from
- [ ] **RESP-02**: Safety warnings from source material are preserved and surfaced in responses
- [ ] **RESP-03**: When retrieved context is insufficient, the system explicitly refuses rather than generating from LLM parametric knowledge
- [ ] **RESP-04**: Responses are formatted as concise, actionable steps (field-manual style) -- numbered steps for procedures, bullets for lists, bold for warnings
- [ ] **RESP-05**: The system never provides medical diagnoses -- it is a reference tool only
- [ ] **RESP-06**: Responses are streamed token-by-token to reduce perceived latency
- [ ] **RESP-07**: Post-generation verification checks that cited sources match retrieved chunks

### Web Interface

- [ ] **WEBUI-01**: Browser-based chat interface accessible at localhost after Docker startup
- [ ] **WEBUI-02**: User can type a query and receive a streamed response with citations
- [ ] **WEBUI-03**: Category filter selector allows scoping queries to specific topics
- [ ] **WEBUI-04**: Citations are displayed with source document name, section, and page number
- [ ] **WEBUI-05**: A visible disclaimer states this is a reference tool, not medical advice
- [ ] **WEBUI-06**: System status indicator shows whether the system is ready (model loaded, KB available)

### CLI Interface

- [ ] **CLI-01**: User can query from the command line (e.g., `survivalrag ask "how to purify water"`)
- [ ] **CLI-02**: Responses are formatted for terminal output with markdown rendering
- [ ] **CLI-03**: Category filtering is available via CLI flag

### Deployment

- [ ] **DEPL-01**: Single `docker compose up` command starts the complete system
- [ ] **DEPL-02**: Docker Compose runs two containers: application (FastAPI + Gradio + ChromaDB embedded) and Ollama
- [ ] **DEPL-03**: Ollama container automatically pulls default models (Llama 3.1 8B + nomic-embed-text) on first startup
- [ ] **DEPL-04**: System is fully functional offline after initial setup (no external API calls at runtime)
- [ ] **DEPL-05**: User can configure an external Ollama instance instead of the bundled one
- [ ] **DEPL-06**: User can configure a different LLM model via environment variable
- [ ] **DEPL-07**: Health checks verify all components are running before accepting queries
- [ ] **DEPL-08**: Minimum hardware requirements are documented (16GB RAM, 20GB disk)

### Evaluation & Quality

- [ ] **EVAL-01**: Golden query dataset of 50+ survival/medical queries with expected results
- [ ] **EVAL-02**: Retrieval quality measured: recall >85% on medical terminology queries
- [ ] **EVAL-03**: Hallucination test suite: system refuses 100% of out-of-scope queries
- [ ] **EVAL-04**: Citation faithfulness rate >90% on evaluation set
- [ ] **EVAL-05**: Safety warning surfacing verified: medical procedure queries return associated warnings
- [ ] **EVAL-06**: Evaluation includes realistic user queries (lay language, typos, emotional phrasing), not just developer-crafted queries

## v2 Requirements

### User Document Ingestion

- **INGEST-01**: User can add their own PDF/text documents to the knowledge base
- **INGEST-02**: User-added documents are processed through the same pipeline (extract, chunk, embed)
- **INGEST-03**: User-added content is kept separate from curated Tier 1 content

### Community Contributions

- **COMM-01**: Contributor guide with document submission workflow
- **COMM-02**: Quality review process for community-submitted documents
- **COMM-03**: Tier 3 content architecturally separated from Tier 1/2

### Extended Content

- **EXTD-01**: Tier 2 documents processed and added to knowledge base
- **EXTD-02**: Regional/climate-specific survival content (maritime, desert, arctic, tropical, urban)
- **EXTD-03**: Non-English content support

### Response Modes

- **MODE-01**: Compact response mode for mobile/low-bandwidth
- **MODE-02**: Ultra-short response mode (~200 characters) for mesh radio
- **MODE-03**: Response mode selectable per query

### Knowledge Base Management

- **KBMG-01**: Knowledge base semantic versioning with changelog
- **KBMG-02**: Confidence indicators on responses based on retrieval similarity scores
- **KBMG-03**: Query logging for retrieval quality monitoring

## Out of Scope

| Feature | Reason |
|---------|--------|
| Meshtastic mesh radio integration | Separate future milestone -- depends on compact response modes |
| Medical diagnosis or triage | Reference tool only -- diagnosis creates liability and potential harm |
| Multi-model orchestration / agentic RAG | Agent loops are slow and unreliable on small local LLMs |
| Real-time document updates | Safety-critical content needs versioned releases, not live updates |
| User accounts / authentication | Local tool -- auth adds friction for zero benefit |
| Telemetry / analytics | Privacy-first, offline tool -- any telemetry undermines trust |
| Knowledge graph / GraphRAG | Overkill for curated document collection at this scale |
| Voice interface | Adds heavy dependencies without proportional value |
| Fine-tuned custom LLM | RAG grounding > parametric medical knowledge for this use case |
| Non-English content (v1) | Doubles QA effort per language -- English-only for v1 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CONT-01 | Phase 1 | Complete (01-01, expanded 01-03) |
| CONT-02 | Phase 1 | Complete (01-02, expanded 01-04) |
| CONT-03 | Phase 1 | Complete (01-02, expanded 01-04) |
| CONT-04 | Phase 1 | Complete (01-02, expanded 01-04) |
| CONT-05 | Phase 1 | Complete (01-01, expanded 01-03) |
| PROC-01 | Phase 2 | Complete |
| PROC-02 | Phase 2 | Complete |
| PROC-03 | Phase 2 | Complete |
| PROC-04 | Phase 2 | Complete |
| PROC-05 | Phase 2 | Complete |
| CHNK-01 | Phase 3 | Complete |
| CHNK-02 | Phase 3 | Complete |
| CHNK-03 | Phase 3 | Complete |
| CHNK-04 | Phase 3 | Complete |
| CHNK-05 | Phase 3 | Complete |
| CHNK-06 | Phase 3 | Complete |
| CHNK-07 | Phase 3 | Complete |
| RETR-01 | Phase 4 | Complete |
| RETR-02 | Phase 4 | Complete |
| RETR-03 | Phase 4 | Complete |
| RETR-04 | Phase 4 | Complete |
| RETR-05 | Phase 4 | Pending |
| RESP-01 | Phase 5 | Pending |
| RESP-02 | Phase 5 | Pending |
| RESP-03 | Phase 5 | Pending |
| RESP-04 | Phase 5 | Pending |
| RESP-05 | Phase 5 | Pending |
| RESP-06 | Phase 5 | Pending |
| RESP-07 | Phase 5 | Pending |
| EVAL-01 | Phase 6 | Pending |
| EVAL-02 | Phase 6 | Pending |
| EVAL-03 | Phase 6 | Pending |
| EVAL-04 | Phase 6 | Pending |
| EVAL-05 | Phase 6 | Pending |
| EVAL-06 | Phase 6 | Pending |
| WEBUI-01 | Phase 7 | Pending |
| WEBUI-02 | Phase 7 | Pending |
| WEBUI-03 | Phase 7 | Pending |
| WEBUI-04 | Phase 7 | Pending |
| WEBUI-05 | Phase 7 | Pending |
| WEBUI-06 | Phase 7 | Pending |
| CLI-01 | Phase 7 | Pending |
| CLI-02 | Phase 7 | Pending |
| CLI-03 | Phase 7 | Pending |
| DEPL-01 | Phase 8 | Pending |
| DEPL-02 | Phase 8 | Pending |
| DEPL-03 | Phase 8 | Pending |
| DEPL-04 | Phase 8 | Pending |
| DEPL-05 | Phase 8 | Pending |
| DEPL-06 | Phase 8 | Pending |
| DEPL-07 | Phase 8 | Pending |
| DEPL-08 | Phase 8 | Pending |

**Coverage:**
- v1 requirements: 52 total
- Mapped to phases: 52
- Unmapped: 0

---
*Requirements defined: 2026-02-28*
*Last updated: 2026-02-28 after roadmap creation*
