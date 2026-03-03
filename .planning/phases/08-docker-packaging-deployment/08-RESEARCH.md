# Phase 8: Docker Packaging & Deployment - Research

**Researched:** 2026-03-03
**Domain:** Docker containerization, Docker Compose orchestration, Ollama model packaging
**Confidence:** HIGH

## Summary

Phase 8 packages the complete SurvivalRAG system into two Docker containers: an application container (FastAPI + Gradio + ChromaDB embedded) and an Ollama container with pre-baked LLM models. The core constraint is that the system must be fully offline from the moment images are built -- no model downloads, no pip installs, no internet at runtime.

The application container uses `python:3.14-slim` as its base, installs only runtime dependencies (no docling, no torch, no OCR), copies the pre-built ChromaDB vector store and source PDFs, and runs uvicorn serving the FastAPI+Gradio app. The Ollama container uses a multi-stage build approach: start ollama serve in the background during the build, pull both models (llama3.1:8b at 4.9GB and nomic-embed-text at 274MB), then copy the model cache to the final image. Docker Compose wires the two containers with health checks and depends_on condition: service_healthy.

**Primary recommendation:** Use multi-stage Dockerfile builds for both containers. Application container strips build-time deps. Ollama container bakes models during Docker build. Entrypoint script in the app container waits for Ollama health before initializing the pipeline.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Pre-built ChromaDB vector store and processed chunks baked into the app Docker image -- no embedding or processing step on first run
- Source PDFs bundled in the image so citation click-through links work out of the box
- Data is ephemeral (lives in the container layer, no named volumes) -- acceptable since the knowledge base is immutable
- Knowledge base is read-only: curated content only, no user-added documents
- Ollama models (Llama 3.1 8B + nomic-embed-text) must be baked into a custom Ollama Docker image -- users will NOT have internet access to pull models
- This is a hard constraint: the system must be fully offline from the moment images are available, no model downloads at runtime
- App container uses health check gating: waits for Ollama to be ready, logs progress ("Waiting for Ollama...", "Ready! Open http://localhost:8080")
- Docker health checks report unhealthy until all components are initialized
- Web UI exposed on port 8080 by default
- External Ollama instance supported via OLLAMA_HOST env var -- power users can point to a GPU machine on the LAN and skip the bundled Ollama container
- LLM model is swappable via SURVIVALRAG_MODEL env var -- default is bundled Llama 3.1 8B, users responsible for model availability if they change it
- Both web UI and CLI available in the container -- `docker exec` for CLI access
- Ship `.env.example` with all SURVIVALRAG_* variables commented out with defaults, referenced from README
- Env vars use existing SURVIVALRAG_* prefix convention from the codebase
- CPU-only default docker-compose.yml -- works on any machine without GPU drivers
- GPU support via separate docker-compose.gpu.yml override or documented override snippet for NVIDIA GPU passthrough
- Multi-arch builds: x86_64 (AMD64) and ARM64 -- covers M-series Macs and Raspberry Pi
- Local build only -- users clone repo and `docker compose build`, no registry publishing
- Large image size acceptable (~8-10GB total) given bundled LLM models (~5GB) + knowledge base + PDFs
- Still use multi-stage builds to strip dev dependencies and build tools

