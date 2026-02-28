# Architecture Patterns

**Domain:** Pre-built RAG knowledge base for survival/medical content, shipped via Docker
**Researched:** 2026-02-28

## Recommended Architecture

SurvivalRAG follows the established multi-container RAG architecture pattern: a Docker Compose stack with a FastAPI backend orchestrating retrieval and generation, a ChromaDB vector database for pre-built embeddings, Ollama for LLM inference and embedding generation, and a lightweight web frontend for user interaction.

The key architectural distinction from a typical RAG system is that SurvivalRAG ships with a **pre-built knowledge base**. The document processing pipeline runs at build time (by project maintainers), not at runtime (by end users). Users receive a Docker image with embeddings and metadata already loaded. This simplifies the runtime architecture significantly while pushing complexity into the build pipeline.

### High-Level Overview

```
+--------------------------------------------------+
|              Docker Compose Network               |
|                                                   |
|  +--------------------------------------------+  |
|  |         survivalrag container               |  |
|  |                                             |  |
|  |  +--------+    +----------+    +---------+  |  |
|  |  | Web UI |<-->| FastAPI  |<-->|Retrieval|  |  |
|  |  | (static|    | Backend  |    | Engine  |  |  |
|  |  | HTML/JS|    +----------+    +----+----+  |  |
|  |  +--------+         |              |        |  |
|  |                +----+----+    +----+------+ |  |
|  |                |  Typer  |    |  ChromaDB | |  |
|  |                |   CLI   |    | (embedded)| |  |
|  |                +---------+    +-----------+ |  |
|  +--------------------------------------------+  |
|                        |                          |
|                  HTTP (port 11434)                 |
|                        |                          |
|  +--------------------------------------------+  |
|  |           ollama container                  |  |
|  |                                             |  |
|  |  +------------------+  +----------------+   |  |
|  |  | llama3.2:3b or   |  | nomic-embed-   |   |  |
|  |  | llama3.1:8b      |  | text           |   |  |
|  |  | (generation)     |  | (embedding)    |   |  |
|  |  +------------------+  +----------------+   |  |
|  |           [GPU passthrough if available]     |  |
|  +--------------------------------------------+  |
+--------------------------------------------------+
```

```
BUILD-TIME PIPELINE (maintainer-only, not shipped to users):

  Source PDFs/HTML
       |
       v
  +------------------+
  | Document Ingestion|
  | - PyMuPDF4LLM     |
  | - OCR (Tesseract) |
  | - HTML scraping    |
  +--------+----------+
           |
           v
  +------------------+
  | Text Processing   |
  | - Cleaning/QA     |
  | - Content typing  |
  | - Safety tagging  |
  +--------+----------+
           |
           v
  +------------------+
  | Chunking Engine   |
  | - Recursive split |
  | - Content-aware   |
  | - Metadata attach |
  +--------+----------+
           |
           v
  +------------------+
  | Embedding + Index |
  | - nomic-embed-text|
  | - ChromaDB ingest |
  | - Provenance store|
  +--------+----------+
           |
           v
  ChromaDB data directory
  (copied into Docker image)
```

### Why Two Containers, Not Three or Four

The standard Docker RAG stack uses 3-4 containers (frontend, backend, vector DB, Ollama). SurvivalRAG simplifies to **two containers** because:

1. **ChromaDB runs embedded** (in-process within the FastAPI backend) rather than as a separate service. SurvivalRAG's Tier 1 content produces thousands to tens of thousands of chunks, not millions. ChromaDB's embedded/persistent mode is designed for exactly this scale and eliminates network latency and an entire container.

2. **The web UI is static HTML/JS** served directly by FastAPI as static files. No separate frontend container or build step needed. The chat interface is a single page with a text input, response area, and citation panel -- this does not warrant a framework.

3. **Ollama must be separate** because it manages its own model lifecycle, GPU allocation, and memory. Mixing it with the application creates coupling and complicates resource management. Users can optionally point the app at an external Ollama instance running on a different machine.

## Component Boundaries

### Runtime Components (shipped to users)

