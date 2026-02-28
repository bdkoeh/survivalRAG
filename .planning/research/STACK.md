# Technology Stack

**Project:** SurvivalRAG
**Researched:** 2026-02-28

## Recommended Stack

### Core RAG Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| LlamaIndex | 0.12.x+ | RAG orchestration, indexing, retrieval pipeline | Purpose-built for document-heavy retrieval. 40% faster document retrieval than LangChain in benchmarks. Lower token overhead (~1.60k vs ~2.40k). 300+ data connectors via LlamaHub. Native Ollama integration via `llama-index-llms-ollama` and `llama-index-embeddings-ollama`. Simpler API for the core use case (retrieve + generate) vs LangChain's more complex chain/agent abstractions. |

**Confidence:** HIGH -- LlamaIndex is the consensus choice for document-centric RAG in 2025-2026. Verified via multiple benchmarks, Docker official RAG guide, and extensive community adoption (44K+ GitHub stars).

**Why not LangChain:** LangChain excels at complex multi-step agent workflows, but SurvivalRAG is a focused retrieve-and-generate system. LangChain introduces unnecessary abstraction overhead (~10ms framework overhead vs ~6ms for LlamaIndex) and higher token usage for this use case. Senior engineers are increasingly avoiding LangChain for simple RAG in favor of LlamaIndex or vanilla Python.

**Why not vanilla Python:** While vanilla Python + direct SDK calls would work, LlamaIndex provides tested chunking, retrieval, and response synthesis patterns that would take significant effort to replicate. The framework overhead is negligible (~6ms) and the abstraction earns its keep for document ingestion pipelines.

### Vector Database

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| ChromaDB | 1.5.x | Vector storage, similarity search, metadata filtering | Embedded mode requires zero configuration -- runs in-process with no separate server. Apache 2.0 license (compatible with MIT/Apache project). 2025 Rust-core rewrite delivers 4x performance improvement. Built-in full-text search + BM25 for hybrid retrieval. Three-tier storage architecture (brute force buffer, HNSW cache, Apache Arrow persistence). Supports metadata filtering for category-scoped queries. Native LlamaIndex integration via `llama-index-vector-stores-chroma`. |

**Confidence:** HIGH -- ChromaDB is the standard embedded vector DB for local/Docker RAG deployments. Version 1.5.2 released Feb 27, 2026. Verified via PyPI, official changelog, and Docker RAG guides.

**Why not Qdrant:** Qdrant is a superior production database with better filtering and horizontal scaling, but it requires running as a separate service. For a Docker-contained knowledge base with a fixed corpus (not billions of vectors), ChromaDB's embedded mode eliminates an entire service and network hop. Qdrant is the right upgrade path if SurvivalRAG ever needs distributed deployment. ChromaDB handles up to ~10M vectors which vastly exceeds Tier 1 content needs.

**Why not FAISS:** FAISS is a library, not a database. No built-in persistence (must manage index save/load), no metadata filtering (critical for category queries), no full-text search. Requires significant engineering to match what ChromaDB provides out of the box. Raw performance advantage is irrelevant at SurvivalRAG's scale.

**Why not pgvector:** Requires running PostgreSQL, adding operational complexity for non-technical Docker users. Overkill for a pre-built, read-heavy knowledge base.

### Embedding Model

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| nomic-embed-text | v1.5 | Document and query embedding | Best accuracy-to-size ratio for local deployment. 86.2% top-5 retrieval accuracy (highest among comparably sized models). Only ~274MB via Ollama. 8192-token context window (handles long document chunks). Apache 2.0 license -- fully open weights, training code, and data. Runs via Ollama (same infrastructure as the LLM). Matryoshka representation learning allows dimension reduction (768 down to 256) if storage becomes a concern. Surpasses OpenAI text-embedding-ada-002 and text-embedding-3-small on retrieval tasks. |

**Confidence:** HIGH -- nomic-embed-text v1.5 is the most recommended local embedding model across multiple 2025-2026 guides. Available directly from Ollama library. Verified via Ollama docs, MTEB benchmarks, and Nomic AI publications.

**Why not mxbai-embed-large:** Higher MTEB score (64.68 vs 53.01 avg) but 1.2GB vs 0.5GB -- more than double the memory for a modest improvement. nomic-embed-text outperforms on retrieval-specific benchmarks which matter more for RAG than aggregate MTEB. The 8192 context window also far exceeds mxbai-embed-large's 512 tokens.

**Why not BGE-M3:** Excellent model with hybrid dense/sparse/multi-vector retrieval, but significantly larger (568M params, ~2GB) and the multi-vector capability adds complexity without clear benefit for a pre-built knowledge base. Good upgrade path if retrieval quality needs improvement.