### Claude's Discretion
- Base image choice (python:slim, ubuntu, etc.)
- Multi-stage build layer optimization
- Exact health check implementation (script, curl, etc.)
- Entrypoint script design
- Docker Compose networking configuration
- .dockerignore contents

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DEPL-01 | Single `docker compose up` command starts the complete system | Docker Compose file with two services, depends_on with health check gating, entrypoint scripts handle all initialization |
| DEPL-02 | Docker Compose runs two containers: application (FastAPI + Gradio + ChromaDB embedded) and Ollama | Two-service compose file; app container runs uvicorn with embedded ChromaDB PersistentClient; Ollama container serves models |
| DEPL-03 | Ollama container automatically pulls default models (Llama 3.1 8B + nomic-embed-text) on first startup | Models baked into custom Ollama image during Docker build via multi-stage approach -- no runtime pull needed |
| DEPL-04 | System is fully functional offline after initial setup (no external API calls at runtime) | All dependencies installed at build time; models baked in; ChromaDB + chunks baked in; no pip install at runtime |
| DEPL-05 | User can configure an external Ollama instance instead of the bundled one | OLLAMA_HOST env var natively supported by ollama Python library; compose override pattern documented |
| DEPL-06 | User can configure a different LLM model via environment variable | SURVIVALRAG_MODEL env var already implemented in pipeline/generate.py (line 140) |
| DEPL-07 | Health checks verify all components are running before accepting queries | Docker HEALTHCHECK in both containers; app entrypoint waits for Ollama; /api/health endpoint already exists in web.py |
| DEPL-08 | Minimum hardware requirements are documented (16GB RAM, 20GB disk) | README section with hardware requirements, model sizes, and expected image sizes |
</phase_requirements>

## Standard Stack

### Core
| Component | Version/Tag | Purpose | Why Standard |
|-----------|-------------|---------|--------------|
| python:3.14-slim-trixie | 3.14.x | App container base image | Matches project Python version; slim variant is 41MB; Debian Trixie is current |
| ollama/ollama | latest (pin to specific tag at build time) | LLM serving container base | Official image; multi-arch (AMD64 + ARM64); includes CUDA support |
| Docker Compose | v2 (Compose specification) | Multi-container orchestration | Built into Docker Desktop; uses `docker compose` (v2 syntax) |
| uvicorn | (from requirements.txt via gradio) | ASGI server for FastAPI+Gradio | Already the server used in web.py; production-grade |

### Supporting
| Component | Purpose | When to Use |
|-----------|---------|-------------|
| curl | Health check HTTP client | Install in both custom images; required for Docker HEALTHCHECK commands |
| docker buildx | Multi-architecture builds | Use when building for both AMD64 and ARM64 |
| wait-for-it pattern | App startup sequencing | Entrypoint script polls Ollama /api/tags before pipeline init |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| python:3.14-slim | ubuntu:24.04 + uv | Slightly faster Python runtime (10-17%) but more complex setup; slim is simpler and matches project |
| curl for health checks | wget or Python script | curl is most idiomatic for Docker HEALTHCHECK; Python script adds complexity |
| Multi-stage Ollama build | Entrypoint pull-on-start | Entrypoint pull requires internet on first run -- violates offline constraint |
| alpine/ollama (70MB) | ollama/ollama (~4GB) | CPU-only, much smaller, but no GPU path and less tested |

## Architecture Patterns

### Recommended Project Structure
```
project_root/
├── Dockerfile                  # App container (FastAPI + Gradio + ChromaDB)
├── Dockerfile.ollama           # Custom Ollama container with baked models
├── docker-compose.yml          # CPU-only default orchestration
├── docker-compose.gpu.yml      # GPU override for NVIDIA
├── .dockerignore               # Exclude build-time-only files
├── .env.example                # All SURVIVALRAG_* env vars with defaults
├── docker/
│   └── entrypoint.sh           # App container entrypoint (wait for Ollama, init, run)
├── web.py                      # (existing) FastAPI+Gradio app
├── cli.py                      # (existing) CLI tool
├── pipeline/                   # (existing) Python pipeline modules
├── data/chroma/                # (existing) Pre-built vector store
├── sources/originals/          # (existing) Source PDFs
└── sources/manifests/          # (existing) YAML provenance manifests
```