| Component | Responsibility | Communicates With | Technology |
|-----------|---------------|-------------------|------------|
| **Web Chat UI** | Browser-based chat interface. Renders markdown responses with citations. Category filter selector. | FastAPI Backend (HTTP/SSE) | Static HTML/CSS/JS (no framework) |
| **FastAPI Backend** | Request routing, response streaming, configuration management. Exposes REST API for CLI and future integrations. Hosts the retrieval engine and ChromaDB in-process. | ChromaDB (direct Python calls), Ollama (HTTP API), Web UI / CLI (HTTP) |  Python, FastAPI, uvicorn |
| **Retrieval Engine** | Query embedding, vector similarity search, category filtering, context assembly, prompt construction, citation injection, safety guardrails. | ChromaDB (direct), Ollama (HTTP) | Python module within FastAPI backend |
| **ChromaDB (embedded)** | Vector storage, similarity search, metadata filtering. Runs in-process with persistent storage on disk. | Retrieval Engine (direct function calls) | ChromaDB PersistentClient |
| **Typer CLI** | Command-line query interface. Formats responses for terminal output. | FastAPI Backend (HTTP) | Python, Typer |
| **Ollama (separate container)** | LLM inference and embedding generation. GPU acceleration when available. | FastAPI Backend (HTTP API on port 11434) | Ollama Docker image |

### Build-Time Components (maintainer tooling, not shipped)

| Component | Responsibility | Communicates With | Technology |
|-----------|---------------|-------------------|------------|
| **Document Ingestion** | Extract text from PDFs (native + OCR), HTML, text files | Text Processing pipeline | PyMuPDF4LLM, Tesseract OCR |
| **Text Processing** | Clean extracted text, classify content types, tag safety warnings | Chunking Engine | Python scripts |
| **Chunking Engine** | Split documents into retrieval-optimized chunks with metadata | Embedding pipeline | Python (recursive character splitting) |
| **Embedding Pipeline** | Generate embeddings, load into ChromaDB, create provenance manifest | ChromaDB, Ollama (for embedding) | Python scripts |
| **Quality Assurance** | Validate retrieval accuracy with test queries, check OCR quality | All build components | Python test suite |
| **Provenance Tracker** | Record source URL, license, distribution statement, verification date per document | Embedding pipeline, manifest file | Python, YAML manifest |

## Data Flow

### Query Flow (Runtime)

```
1. User types query in Web UI or CLI
   |
2. Frontend sends POST /api/query to FastAPI
   Body: { query: "how to purify water", category: "water" (optional) }
   |
3. FastAPI: Query Preprocessing
   - Validate input
   - Extract category filter if present
   |
4. FastAPI -> Ollama: Generate query embedding
   POST http://ollama:11434/api/embeddings
   Body: { model: "nomic-embed-text", prompt: "search_query: how to purify water" }
   Returns: 768-dimension float vector
   |
5. FastAPI -> ChromaDB: Vector similarity search (in-process)
   collection.query(
     query_embeddings=[vector],
     n_results=20,
     where={"category": "water"}  # if category filter provided
   )
   Returns: top 20 chunks with text, metadata, distances
   |
6. FastAPI: Relevance filtering
   - Discard chunks below similarity threshold
   - If no chunks pass threshold: return "insufficient context" immediately
   - Select top 5 most relevant chunks
   |
7. FastAPI: Prompt Assembly
   - System prompt: field-manual style, cite sources, refuse if insufficient
   - Context: top 5 chunks with source metadata
   - Safety: include any safety warnings from chunk metadata
   - User query appended
   |
8. FastAPI -> Ollama: Generate response
   POST http://ollama:11434/api/chat
   Body: { model: "llama3.2:3b", messages: [...], stream: true }
   Returns: streamed token response
   |
9. FastAPI: Post-processing
   - Verify citations reference actual retrieved sources
   - Format source references
   - Attach provenance data to citations
   |
10. FastAPI -> Frontend: Stream response
    SSE stream of tokens + final citation block
```

### Document Processing Flow (Build-Time)