**Why not domain-specific medical models (MedEIR, PubMedBERT):** These models are not available via Ollama, requiring separate SentenceTransformers infrastructure. They add deployment complexity. nomic-embed-text generalizes well across domains. If retrieval quality testing reveals poor performance on medical terminology, fine-tuning or switching to a medical model becomes a Phase 2 research task.

**Fallback strategy:** If nomic-embed-text underperforms on medical/survival queries during evaluation, upgrade to mxbai-embed-large (1.2GB, higher MTEB scores) or investigate domain-specific models. Build the pipeline to make embedding model swaps easy.

### LLM (Default Bundled Model)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Llama 3.1 8B | Q4_K_M quant | Default response generation model | Most downloaded model on Ollama (108M+ downloads). Strong instruction-following for RAG citation tasks. 8B parameters fits in ~4.7GB VRAM/RAM. Excellent balance of capability and resource requirements. Meta's permissive license allows redistribution. Well-tested with LlamaIndex + Ollama integration. |

**Confidence:** HIGH -- Llama 3.1 8B is the de facto standard for local LLM deployment via Ollama in 2025-2026. Verified via Ollama library stats and multiple deployment guides.

**Why not medical-specific models (Med42-8B, MediChat-Llama3):** SurvivalRAG is a RAG system -- the LLM generates responses grounded in retrieved context, not from parametric knowledge. A strong general-purpose instruction follower that respects context and produces citations is more important than domain-specific medical training. Medical fine-tuned models may actually be worse for RAG because they are more likely to generate from parametric medical knowledge rather than citing retrieved context. The safety-first design (refuse when context is insufficient) requires a model that follows system prompts reliably, which Llama 3.1 8B excels at.

**Why not Phi-3 (3.8B):** Significantly smaller and faster, but weaker at following complex system prompts and producing structured citations. Could be offered as a "lite" option for low-resource deployments.

**Why not Mistral 7B:** Comparable to Llama 3.1 8B but slightly less capable at instruction following. Llama 3.1 has a larger community, more testing, and better Ollama integration.

**LLM-agnostic design:** The system must be configurable to use any Ollama model. The bundled default is for zero-config experience; power users can swap to any model.

### Document Processing Pipeline

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Docling | latest | Primary PDF extraction with layout analysis | Open-source under Linux Foundation (MIT-compatible). Advanced AI-powered layout analysis for complex military manual layouts. Multiple OCR backend support (Tesseract, EasyOCR, RapidOCR). Table structure recognition via TableFormer model. Exports directly to Markdown (ideal for LLM consumption). No AGPL licensing concerns (unlike PyMuPDF). Handles mixed content types (text, tables, figures). |
| Tesseract OCR | 5.x | OCR engine for scanned PDFs | Most mature OCR engine. Supports 100+ languages. CPU-first (no GPU required for document processing). Custom training capability for domain-specific vocabulary. FOSS with Apache 2.0 license. |
| EasyOCR | latest | Fallback OCR for degraded scans | Deep learning-based, ~95% accuracy vs Tesseract's ~90%. Better on noisy/low-quality scans (critical for old military manuals). Can be used selectively on pages where Tesseract fails. |

**Confidence:** MEDIUM -- Docling is relatively newer than PyMuPDF but backed by IBM Research and Linux Foundation. Tesseract and EasyOCR are well-established. The pipeline design (try clean extraction first, OCR as fallback) is standard practice.

**Why not PyMuPDF/PyMuPDF4LLM:** PyMuPDF is technically superior for speed (0.12s markdown extraction) but is licensed AGPL-3.0. This is a viral copyleft license that would require SurvivalRAG (targeting MIT/Apache 2.0 license) to either: (a) release under AGPL, or (b) obtain a commercial license from Artifex. This is a hard blocker for an open-source project targeting permissive licensing. Multiple projects (LangChain, browser-use, gpt-researcher, doctr) have flagged this exact issue.

**Why not Unstructured:** Apache 2.0 license is good, but the free/open-source version produces inconsistent results in 2025 evaluations. The paid hosted version is not suitable for an offline-first project.

**Why not marker-pdf:** Excellent quality (perfect structure preservation) but very slow (~11.3s per document). Good for one-time batch processing but overkill when Docling handles the same task adequately.

### Chunking Strategy

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| LlamaIndex SentenceSplitter | (bundled) | Recursive character splitting baseline | LlamaIndex's built-in recursive splitter. Respects paragraph and sentence boundaries. Configurable chunk size and overlap. Fast and reliable baseline. |
| LlamaIndex SemanticSplitter | (bundled) | Semantic chunking for knowledge base content | Groups semantically related sentences. 70% retrieval accuracy improvement over fixed-size chunking in benchmarks. Better for technical/procedural content where topics shift within sections. |