### Pattern 1: Multi-Stage Ollama Model Baking
**What:** Build a custom Ollama image with models pre-downloaded during Docker build
**When to use:** When the system must be offline from the moment containers start
**Example:**
```dockerfile
# Source: https://github.com/ollama/ollama/issues/957
FROM ollama/ollama:latest AS builder
RUN ollama serve & sleep 5 && \
    ollama pull llama3.1:8b && \
    ollama pull nomic-embed-text

FROM ollama/ollama:latest
COPY --from=builder /root/.ollama /root/.ollama
EXPOSE 11434
CMD ["serve"]
```
**Confidence:** HIGH -- this pattern is well-documented in Ollama GitHub issue #957 and confirmed working by multiple users. The multi-stage approach avoids cache invalidation issues.

### Pattern 2: App Container Entrypoint with Health Gating
**What:** Entrypoint script that waits for Ollama before starting the app
**When to use:** When the app container depends on Ollama being fully ready
**Example:**
```bash
#!/bin/bash
set -e

OLLAMA_URL="${OLLAMA_HOST:-http://ollama:11434}"

echo "Waiting for Ollama at $OLLAMA_URL..."
MAX_RETRIES=60
for i in $(seq 1 $MAX_RETRIES); do
    if curl -sf "$OLLAMA_URL/api/tags" > /dev/null 2>&1; then
        echo "Ollama is ready!"
        break
    fi
    if [ "$i" -eq "$MAX_RETRIES" ]; then
        echo "ERROR: Ollama not available after ${MAX_RETRIES}s"
        exit 1
    fi
    sleep 1
done

echo "Starting SurvivalRAG on http://0.0.0.0:8080"
exec python -m uvicorn web:app --host 0.0.0.0 --port 8080
```
**Confidence:** HIGH -- standard Docker pattern for service dependency gating.

### Pattern 3: Docker Compose Health Check + depends_on
**What:** Use Docker native health checks with depends_on condition: service_healthy
**When to use:** To ensure containers start in the right order
**Example:**
```yaml
# Source: https://docs.docker.com/compose/how-tos/startup-order/
services:
  ollama:
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:11434/api/tags"]
      interval: 10s
      timeout: 5s
      retries: 30
      start_period: 10s

  app:
    depends_on:
      ollama:
        condition: service_healthy
```
**Confidence:** HIGH -- official Docker Compose documentation pattern.

### Pattern 4: Runtime-Only Requirements
**What:** Separate runtime deps from build-time deps to minimize image size
**When to use:** When the full dependency set includes large build-only packages (docling, torch, OCR)

The runtime dependency chain for the Docker app container is:
```
web.py / cli.py
├── pipeline.generate  → ollama
├── pipeline.retrieve  → chromadb, bm25s, pipeline._chromadb_compat
├── pipeline.rewrite   → ollama, pipeline.generate
├── pipeline.embed     → ollama, pipeline.models, pipeline.spellcheck
├── pipeline.ingest    → chromadb, pipeline.models
├── pipeline.prompt    → (stdlib only)
├── pipeline.models    → pydantic
├── pipeline.spellcheck → pyspellchecker
├── pipeline._chromadb_compat → (stdlib only)
├── gradio
├── fastapi / starlette
├── uvicorn
├── yaml (pyyaml)
├── click
└── rich
```

**NOT needed at runtime (build-time only):**
- docling (PDF extraction -- already done)
- docling_core (section splitting -- already done)
- torch/pytorch (used by docling -- already done)
- tesseract/OCR packages (extraction -- already done)

**Runtime requirements.txt for Docker:**
```
ollama>=0.6.1
pydantic>=2.0
pyspellchecker>=0.8.0
chromadb>=1.5.0
bm25s>=0.3.0
gradio>=6.8.0
click>=8.1
rich>=14.0
pyyaml>=6.0
```
**Confidence:** HIGH -- traced from actual import chains in the codebase.

### Pattern 5: GPU Override Compose File
**What:** Separate docker-compose.gpu.yml for NVIDIA GPU passthrough
**When to use:** Users with NVIDIA GPUs who want accelerated inference
**Example:**
```yaml
# Source: https://docs.docker.com/compose/how-tos/gpu-support/
# Usage: docker compose -f docker-compose.yml -f docker-compose.gpu.yml up
services:
  ollama:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```