```
1. Source Document Acquisition
   - Download PDF from verified public domain source
   - Record provenance: URL, license, distribution statement, date
   |
2. License Verification
   - Check document-level distribution statement
   - Ambiguous = exclude (conservative default)
   - Log verification in provenance manifest
   |
3. Text Extraction
   - PyMuPDF4LLM: native text extraction with markdown output
   - If page has < threshold text density: apply OCR via Tesseract
   - Hybrid strategy: analyze pages, OCR only where needed
   - Output: markdown text with page numbers preserved
   |
4. Text Cleaning
   - Remove headers/footers, page numbers, watermarks
   - Fix OCR artifacts (common in scanned military PDFs)
   - Normalize whitespace, fix encoding
   - Manual review flag for low-confidence OCR pages
   |
5. Content Classification
   - Tag each section with content_type:
     * "procedure" - step-by-step instructions
     * "reference_table" - tabular data
     * "safety_warning" - critical safety information
     * "general" - descriptive/explanatory text
   - Tag with category: "medical", "water", "shelter", "fire",
     "food", "navigation", "signaling", "tools", "first_aid"
   |
6. Chunking (content-type-aware)
   - Procedures: chunk at procedure boundaries, never split steps
   - Reference tables: keep table + header as single chunk
   - Safety warnings: keep warning intact, duplicate into related chunks
   - General text: recursive character split, 512 tokens, 50-token overlap
   |
7. Metadata Attachment (per chunk)
   {
     "source_document": "FM 3-05.70",
     "source_title": "Survival",
     "page_number": 42,
     "section_header": "Water Purification Methods",
     "content_type": "procedure",
     "category": "water",
     "has_safety_warning": true,
     "safety_warning_text": "WARNING: Iodine purification is not...",
     "source_url": "https://...",
     "license": "public_domain_us_gov",
     "distribution_statement": "Distribution A: Approved for public release",
     "verification_date": "2026-02-28",
     "chunk_index": 3,
     "total_chunks_in_section": 7
   }
   |
8. Embedding Generation
   - Run each chunk through nomic-embed-text via Ollama
   - Store embedding + text + metadata in ChromaDB
   |
9. Quality Validation
   - Run test query suite against built knowledge base
   - Verify retrieval accuracy for medical terminology
   - Check safety warnings surface for dangerous procedures
   - Validate citation metadata is complete
   |
10. Export
    - ChromaDB data directory copied into Docker image at build
    - Provenance manifest bundled alongside
```

## Content Type Handling Strategy

Different content types in survival/medical documents require different chunking and retrieval strategies. This is one of the most important architectural decisions, and research confirms that "one chunk size fits all" is a common source of RAG failure.

### Procedures (Step-by-Step Instructions)

Examples: "How to apply a tourniquet", "Water purification steps", "Building a debris shelter"

**Chunking rule:** Never split a procedure mid-step. Chunk at procedure boundaries. If a procedure is short (under 512 tokens), keep it as a single chunk. If long, split between logical step groups but include the procedure title and any preceding safety warnings in each chunk.

**Metadata:** `content_type: "procedure"`, include step range (e.g., "steps 1-5 of 12").

**Retrieval benefit:** Complete procedures are returned, not fragments. Users get actionable step sequences.

### Reference Tables

Examples: Edible plant identification tables, medication dosage charts, signal code tables

**Chunking rule:** Keep the entire table as one chunk, including its header/title and any footnotes. If a table exceeds the chunk size limit, split by logical row groups but repeat the header row and table title in each chunk.

**Metadata:** `content_type: "reference_table"`, include table title.

**Retrieval benefit:** Tables are meaningless without headers. This ensures context is always present.

### Safety Warnings

Examples: Drug interaction warnings, poisonous plant warnings, hypothermia danger signs

**Chunking rule:** Safety warnings are never stripped, summarized, or separated from their context. A safety warning chunk includes: (1) the warning itself, (2) what it applies to, and (3) the source citation. Additionally, safety warnings are **duplicated as metadata** on related chunks so they surface even when the warning chunk itself is not retrieved.

**Metadata:** `content_type: "safety_warning"`, `has_safety_warning: true` on related chunks, `safety_warning_text` field carries the warning text.

**Retrieval benefit:** Safety information surfaces whether the user queries the warning directly or queries the related procedure/topic. A water purification query returns both the procedure AND the safety warning about Cryptosporidium resistance to iodine.

### General Descriptive Text

Examples: Background on survival psychology, terrain descriptions, general medical knowledge

**Chunking rule:** Standard recursive character splitting. 512 tokens with 50-token overlap. Split on paragraph boundaries first, then sentences.

