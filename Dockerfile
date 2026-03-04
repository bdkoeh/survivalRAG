# SurvivalRAG Application Container
# Multi-stage build: runtime-only dependencies, pre-built ChromaDB data, source PDFs
# No docling, no torch, no OCR -- all document processing is pre-built

# --- Stage 1: Builder (install Python packages) ---
FROM python:3.14-slim AS builder

WORKDIR /app

# Install build-time system deps needed for Python package compilation
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install Python runtime dependencies only
COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt

# --- Stage 2: Runtime ---
FROM python:3.14-slim

WORKDIR /app

# Install curl for Docker HEALTHCHECK
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY web.py cli.py ask.py ./
COPY pipeline/ ./pipeline/

# Copy pre-built data (ChromaDB vector store + evaluation golden queries)
COPY data/chroma/ ./data/chroma/
COPY data/eval/ ./data/eval/

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