**Confidence:** HIGH -- official Docker Compose GPU documentation.

### Anti-Patterns to Avoid
- **Model pull at runtime:** Violates the offline constraint. Models MUST be baked into the image.
- **Named volumes for knowledge base:** The KB is immutable/read-only. Named volumes add complexity and create a "where's my data?" debugging surface. Bake it in.
- **Running embedding/processing in Docker:** All 175MB of ChromaDB data and 274MB of chunks are pre-built. Docker just copies them in.
- **Single monolith container:** Running Ollama inside the app container prevents users from pointing to an external Ollama instance and makes GPU passthrough harder.
- **Using `sleep` for startup sequencing:** Use health check polling loops instead of arbitrary sleep durations.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Service startup ordering | Custom process manager | Docker Compose depends_on + healthcheck | Docker-native, well-tested, handles restarts |
| Container health monitoring | Custom health daemon | Docker HEALTHCHECK directive | Built into Docker engine, visible in `docker ps` |
| Multi-arch image builds | Separate Dockerfiles per arch | `docker buildx build --platform` | Single Dockerfile, buildx handles cross-compilation |
| Ollama readiness detection | Custom TCP probe | `curl -sf http://host:11434/api/tags` | Ollama's /api/tags returns model list only when ready |
| GPU detection/passthrough | Custom device mapping | Docker Compose deploy.resources.reservations.devices | NVIDIA Container Toolkit handles all driver mounting |
| Process supervision in container | supervisord / systemd | Single process per container + Docker restart policy | Docker best practice; simpler, more predictable |

**Key insight:** Docker Compose and Docker's built-in health check system provide all the orchestration needed. The entrypoint script is the only custom logic required -- everything else uses standard Docker primitives.

## Common Pitfalls