**Strategy:** Use a hybrid approach. First split by document structure (headings, sections) using Markdown headers from Docling output, then apply semantic chunking within sections. Target 512 tokens per chunk with 50-token overlap. Different content types may need different strategies:
- **Procedures (step-by-step):** Keep complete procedures in single chunks. Do not split mid-procedure.
- **Reference tables:** Preserve table structure as single chunks with metadata.
- **Safety warnings:** Tag as high-priority, never split, include in metadata for retrieval boosting.

**Confidence:** MEDIUM -- Chunking strategy will need empirical tuning during development. The hybrid approach is well-supported by 2025 literature but optimal parameters are domain-specific.

### Web Interface

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| FastAPI | 0.115.x+ | Backend API server | High-performance async Python API. Clean separation between UI and retrieval logic. Supports streaming responses (critical for LLM output). Enables future API consumers (CLI, mobile, Meshtastic). Well-documented, widely adopted. |
| Gradio | 5.x | Chat UI frontend | Built-in ChatInterface component -- production-quality chat UI in minimal code. Uses FastAPI under the hood. Streaming response support. Dark/light mode. Mobile responsive. No frontend build toolchain required (pure Python). Can be embedded in the FastAPI app or run standalone. Simpler than Streamlit for chat-focused UIs. Free hosting via HuggingFace Spaces for demo purposes. |

**Confidence:** HIGH -- FastAPI + Gradio is a proven pattern for Python RAG applications in 2025-2026. Verified via multiple tutorials and production deployments.

**Why not Streamlit:** Streamlit requires a separate process and has poor support for long-running inference tasks. Gradio's ChatInterface is purpose-built for LLM chat and requires less code. Streamlit is better for dashboards; Gradio is better for model interaction.

**Why not Open WebUI:** Open WebUI is feature-rich but designed as a general-purpose Ollama frontend. It would replace SurvivalRAG's custom retrieval pipeline with its own RAG implementation. We need control over the retrieval pipeline (category filtering, citation enforcement, safety prompts). Open WebUI is overkill and would fight the custom RAG logic. Users who want Open WebUI can point it at SurvivalRAG's API.

**Why not a React/Vue frontend:** Adds a JavaScript build toolchain, node_modules, and frontend complexity to a Python project targeting non-technical contributors. Gradio keeps the entire stack in Python.

### CLI Interface

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Typer | 0.15.x+ | CLI framework | Built on Click. Type hints for argument parsing. Auto-generated help. Rich terminal output. Minimal boilerplate. Same author as FastAPI (Sebastian Ramirez). |
| Rich | 13.x+ | Terminal formatting | Markdown rendering in terminal (matches field-manual style). Progress bars for ingestion. Syntax highlighting. Tables for structured output. |

**Confidence:** HIGH -- Typer + Rich is the standard Python CLI stack in 2025-2026.

### Containerization

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Docker + Docker Compose | latest | Container orchestration | Industry standard. Compose enables multi-container (app + Ollama) deployment. GPU passthrough via NVIDIA Container Toolkit. Named volumes for model persistence. Single `docker compose up` for complete deployment. |

**Architecture:** Two-container Docker Compose setup:
1. **survivalrag** container: FastAPI + Gradio + LlamaIndex + ChromaDB (embedded) + pre-built knowledge base
2. **ollama** container: Ollama server with pre-pulled default model (llama3.1:8b + nomic-embed-text)

Shared Docker network for inter-container communication. Named volume for Ollama model persistence across restarts.

**Confidence:** HIGH -- This is the Docker-official pattern for RAG + Ollama deployments, verified via docs.docker.com/guides/rag-ollama/.

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | 2.x | Data validation and settings | Configuration, document metadata schemas, API models |
| python-dotenv | 1.x | Environment configuration | Loading .env for model paths, API ports, Ollama URL |
| httpx | 0.28.x+ | Async HTTP client | Communication with Ollama API |
| pyyaml | 6.x | YAML parsing | Document provenance manifests, configuration files |
| pytest | 8.x | Testing | Retrieval quality testing, integration tests |
| ragas | 0.2.x+ | RAG evaluation | Evaluating retrieval quality, answer faithfulness, citation accuracy |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| RAG Framework | LlamaIndex | LangChain | Higher overhead, more complex API for simple retrieval tasks |
| RAG Framework | LlamaIndex | Haystack | Excellent framework but smaller ecosystem, fewer Ollama-specific integrations |
| RAG Framework | LlamaIndex | Vanilla Python | Too much wheel-reinvention for document ingestion and chunking |
| Vector DB | ChromaDB (embedded) | Qdrant | Requires separate service; overkill for fixed-corpus local deployment |
| Vector DB | ChromaDB (embedded) | FAISS | No persistence, no metadata filtering, no full-text search |
| Vector DB | ChromaDB (embedded) | pgvector | Requires PostgreSQL; adds operational complexity |
| Embedding | nomic-embed-text v1.5 | mxbai-embed-large | 2x memory for modest improvement; shorter context window |
| Embedding | nomic-embed-text v1.5 | BGE-M3 | 4x memory; hybrid retrieval complexity unnecessary for v1 |
| Embedding | nomic-embed-text v1.5 | MedEIR/PubMedBERT | Not on Ollama; requires separate inference infrastructure |
| PDF Extraction | Docling | PyMuPDF | AGPL-3.0 license incompatible with MIT/Apache project |
| PDF Extraction | Docling | Unstructured (free) | Inconsistent results in 2025 evaluations |
| PDF Extraction | Docling | marker-pdf | Too slow for batch processing |
| Web UI | Gradio | Streamlit | Worse for chat interfaces; poor long-running inference support |
| Web UI | Gradio | Open WebUI | Replaces custom RAG pipeline; overkill for focused product |
| Web UI | Gradio | React/Vue | Adds JavaScript toolchain complexity to Python project |
| Default LLM | Llama 3.1 8B | Med42-8B | Medical fine-tuning counterproductive for RAG citation compliance |
| Default LLM | Llama 3.1 8B | Phi-3 3.8B | Weaker instruction following; offer as lite option only |

