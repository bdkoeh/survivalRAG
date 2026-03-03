# Phase 8: Docker Packaging & Deployment - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Anyone can `docker compose up` and have a fully functional, offline-capable survival knowledge base — zero configuration, zero external dependencies after initial pull. Two containers: application (FastAPI + Gradio + ChromaDB embedded) and Ollama with pre-baked models. The system must work completely offline from the moment the image is built.

</domain>

<decisions>
## Implementation Decisions

### Data bundling strategy
- Pre-built ChromaDB vector store and processed chunks baked into the app Docker image — no embedding or processing step on first run
- Source PDFs bundled in the image so citation click-through links work out of the box
- Data is ephemeral (lives in the container layer, no named volumes) — acceptable since the knowledge base is immutable
- Knowledge base is read-only: curated content only, no user-added documents

### First-run experience
- Ollama models (Llama 3.1 8B + nomic-embed-text) must be baked into a custom Ollama Docker image — users will NOT have internet access to pull models
- This is a hard constraint: the system must be fully offline from the moment images are available, no model downloads at runtime
- App container uses health check gating: waits for Ollama to be ready, logs progress ("Waiting for Ollama...", "Ready! Open http://localhost:8080")
- Docker health checks report unhealthy until all components are initialized
- Web UI exposed on port 8080 by default

### Configuration surface
- External Ollama instance supported via OLLAMA_HOST env var — power users can point to a GPU machine on the LAN and skip the bundled Ollama container
- LLM model is swappable via SURVIVALRAG_MODEL env var — default is bundled Llama 3.1 8B, users responsible for model availability if they change it
- Both web UI and CLI available in the container — `docker exec` for CLI access
- Ship `.env.example` with all SURVIVALRAG_* variables commented out with defaults, referenced from README
- Env vars use existing SURVIVALRAG_* prefix convention from the codebase

### Image & build approach
- CPU-only default docker-compose.yml — works on any machine without GPU drivers
- GPU support via separate docker-compose.gpu.yml override or documented override snippet for NVIDIA GPU passthrough
- Multi-arch builds: x86_64 (AMD64) and ARM64 — covers M-series Macs and Raspberry Pi
- Local build only — users clone repo and `docker compose build`, no registry publishing
- Large image size acceptable (~8-10GB total) given bundled LLM models (~5GB) + knowledge base + PDFs
- Still use multi-stage builds to strip dev dependencies and build tools

### Claude's Discretion
- Base image choice (python:slim, ubuntu, etc.)
- Multi-stage build layer optimization
- Exact health check implementation (script, curl, etc.)
- Entrypoint script design
- Docker Compose networking configuration
- .dockerignore contents

</decisions>

<specifics>
## Specific Ideas

- Users will not have internet access — this is the core constraint driving the "bake everything in" approach
- The system serves a Meshtastic/off-grid use case, so true offline capability is non-negotiable
- Port 8080 chosen to avoid conflicts with common dev servers

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `web.py`: Gradio + FastAPI app, entry point for web UI. Currently serves on Gradio default port, mounts PDFs from `sources/originals/` via StaticFiles
- `cli.py`: Click CLI with `ask` subcommand and REPL mode. Can be invoked as `python cli.py ask "query"`
- `ask.py`: Quick interactive query tool (simpler than cli.py)
- `pipeline/retrieve.py`: Hybrid retrieval engine, init takes `chroma_path` param (default `./data/chroma`)
- `pipeline/generate.py`: LLM generation, init validates model availability via Ollama
- `pipeline/embed.py`: Embedding via nomic-embed-text through Ollama
- `requirements.txt`: All Python dependencies listed (docling, chromadb, bm25s, gradio, click, rich, etc.)
- `sources/scripts/download-all.sh`: Downloads source PDFs — not needed in Docker since PDFs are baked in

### Established Patterns
- App initialization: `retrieve.init(chroma_path="./data/chroma")` then `gen.init()` — must happen before accepting queries
- Ollama connection: defaults to `http://localhost:11434`, configurable
- Environment variables: `SURVIVALRAG_*` prefix (SURVIVALRAG_MODEL, SURVIVALRAG_RELEVANCE_THRESHOLD, etc.)
- ChromaDB data stored at `data/chroma/`
- Source PDFs at `sources/originals/`

### Integration Points
- `web.py` is the Docker entrypoint for the web service
- `cli.py` needs to be accessible via `docker exec`
- Ollama must be reachable from the app container (inter-container networking)
- ChromaDB runs embedded in the app process (not a separate service)
- BM25 index built in-memory at startup from ChromaDB data

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 08-docker-packaging-deployment*
*Context gathered: 2026-03-03*