**Metadata:** `content_type: "general"`.

## Patterns to Follow

### Pattern 1: Safety-First Response Generation

**What:** The system prompt enforces three safety behaviors: (1) always cite sources, (2) preserve safety warnings from source material, (3) explicitly refuse when retrieved context is insufficient rather than generating from parametric knowledge.

**When:** Every query. This is the core safety contract.

**Why:** Small LLMs (3B-8B parameters) hallucinate medical procedures. A 2025 radiology study found RAG eliminated hallucinations (0% vs 8%) in a local Llama 3.2-11B model. But the system prompt must explicitly prohibit fallback to parametric knowledge, because models exhibit "parametric knowledge bias" -- they may ignore retrieved context when internal training weights strongly contradict it.

**Implementation:**

```python
SYSTEM_PROMPT = """You are a survival and field medicine reference assistant.
You MUST follow these rules strictly:

1. ONLY use information from the provided context documents.
2. CITE every claim with [Source: document_name, page X].
3. If the context does not contain sufficient information to answer,
   respond: "I don't have enough information in my sources to answer
   this reliably. Please consult a qualified professional."
4. PRESERVE all safety warnings from source material verbatim.
5. Format responses as concise, actionable steps (field-manual style):
   - Numbered steps for procedures
   - Bullet points for lists
   - Bold for critical warnings
6. NEVER provide medical diagnoses.
7. NEVER guess or extrapolate beyond what the sources explicitly state.

Context documents:
{retrieved_context}

User question: {query}
"""
```

### Pattern 2: Embedded Vector Database

**What:** Run ChromaDB in-process within the application container rather than as a separate service.

**When:** Fixed-corpus, read-heavy workloads where the entire index fits in memory. SurvivalRAG's Tier 1 content will produce thousands of chunks, not millions.

**Why:** Eliminates network latency, reduces container count, simplifies deployment. ChromaDB's PersistentClient mode is designed for exactly this use case. The 2025 Rust rewrite delivers 4x faster queries. At 50,000 chunks with 768 dimensions, storage is approximately 150 MB -- trivial.

**Example:**

```python
import chromadb

# Persistent embedded storage -- no server needed
db = chromadb.PersistentClient(path="/app/chroma_db")
collection = db.get_or_create_collection(
    name="survivalrag",
    metadata={"hnsw:space": "cosine"}
)
```

### Pattern 3: Two-Container Docker Compose

**What:** Separate the application logic from the LLM inference server.

**When:** Always, for this project. Ollama manages its own model lifecycle, GPU allocation, and memory.

**Why:** Independent scaling (users can run Ollama on a different machine). Clean separation of concerns. Ollama container can be replaced with any OpenAI-compatible endpoint. Model persistence via named volume survives container rebuilds.

**Example:**

```yaml
services:
  survivalrag:
    build: .
    ports:
      - "8080:8080"   # Web UI + API
    volumes:
      - ./chroma_db:/app/chroma_db  # Pre-built knowledge base
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - DEFAULT_MODEL=llama3.2:3b
      - EMBED_MODEL=nomic-embed-text
    depends_on:
      ollama:
        condition: service_healthy

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  ollama_data:
```

### Pattern 4: Category-Filtered Retrieval

**What:** Pre-filter vector search results by category metadata before similarity ranking.

**When:** User selects a category (medical, water, shelter, etc.) or system auto-detects topic from query.

**Why:** Mixed-domain content without filtering produces noisy results. A water purification query should not return wound care procedures. ChromaDB supports `where` filters on metadata natively, applied before vector search for efficiency.

**Example:**

```python
def retrieve_chunks(
    query_embedding: list[float],
    category: str | None = None,
    n_results: int = 20
) -> list:
    where_filter = None
    if category:
        where_filter = {"category": category}

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where_filter,
        include=["documents", "metadatas", "distances"]
    )
    return results
```

### Pattern 5: Streaming Response with Citations

**What:** Stream LLM responses token-by-token to the UI, then append a citation block after the response completes.

**When:** Always for the web UI. CLI can optionally buffer.

**Why:** LLM generation on local hardware (especially CPU) can take 10-60 seconds. Without streaming, the user sees a blank screen. Streaming reduces perceived latency and user abandonment.

**Example:**