### Pitfall 1: Ollama Image Missing curl
**What goes wrong:** Docker HEALTHCHECK uses `curl` but the official `ollama/ollama` image does not include curl.
**Why it happens:** Ollama's base image is minimal and does not ship HTTP client tools.
**How to avoid:** Install curl in the custom Ollama Dockerfile: `RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*`
**Warning signs:** Health check always fails; container marked unhealthy in `docker ps`.
**Source:** [GitHub Issue #9781](https://github.com/ollama/ollama/issues/9781)

### Pitfall 2: Model Bake Fails Because Ollama Server Not Running
**What goes wrong:** `RUN ollama pull llama3.1:8b` fails with "connection refused" during Docker build.
**Why it happens:** Ollama CLI requires the Ollama server process to be running. Docker RUN commands don't start background services automatically.
**How to avoid:** Start ollama serve in the background before pulling: `RUN ollama serve & sleep 5 && ollama pull llama3.1:8b`
**Warning signs:** Build error "could not connect to ollama app".
**Source:** [GitHub Issue #957](https://github.com/ollama/ollama/issues/957)

### Pitfall 3: Python 3.14 + ChromaDB Compatibility
**What goes wrong:** ChromaDB import fails with pydantic v1 ConfigError on Python 3.14.
**Why it happens:** ChromaDB uses pydantic v1 BaseSettings which has type inference issues on Python 3.14+.
**How to avoid:** The project already has `pipeline/_chromadb_compat.py` that patches this. Ensure the import `import pipeline._chromadb_compat` runs before any chromadb import. The entrypoint must preserve the working directory and module path so this import works.
**Warning signs:** `pydantic.v1.errors.ConfigError` on container startup.

### Pitfall 4: Large Build Context Slows Docker Build
**What goes wrong:** Docker build takes minutes just to send context because `.venv/`, `.git/`, `processed/`, etc. are included.
**Why it happens:** Without a `.dockerignore`, Docker sends the entire project directory (potentially GBs) to the daemon.
**How to avoid:** Create a comprehensive `.dockerignore` that excludes `.venv/`, `.git/`, `__pycache__/`, `processed/`, `.planning/`, `.claude/`, `*.pyc`, etc.
**Warning signs:** "Sending build context to Docker daemon" takes more than a few seconds.

### Pitfall 5: web.py Listens on Port 7860 But Container Exposes 8080
**What goes wrong:** Users can't reach the web UI despite the container running.
**Why it happens:** web.py hardcodes `port=7860` in its `__main__` block, but the CONTEXT.md specifies port 8080.
**How to avoid:** The entrypoint should run uvicorn directly with `--port 8080` instead of using `python web.py`. Alternatively, modify web.py to read port from an environment variable.
**Warning signs:** Container starts but `http://localhost:8080` returns connection refused.

### Pitfall 6: Docker on Mac Doesn't Provide GPU Access
**What goes wrong:** Users on M-series Macs expect GPU acceleration but get CPU-only performance.
**Why it happens:** Docker Desktop on macOS runs Linux VMs that cannot access Apple Metal GPUs. Only NVIDIA GPUs on Linux hosts support Docker GPU passthrough.
**How to avoid:** Document clearly: "GPU acceleration in Docker requires NVIDIA GPU on Linux. On macOS, run Ollama natively for GPU access and point Docker to it via OLLAMA_HOST."
**Warning signs:** Very slow inference times (~tokens/sec) on capable hardware.
**Source:** [Chariot Solutions Blog](https://chariotsolutions.com/blog/post/apple-silicon-gpus-docker-and-ollama-pick-two/)

### Pitfall 7: Ollama Model Path Mismatch Between Build and Runtime
**What goes wrong:** Models baked during build are not found at runtime.
**Why it happens:** Ollama stores models in `$HOME/.ollama` which may differ between build user (root) and runtime user.
**How to avoid:** Use consistent user (root) or explicitly set `OLLAMA_MODELS` env var to a fixed path. The multi-stage COPY approach (`COPY --from=builder /root/.ollama /root/.ollama`) avoids this by using consistent paths.
**Warning signs:** "model not found" errors despite models being in the image.

## Code Examples

### Complete Application Dockerfile
```dockerfile
# Source: Synthesized from FastAPI docs + project analysis
FROM python:3.14-slim-trixie AS builder

WORKDIR /app

# Install build dependencies for Python packages that need compilation
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install Python runtime dependencies only (no docling, no torch, no OCR)
COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt

# --- Runtime stage ---
FROM python:3.14-slim-trixie

WORKDIR /app

# Install curl for health checks
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY web.py cli.py ask.py ./
COPY pipeline/ ./pipeline/

# Copy pre-built data (ChromaDB vector store + evaluation data)
COPY data/ ./data/

# Copy source PDFs and manifests for citation links
COPY sources/originals/ ./sources/originals/
COPY sources/manifests/ ./sources/manifests/

# Copy entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -sf http://localhost:8080/api/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
```

### Complete Ollama Dockerfile
```dockerfile
# Source: https://github.com/ollama/ollama/issues/957 (multi-stage pattern)
FROM ollama/ollama:latest AS model-builder

# Install curl for model pull verification
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Start Ollama server, wait for readiness, pull models
RUN ollama serve & \
    sleep 5 && \
    until curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do sleep 1; done && \
    ollama pull llama3.1:8b && \
    ollama pull nomic-embed-text

# --- Final image ---
FROM ollama/ollama:latest

# Install curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Copy pre-pulled models from builder
COPY --from=model-builder /root/.ollama /root/.ollama

EXPOSE 11434

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=5 \
    CMD curl -sf http://localhost:11434/api/tags || exit 1

CMD ["serve"]
```

### Complete Docker Compose File
```yaml
# Source: Docker Compose official docs + project requirements
services:
  ollama:
    build:
      context: .
      dockerfile: Dockerfile.ollama
    container_name: survivalrag-ollama
    ports:
      - "11434:11434"
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:11434/api/tags"]
      interval: 10s
      timeout: 5s
      retries: 30
      start_period: 10s
    restart: unless-stopped

  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: survivalrag-app
    ports:
      - "8080:8080"
    environment:
      - OLLAMA_HOST=http://ollama:11434
      - SURVIVALRAG_MODEL=${SURVIVALRAG_MODEL:-llama3.1:8b}
    depends_on:
      ollama:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8080/api/health"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 30s
    restart: unless-stopped
```

### Entrypoint Script
```bash
#!/bin/bash
set -e

OLLAMA_URL="${OLLAMA_HOST:-http://ollama:11434}"

# Wait for Ollama (even with depends_on, extra safety)
echo "SurvivalRAG: Checking Ollama at $OLLAMA_URL..."
for i in $(seq 1 30); do
    if curl -sf "$OLLAMA_URL/api/tags" > /dev/null 2>&1; then
        echo "SurvivalRAG: Ollama is ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "SurvivalRAG: WARNING - Ollama not detected, starting anyway..."
    fi
    sleep 1
done

echo "SurvivalRAG: Starting web UI at http://0.0.0.0:8080"
exec python -m uvicorn web:app --host 0.0.0.0 --port 8080
```

### .dockerignore
```
.git
.gitignore
.venv/
.env
.env.*
.planning/
.claude/
__pycache__/
*.pyc
*.pyo
processed/sections/
processed/reports/
processed/corrections/
processed/spellcheck/
processed/benchmark/
processed/eval/
scripts/
sources/scripts/
sources/excluded/
sources/checksums.sha256
*.md
!requirements*.txt
*.log
.DS_Store
Thumbs.db
.vscode/
.idea/
*.egg-info/
dist/
build/
LICENSE
SurvivalRAG_Brief.md
```

### .env.example
```bash
# SurvivalRAG Configuration
# Copy to .env and uncomment to override defaults

# LLM model for response generation (default: llama3.1:8b)
# SURVIVALRAG_MODEL=llama3.1:8b

# Ollama server URL (default: http://ollama:11434 in Docker)
# Set to point to external Ollama instance (e.g., GPU machine on LAN)
# OLLAMA_HOST=http://192.168.1.100:11434

# Maximum chunks to retrieve per query (default: 5)
# SURVIVALRAG_MAX_CHUNKS=5

# Cosine similarity threshold for relevance filtering (default: 0.25)
# SURVIVALRAG_RELEVANCE_THRESHOLD=0.25
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `ollama pull` at runtime | Models baked into image at build time | 2024-2025 | Enables fully offline deployment |
| docker-compose v1 (`docker-compose`) | Docker Compose v2 (`docker compose`) | 2023 | Built into Docker CLI; v1 is deprecated |
| `condition: service_started` | `condition: service_healthy` | Docker Compose v2.1+ | Real readiness detection, not just "is running" |
| sleep-based service waiting | curl health check polling loops | 2024+ | Deterministic, fails fast, works on any hardware speed |
| Single `requirements.txt` | Separate runtime/build requirements | Best practice | Dramatically smaller runtime images |

**Deprecated/outdated:**
- `docker-compose` (v1 binary): Deprecated in favor of `docker compose` (v2, plugin). Always use v2 syntax.
- `tiangolo/uvicorn-gunicorn-fastapi` image: Deprecated by the author. Build from official `python:` images instead.
- `links:` in Compose: Superseded by Docker network DNS. Services on the same Compose network can reach each other by service name.

## Open Questions

1. **Ollama `sleep 5` reliability during model bake**
   - What we know: The `ollama serve & sleep 5 && ollama pull` pattern works for most users per GitHub issue #957. Some prefer using `wait4x` or a curl polling loop for more deterministic startup.
   - What's unclear: On very slow CI systems, 5 seconds may not be enough for Ollama to initialize.
   - Recommendation: Use curl polling loop (`until curl -sf ... > /dev/null; do sleep 1; done`) instead of fixed sleep. More reliable across hardware.

2. **Python 3.14 slim image stability**
   - What we know: `python:3.14-slim-trixie` exists on Docker Hub with multi-arch support (AMD64, ARM64). Python 3.14 is the project's Python version.
   - What's unclear: Python 3.14 may still have minor compatibility issues with some packages. The ChromaDB compat shim already handles the known issue.
   - Recommendation: Use `python:3.14-slim` and test. If issues arise, `python:3.13-slim-bookworm` is a well-tested fallback.

3. **Multi-arch build for Ollama with baked models**
   - What we know: `docker buildx build --platform linux/amd64,linux/arm64` works for standard Dockerfiles. Ollama official images support both architectures.
   - What's unclear: The `ollama pull` during build fetches architecture-specific model files. QEMU emulation during cross-arch builds may be very slow for 5GB model downloads.
   - Recommendation: Document that multi-arch builds should be done on native hardware or CI with appropriate architecture runners. For local use, `docker compose build` builds for the host architecture only, which is the expected workflow.

4. **Image size budget**
   - What we know: Ollama base (~1GB compressed) + llama3.1:8b (4.9GB) + nomic-embed-text (274MB) = ~6.2GB for Ollama container. App container: python:3.14-slim (41MB) + deps + ChromaDB data (175MB) + PDFs (314MB) + chunks data = ~800MB-1GB.
   - What's unclear: Exact compressed image sizes may vary.
   - Recommendation: Acceptable per user decision ("Large image size acceptable ~8-10GB total"). Document sizes in README.

## Sources

### Primary (HIGH confidence)
- [Docker Compose Startup Order](https://docs.docker.com/compose/how-tos/startup-order/) - depends_on conditions and healthcheck syntax
- [Docker Compose GPU Support](https://docs.docker.com/compose/how-tos/gpu-support/) - NVIDIA GPU reservation in Compose
- [Docker Multi-Platform Builds](https://docs.docker.com/build/building/multi-platform/) - buildx multi-arch patterns
- [FastAPI Docker Deployment](https://fastapi.tiangolo.com/deployment/docker/) - official Dockerfile patterns
- [Ollama Docker Hub](https://hub.docker.com/r/ollama/ollama) - official Ollama image tags and architectures
- [Ollama GitHub Issue #957](https://github.com/ollama/ollama/issues/957) - pre-baked model Dockerfile patterns
- [Ollama GitHub Issue #9781](https://github.com/ollama/ollama/issues/9781) - curl missing from image, health check implications

### Secondary (MEDIUM confidence)
- [DoltHub: Pull-first Ollama Docker Image](https://www.dolthub.com/blog/2025-03-19-a-pull-first-ollama-docker-image/) - entrypoint script and health gating patterns
- [Reducing Docling Docker Image Size](https://shekhargulati.com/2025/02/05/reducing-size-of-docling-pytorch-docker-image/) - CPU-only PyTorch optimization (9.74GB -> 1.74GB) -- confirms docling should NOT be in runtime image
- [Docker Python Best Practices](https://pythonspeed.com/articles/base-image-python-docker-images/) - base image comparison (February 2026)
- [Chariot Solutions: Apple Silicon + Docker + Ollama](https://chariotsolutions.com/blog/post/apple-silicon-gpus-docker-and-ollama-pick-two/) - Mac GPU limitation documentation
- [Ollama Model Sizes](https://ollama.com/library/llama3.1:8b) - llama3.1:8b is 4.9GB; nomic-embed-text is 274MB

### Tertiary (LOW confidence)
- None -- all findings verified with at least two sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Docker, Docker Compose, Python slim images are all well-documented stable technologies
- Architecture: HIGH - Two-container pattern with health gating is the standard Ollama+app deployment model; verified in multiple sources
- Pitfalls: HIGH - Each pitfall sourced from official GitHub issues or documentation; most discovered from real user reports

**Research date:** 2026-03-03
**Valid until:** 2026-04-03 (stable domain, 30-day validity)
