---
phase: 08-docker-packaging-deployment
plan: 01
subsystem: infra
tags: [docker, dockerfile, ollama, multi-stage-build, offline-deployment]

# Dependency graph
requires:
  - phase: 07-user-interfaces
    provides: web.py FastAPI+Gradio app and cli.py as Docker entrypoint targets
provides:
  - Application Dockerfile (multi-stage, runtime-only deps, pre-built data)
  - Custom Ollama Dockerfile with pre-baked llama3.1:8b and nomic-embed-text models
  - Runtime requirements file (9 packages, no docling/torch/OCR)
  - .dockerignore for fast build context
  - Entrypoint script with Ollama health gating and pipeline initialization
  - .env.example documenting all configurable environment variables
affects: [08-docker-packaging-deployment plan 02, 08-docker-packaging-deployment plan 03]

# Tech tracking
tech-stack:
  added: [python:3.14-slim, ollama/ollama, multi-stage-docker-build]
  patterns: [curl-polling-health-gate, inline-python-entrypoint, model-baking-at-build-time]

key-files:
  created:
    - Dockerfile
    - Dockerfile.ollama
    - requirements-docker.txt
    - .dockerignore
    - docker/entrypoint.sh
    - .env.example
  modified: []

key-decisions:
  - "python:3.14-slim base image for app container -- matches project Python version, multi-arch, minimal"
  - "Inline Python wrapper in entrypoint.sh calls build_source_map(), retrieve.init(), gen.init() before uvicorn -- required because uvicorn web:app skips __main__ initialization block"
  - "Curl polling loop (not fixed sleep) for Ollama readiness in both Dockerfile.ollama build and entrypoint.sh runtime"
  - "Entrypoint starts anyway after 60s timeout with WARNING (not hard exit) so web UI can show degraded status"
  - "Port 8080 for web UI (not web.py default 7860) per CONTEXT.md locked decision"

patterns-established:
  - "Multi-stage Docker build: builder stage installs Python packages, runtime stage copies only installed packages"
  - "Model baking: pull Ollama models during Docker build with curl polling loop for readiness"
  - "Health gate pattern: entrypoint polls dependency service before starting app, with graceful degradation on timeout"

requirements-completed: [DEPL-02, DEPL-03, DEPL-04, DEPL-05, DEPL-06]

# Metrics
duration: 3min
completed: 2026-03-03
---

# Phase 8 Plan 1: Docker Container Infrastructure Summary

**Multi-stage Dockerfiles for app (python:3.14-slim, runtime-only deps) and Ollama (pre-baked llama3.1:8b + nomic-embed-text), with curl-polling entrypoint and env var configuration**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-04T00:23:49Z
- **Completed:** 2026-03-04T00:27:13Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Created 6 Docker infrastructure files for fully offline two-container deployment
- Application Dockerfile uses multi-stage build with python:3.14-slim, installs only runtime deps, copies pre-built ChromaDB vector store and source PDFs
- Ollama Dockerfile bakes llama3.1:8b (4.9GB) and nomic-embed-text (274MB) into the image at build time with curl polling loop
- Entrypoint script initializes full pipeline (build_source_map, retrieve.init, gen.init) before starting uvicorn on port 8080

## Task Commits

Each task was committed atomically:

1. **Task 1: Create application Dockerfile, runtime requirements, and .dockerignore** - `10f2577` (feat, from prior 08-02 execution)
2. **Task 2: Create Ollama Dockerfile, entrypoint script, and .env.example** - `a7e8380` (feat)

## Files Created/Modified
- `Dockerfile` - Multi-stage build: python:3.14-slim builder + runtime with curl, copies app code, ChromaDB data, source PDFs, HEALTHCHECK on port 8080
- `Dockerfile.ollama` - Multi-stage build: bakes llama3.1:8b and nomic-embed-text into ollama/ollama image with curl polling loop, HEALTHCHECK on port 11434
- `requirements-docker.txt` - 9 runtime-only Python packages (ollama, chromadb, bm25s, gradio, click, rich, pydantic, pyspellchecker, pyyaml)
- `.dockerignore` - Excludes .venv, .git, processed/, .planning/, .claude/, __pycache__, and other build-time artifacts
- `docker/entrypoint.sh` - Waits for Ollama via curl polling (60s timeout), initializes pipeline in-process, starts uvicorn on port 8080
- `.env.example` - Documents SURVIVALRAG_MODEL, OLLAMA_HOST, SURVIVALRAG_MAX_CHUNKS, SURVIVALRAG_RELEVANCE_THRESHOLD with commented defaults

## Decisions Made
- python:3.14-slim chosen over alpine/ubuntu for matching project Python version and multi-arch support (AMD64 + ARM64)
- Inline Python wrapper in entrypoint.sh rather than `python -m uvicorn web:app` -- web.py's pipeline init only runs in `__main__` block, so uvicorn direct invocation would skip init entirely
- Curl polling loop (up to 30 retries in Dockerfile.ollama, 60 retries in entrypoint.sh) instead of fixed `sleep 5` -- more reliable across hardware speeds per RESEARCH.md Open Question 1
- On Ollama timeout, entrypoint starts anyway with WARNING rather than hard exit -- allows web UI to show degraded status via /api/health
- requirements-docker.txt excludes docling, torch, and OCR packages -- all document processing is pre-built, saving ~8GB in image size

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed requirements-docker.txt comment triggering verification false positive**
- **Found during:** Task 1 (verification)
- **Issue:** Comment line mentioning "docling" as excluded package triggered `assert 'docling' not in reqs` verification failure
- **Fix:** Changed comment wording from naming specific packages to generic description "PDF extraction, ML frameworks, OCR"
- **Files modified:** requirements-docker.txt
- **Verification:** Verification script passes
- **Committed in:** 10f2577 (prior commit from 08-02 execution already had identical content)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Trivial comment wording change. No functional impact.

## Issues Encountered
- Task 1 files (Dockerfile, requirements-docker.txt, .dockerignore) were already committed by plan 08-02 execution (commit 10f2577). The 08-02 executor created these files as part of its second task commit. Content matched the plan exactly, so no additional commit was needed for Task 1.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All 6 Docker infrastructure files in place for docker-compose.yml (plan 08-02, already complete)
- Ready for plan 08-03 (startup scripts and documentation)
- System will be fully offline from the moment Docker images are built

## Self-Check: PASSED

All 6 created files verified on disk. Both commit hashes (10f2577, a7e8380) found in git log.

---
*Phase: 08-docker-packaging-deployment*
*Completed: 2026-03-03*