```python
@app.post("/api/query")
async def query(request: QueryRequest):
    chunks = retrieve_chunks(request.query, request.category)
    prompt = build_prompt(request.query, chunks)

    async def generate():
        async for token in ollama_stream(prompt):
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        # After generation, send structured citations
        citations = format_citations(chunks)
        yield f"data: {json.dumps({'type': 'citations', 'sources': citations})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

### Pattern 6: Build-Time Ingestion, Runtime Read-Only

**What:** All document processing, chunking, and embedding happens at build time. The runtime application only reads from the pre-built ChromaDB index.

**When:** Always for v1. The knowledge base is fixed at build.

**Why:** Eliminates the ingestion pipeline from the runtime container (simpler, smaller, faster startup). Ensures reproducible knowledge base across all installations. No need for Tesseract/PyMuPDF at runtime. Users get identical content regardless of their hardware.

**Implementation:** The build pipeline is a separate set of Python scripts that run during Docker image creation or as a pre-release step. The output (ChromaDB directory) is copied into the Docker image.

### Pattern 7: Provenance Manifest for Every Document

**What:** A YAML manifest file for each source document recording its provenance chain.

**When:** Every document added to the knowledge base.

**Why:** Legal requirement (public domain verification). User trust (answers cite verifiable sources). Audit trail (when was this last verified?).

**Example:**

```yaml
# data/manifests/fm-3-05-70.yaml
document_id: fm-3-05-70
title: "FM 3-05.70 Survival"
source_url: "https://..."
license: "public_domain_us_gov"
distribution_statement: "Distribution A: Approved for public release"
verification_date: "2026-02-28"
verified_by: "maintainer_handle"
pages: 676
ocr_required: true
ocr_quality: "good"  # good | fair | poor_needs_review
processing_notes: "Pages 45-67 required OCR. Manual cleanup on drug tables."
categories:
  - shelter
  - water
  - food
  - fire
  - navigation
  - medical
  - tools
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Agent Loops for Simple RAG

**What:** Using LangChain agents or multi-step reasoning loops that make multiple LLM inference calls per query.

**Why bad:** On small local LLMs (3B-8B parameters), agent loops are slow (multiple inference passes), unreliable (models make poor tool-use decisions), and unpredictable (different execution paths for similar queries). A simple retrieve-then-generate pipeline is 3-5x faster and produces more consistent results.

**Instead:** Single-pass pipeline: embed query, retrieve chunks, assemble context, generate response. One LLM inference call per query.

### Anti-Pattern 2: Shipping the Ingestion Pipeline to Users

**What:** Including document processing, OCR, and embedding generation in the user-facing Docker image.

**Why bad:** Massively increases image size. Introduces Tesseract, PyMuPDF, and other build-time dependencies into the runtime. Confuses users who do not need to process documents. Increases attack surface.

**Instead:** Keep the build pipeline in a separate `tools/` or `scripts/` directory. Ship only the pre-built ChromaDB data.

### Anti-Pattern 3: Using LLM Parametric Knowledge as Fallback

**What:** When retrieved context is insufficient, allowing the LLM to answer from its training data.

**Why bad:** Small LLMs hallucinate medical procedures. The entire value proposition of SurvivalRAG is grounded, cited answers. Falling back to parametric knowledge breaks this safety contract. Research shows models exhibit "parametric knowledge bias" where they override RAG context with internal (potentially wrong) knowledge.

**Instead:** Explicitly instruct the model to refuse when context is insufficient. Apply a relevance threshold on retrieved chunks. If no chunks score above threshold, return "insufficient context" before even calling the LLM.

### Anti-Pattern 4: Splitting Safety Warnings from Context

**What:** Chunking a safety warning separately from the procedure it applies to.

**Why bad:** A user asking "how to purify water with iodine" might get the procedure chunk but not the "WARNING: Iodine purification is not effective against Cryptosporidium" chunk. This is a genuine safety failure for a survival/medical knowledge base.

**Instead:** Duplicate safety warnings into related chunk metadata. Tag related chunks with `has_safety_warning: true` and include the warning text. The prompt builder always includes surfaced safety warnings.

### Anti-Pattern 5: Trusting LLM Output Without Citation Verification

**What:** Passing retrieved context to the LLM and trusting the response contains valid citations.