## Version Pinning Strategy

Pin major versions, allow minor updates:
```
llama-index>=0.12,<0.13
chromadb>=1.5,<2.0
fastapi>=0.115,<1.0
gradio>=5.0,<6.0
docling>=2.0,<3.0
typer>=0.15,<1.0
rich>=13.0,<14.0
pydantic>=2.0,<3.0
ragas>=0.2,<1.0
```

## Installation

```bash
# Core RAG pipeline
pip install llama-index llama-index-llms-ollama llama-index-embeddings-ollama llama-index-vector-stores-chroma chromadb

# Document processing
pip install docling

# Web interface
pip install fastapi gradio uvicorn

# CLI
pip install typer rich

# Configuration and utilities
pip install pydantic python-dotenv pyyaml httpx

# Development and testing
pip install pytest ragas
```

```bash
# Ollama models (run after Ollama is installed)
ollama pull nomic-embed-text:v1.5
ollama pull llama3.1:8b
```

## Hardware Requirements

### Minimum (CPU-only)
- 16GB RAM
- 20GB disk (models + knowledge base)
- Any modern x86_64 CPU

### Recommended
- 16GB+ RAM
- NVIDIA GPU with 8GB+ VRAM (for LLM inference)
- NVMe SSD (for model loading speed)
- 30GB disk

### Notes
- Embedding generation (nomic-embed-text) is fast even on CPU (~3,250 tokens/sec)
- LLM inference is the bottleneck -- GPU dramatically improves response time
- The knowledge base itself is small (< 1GB for Tier 1 content)
- Ollama model files are the largest disk consumers (~5GB for llama3.1:8b)

## Sources

- [Docker Official RAG + Ollama Guide](https://docs.docker.com/guides/rag-ollama/)
- [Ollama Docker Documentation](https://docs.ollama.com/docker)
- [Ollama Embedding Models Blog](https://ollama.com/blog/embedding-models)
- [nomic-embed-text on Ollama](https://ollama.com/library/nomic-embed-text)
- [mxbai-embed-large on Ollama](https://ollama.com/library/mxbai-embed-large)
- [ChromaDB Official Site](https://www.trychroma.com/)
- [ChromaDB 1.0 Performance Announcement](https://www.trychroma.com/project/1.0.0)
- [ChromaDB PyPI](https://pypi.org/project/chromadb/)
- [LlamaIndex Documentation](https://docs.llamaindex.ai/)
- [Docling Official Site](https://www.docling.ai/)
- [Best Open-Source Embedding Models Benchmarked](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/)
- [15 Best Open-Source RAG Frameworks 2026](https://www.firecrawl.dev/blog/best-open-source-rag-frameworks)
- [RAG Framework Benchmarks (Pathway)](https://pathway.com/rag-frameworks)
- [Vector Database Comparison 2025 (LiquidMetal AI)](https://liquidmetal.ai/casesAndBlogs/vector-comparison/)
- [Best Python PDF Parsers 2026 (Unstract)](https://unstract.com/blog/evaluating-python-pdf-to-text-libraries/)
- [Open WebUI Features](https://docs.openwebui.com/features/)
- [Chunking Strategies for RAG (Databricks)](https://community.databricks.com/t5/technical-blog/the-ultimate-guide-to-chunking-strategies-for-rag-applications/ba-p/113089)
- [MedEmbed: Fine-Tuned Medical Embedding Models](https://huggingface.co/blog/abhinand/medembed-finetuned-embedding-models-for-medical-ir)
- [Ollama Docker Compose GPU Guide (DEV Community)](https://dev.to/ajeetraina/running-ollama-with-docker-compose-and-gpus-lkn)