**Why bad:** Small LLMs fabricate citations that look real but reference documents that do not exist. They may ignore retrieved context entirely. For medical/survival content, this is dangerous.

**Instead:** Post-process responses to verify cited source names match retrieved chunks. Flag responses where citations reference unknown documents. Consider a lightweight verification step that checks cited document names against the provenance manifest.

### Anti-Pattern 6: One Chunk Size for All Content Types

**What:** Using the same 512-token split for procedures, tables, warnings, and narrative.

**Why bad:** A 20-step medical procedure gets split into fragments where step 14 is separated from step 1. A reference table gets split mid-row, losing headers. A drug interaction warning gets separated from the drug it warns about. Research confirms this is the most common source of RAG failure in domain-specific applications.

**Instead:** Content-type-aware chunking as described in the Content Type Handling Strategy section.

## Scalability Considerations

| Concern | Tier 1 (~100 docs, ~10-50K chunks) | Tier 2 (~500 docs, ~100K chunks) | Tier 3 (~2000+ docs, ~500K+ chunks) |
|---------|-------------------------------------|----------------------------------|--------------------------------------|
| **Vector DB** | ChromaDB embedded, <200MB. Handles trivially. | <500MB. Still fine embedded. | 1-2GB. May need Qdrant as separate service. |
| **Embedding time (build)** | Minutes on CPU. | 30-60 min on CPU. | Hours on CPU; GPU recommended. |
| **Query latency** | <100ms retrieval + LLM generation. | Same. Metadata filtering keeps it fast. | May need HNSW parameter tuning. |
| **Docker image size** | ~500MB (app) + ~5GB (Ollama + models). | Same. KB data still manageable. | KB data reaches 2-3GB. |
| **Memory at runtime** | ~2GB (app + ChromaDB) + ~4-5GB (Ollama model). | ~3GB + ~5GB = ~8GB. | ~5GB + ~5GB = ~10GB. 16GB min. |

**Note:** SurvivalRAG v1 targets personal/household deployment on commodity hardware. Multi-user scaling is not a v1 concern.

## Suggested Build Order (Dependencies)

The components have clear dependency relationships that dictate build order:

```
Phase 1: Document Pipeline (Foundation)
  1. Provenance manifest format + license verification process
  2. Document ingestion (PyMuPDF4LLM + OCR)
  3. Text cleaning and content classification
  4. Chunking engine with content-type awareness
  5. Quality checks for extracted text
     Dependencies: None (standalone build tools)
     WHY FIRST: If OCR produces garbage, everything downstream fails.
     This is the critical path.

Phase 2: Knowledge Base Assembly
  6. ChromaDB schema design + metadata structure
  7. Embedding pipeline (Ollama nomic-embed-text -> ChromaDB)
  8. Process Tier 1 documents through full pipeline
  9. Retrieval quality test suite (golden queries)
     Dependencies: Phase 1 complete
     WHY SECOND: Need populated data to build anything on top of.

Phase 3: Retrieval + Generation Backend
  10. FastAPI backend skeleton with config management
  11. Query embedding + ChromaDB retrieval
  12. Category-filtered search
  13. Safety-first prompt assembly
  14. Ollama LLM integration + response streaming
  15. Citation formatting + verification
      Dependencies: Phase 2 (needs populated ChromaDB)
      WHY THIRD: Core value proposition. Most architectural risk here.

Phase 4: User Interfaces
  16. Web chat UI (static HTML/JS/CSS with SSE streaming)
  17. CLI client (Typer)
  18. Citation display with source attribution
      Dependencies: Phase 3 (needs working API)
      WHY FOURTH: Skin on top of working backend.

Phase 5: Docker Packaging + Deployment
  19. Docker Compose configuration (two containers)
  20. Auto-model-pull entrypoint script for Ollama
  21. Pre-built knowledge base volume packaging
  22. First-run health checks and status display
  23. README with deployment instructions
      Dependencies: Phase 4 (needs all components)
      WHY LAST: Everything must work before packaging.
```

**Critical path:** Document ingestion quality (Phase 1) determines everything downstream. If OCR produces garbage text, embeddings will be useless, retrieval will fail, and responses will be wrong. Invest heavily in Phase 1 quality assurance before proceeding.

**Highest architectural risk:** Phase 3, specifically the interaction between small LLM behavior, prompt engineering for citation enforcement, and safety guardrails. This needs extensive testing with real survival/medical queries.

## Directory Structure

```
survivalrag/
+-- docker-compose.yml          # Two-container orchestration
+-- Dockerfile                  # Application container
+-- pyproject.toml              # Python dependencies
+-- src/
|   +-- survivalrag/
|       +-- __init__.py
|       +-- config.py           # Settings (Pydantic BaseSettings)
|       +-- main.py             # FastAPI app, static file serving
|       +-- cli.py              # Typer CLI
|       +-- pipeline/
|       |   +-- __init__.py
|       |   +-- retriever.py    # ChromaDB query + category filtering
|       |   +-- generator.py    # Prompt assembly + Ollama streaming
|       |   +-- citations.py    # Citation extraction and verification
|       |   +-- safety.py       # Safety warning surfacing logic
|       +-- ui/
|           +-- static/
|               +-- index.html  # Chat interface
|               +-- style.css
|               +-- app.js      # SSE client, citation rendering
+-- tools/                      # Build-time only (not in runtime image)
|   +-- ingest.py               # Document ingestion (PyMuPDF4LLM)
|   +-- chunk.py                # Content-type-aware chunking
|   +-- embed.py                # Embedding via Ollama -> ChromaDB
|   +-- classify.py             # Content type + category classification
|   +-- validate.py             # Retrieval quality validation
+-- data/
|   +-- sources/                # Raw source PDFs (not in Docker image)
|   +-- manifests/              # Provenance YAML per document
|   +-- chroma_db/              # Pre-built ChromaDB (shipped in image)
+-- tests/
|   +-- test_retrieval.py       # Retrieval quality tests
|   +-- test_citations.py       # Citation verification tests
|   +-- test_safety.py          # Safety warning surfacing tests
|   +-- test_refusal.py         # "Refuse when insufficient" tests
|   +-- golden_queries.yaml     # Test queries with expected results
+-- scripts/
    +-- pull_models.sh          # Pull Ollama models for first run
    +-- healthcheck.sh          # Container health check
```

## Technology Selection Rationale

### ChromaDB (Embedded) over Qdrant or Milvus

ChromaDB is the right choice for v1:

1. **Simplest deployment** -- Apache 2.0 license, PersistentClient runs in-process, zero server configuration. Qdrant and Milvus are more powerful but add operational complexity inappropriate for a "docker pull and run" product.
2. **Sufficient scale** -- Tier 1 content is estimated at 10,000-50,000 chunks. ChromaDB handles this trivially. Production concerns start at 50M+ vectors.
3. **Native metadata filtering** -- `where` filters on metadata enable category-scoped queries without additional infrastructure.
4. **Python-native** -- No gRPC/REST complexity; direct function calls from FastAPI.
5. **2025 Rust rewrite** -- 4x performance improvement. ~20ms median search latency at 100K vectors.

**Upgrade path:** If SurvivalRAG grows beyond Tier 2, Qdrant is the natural step up (also Docker-friendly, Rust-based, production-grade filtering).

### FastAPI over Flask or Django

FastAPI because: async-native (critical for streaming LLM responses), automatic OpenAPI docs for API consumers, dominant in the RAG ecosystem, and lightweight.

### Static HTML/JS over React, Streamlit, or Gradio

For v1, a simple static web page with vanilla JavaScript:

1. **Zero build step** -- No node_modules, webpack, or npm. Files served directly by FastAPI.
2. **No Python UI dependency** -- Streamlit re-executes entire scripts on every interaction. Gradio adds heavyweight dependencies. Neither is appropriate for a simple chat interface.
3. **React is overkill** -- A chat interface needs a text input, response area with streaming, and citation panel. This does not warrant a framework or build pipeline.
4. **SSE is native** -- `EventSource` in vanilla JS handles server-sent event streams perfectly.

**Upgrade path:** If the UI grows significantly (settings, document browser), consider Alpine.js or Preact.

### nomic-embed-text for Embeddings

1. **Available through Ollama** -- Same infrastructure as the LLM. No additional embedding service.
2. **Strong on medical content** -- Research (Khodadad et al., July 2025) found nomic-embed-text outperforms most dedicated medical embedding models.
3. **768 dimensions, 8192 token context** -- Good balance of expressiveness and storage. Long context handles larger chunks.
4. **Small footprint** -- ~0.5 GB memory, fast inference even on CPU.

### Recursive Character Splitting as Default Chunking

1. **Benchmarked winner** -- Vecta's February 2026 benchmark placed recursive 512-token splitting first at 69% accuracy, ahead of semantic chunking at 54%.
2. **Simple and debuggable** -- No ML models required for boundary detection.
3. **Enhanced, not replaced** -- Augmented with content-type-aware rules (preserve procedures, tables, safety warnings) rather than replaced by a complex strategy.

### PyMuPDF4LLM over Docling or Unstructured for PDF Extraction

1. **Markdown output optimized for LLM/RAG** -- Direct markdown extraction in benchmarks achieved 0.12s per document with excellent quality.
2. **Hybrid OCR strategy** -- Analyze pages, apply Tesseract OCR only where needed (scanned pages). Native text extraction is 1000x faster than OCR.
3. **Mature and reliable** -- PyMuPDF is well-established. Unstructured has reported quality regressions in 2025. Docling uses AI models (heavier dependencies).

## Sources

- [Docker Official RAG + Ollama Guide](https://docs.docker.com/guides/rag-ollama/)
- [Ollama Embedding Models Blog](https://ollama.com/blog/embedding-models)
- [nomic-embed-text on Ollama](https://ollama.com/library/nomic-embed-text)
- [Khodadad et al., "Towards Domain Specification of Embedding Models in Medicine" (July 2025)](https://arxiv.org/abs/2507.19407)
- [Vecta Chunking Benchmark (February 2026) via LangCopilot](https://langcopilot.com/posts/2025-10-11-document-chunking-for-rag-practical-guide)
- [Tensorlake, "Citation-Aware RAG"](https://www.tensorlake.ai/blog/rag-citations)
- [Particula, "How to Make My RAG Agent Cite Sources Correctly"](https://particula.tech/blog/fix-rag-citations)
- [PyMuPDF4LLM Documentation](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/)
- [RAG Docker PoC on GitHub](https://github.com/myesua/rag-docker-poc)
- [Collabnix, "Building RAG Applications with Ollama and Python"](https://collabnix.com/building-rag-applications-with-ollama-and-python-complete-2025-tutorial/)
- [MedRAG Toolkit on GitHub](https://github.com/Teddy-XiongGZ/MedRAG)
- [RAG Hallucination Mitigation in Radiology (PMC 2025)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12223273/)
- [Onidel Cloud, "Production RAG Stack Tutorial (2025)"](https://onidel.com/deploy-rag-stack-ubuntu-vps/)
- [LiquidMetal AI, "Vector Database Comparison 2025"](https://liquidmetal.ai/casesAndBlogs/vector-comparison/)
- [Firecrawl, "Best Chunking Strategies for RAG in 2025"](https://www.firecrawl.dev/blog/best-chunking-strategies-rag)
- [Sarthak AI, "Improve Your RAG Accuracy With Smarter Chunking"](https://sarthakai.substack.com/p/improve-your-rag-accuracy-with-a)
- [Dell InfoHub, "Chunk Twice, Retrieve Once: RAG Chunking Strategies for Different Content Types"](https://infohub.delltechnologies.com/en-uk/p/chunk-twice-retrieve-once-rag-chunking-strategies-optimized-for-different-content-types/)
- [Neo4j, "Graph-based Metadata Filtering for Vector Search in RAG"](https://neo4j.com/blog/developer/graph-metadata-filtering-vector-search-rag/)
- [CodeSignal, "Metadata-Based Filtering in RAG Systems"](https://codesignal.com/learn/courses/scaling-up-rag-with-vector-databases/lessons/metadata-based-filtering-in-rag-systems)
- [Analytics Vidhya, "Top 7 Rerankers for RAG"](https://www.analyticsvidhya.com/blog/2025/06/top-rerankers-for-rag/)
- [Latenode, "LangChain vs LlamaIndex 2025 Comparison"](https://latenode.com/blog/platform-comparisons-alternatives/automation-platform-comparisons/langchain-vs-llamaindex-2025-complete-rag-framework-comparison)
