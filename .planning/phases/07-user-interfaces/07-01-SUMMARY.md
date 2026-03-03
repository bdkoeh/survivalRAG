---
phase: 07-user-interfaces
plan: 01
subsystem: ui
tags: [gradio, fastapi, streaming, chat-ui, pdf-serving, terminal-theme]

# Dependency graph
requires:
  - phase: 05-response-generation
    provides: "gen.answer_stream() streaming entry point with citation verification"
  - phase: 04-retrieval-pipeline
    provides: "retrieve.init() and retrieve.retrieve() for hybrid search and chunk counts"
  - phase: 01-content-sourcing
    provides: "sources/manifests/*.yaml for source-to-PDF mapping, sources/originals/ for PDF serving"
provides:
  - "Gradio + FastAPI web chat UI at localhost:7860"
  - "Terminal-style dark theme with monospace fonts"
  - "Streaming chat responses with token-by-token display"
  - "Clickable citation links to locally-served PDFs with page anchors"
  - "Safety warning blocks with colored styling"
  - "Category filter pills and response mode toggle"
  - "Health check API at /api/health"
  - "PDF static file serving at /pdf/"
affects: [07-02-cli, 08-deployment]

# Tech tracking
tech-stack:
  added: [gradio>=6.8.0, click>=8.1, rich>=14.0]
  patterns: [gradio-blocks-layout, fastapi-gradio-mount, generator-streaming, manifest-pdf-mapping]

key-files:
  created: [web.py]
  modified: [requirements.txt]

key-decisions:
  - "Used text-based status indicators ([OK]/[ERR]) instead of emoji for terminal aesthetic consistency"
  - "Extended _PUBLISHER_TO_DIR mapping to handle actual manifest publisher values (Department of the Army, NWS, USDA FSIS, FEMA / American Red Cross)"
  - "System fonts only (JetBrains Mono, Cascadia Code, Fira Code, monospace) -- no Google Fonts CDN for fully offline operation"
  - "Citation link conversion happens AFTER streaming completes to avoid broken links from partial citation text mid-token"
  - "Safety warnings collected via separate retrieve() call after streaming to prepend as styled blocks"

patterns-established:
  - "Gradio Blocks with custom TerminalTheme for all web UI components"
  - "FastAPI parent app with Gradio mounted at root via gr.mount_gradio_app()"
  - "Source-to-PDF mapping built at startup from manifest YAML scanning"
  - "Generator-based streaming with post-processing on final yield"

requirements-completed: [WEBUI-01, WEBUI-02, WEBUI-03, WEBUI-04, WEBUI-05, WEBUI-06]

# Metrics
duration: 3min
completed: 2026-03-02
---

# Phase 7 Plan 1: Web Chat UI Summary

**Gradio + FastAPI web chat UI with terminal-style dark theme, streaming responses, clickable PDF citation links, category filtering, and safety warning blocks**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-02T23:58:29Z
- **Completed:** 2026-03-03T00:01:34Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Single-file web.py with complete Gradio + FastAPI chat application
- Terminal-style dark theme with monospace fonts, green accents, and sharp corners
- Streaming chat handler (generator-based) with error handling for ConnectionError, RuntimeError, and generic exceptions
- Source-to-PDF mapping from 72 manifest YAML files for clickable citation links with #page=N anchors
- Safety warnings displayed as styled HTML blocks (amber for warning, red for danger) prepended to responses
- Category filter pills (9 categories) and response mode toggle (full/compact/ultra)
- FastAPI serves PDFs from sources/originals/ at /pdf/ endpoint
- Health check endpoint at /api/health returns Ollama status, model name, and chunk count

## Task Commits

Both tasks were implemented together in a single file creation (web.py is a single-file application where layout and behavior are tightly coupled):

1. **Task 1: Build Gradio + FastAPI web application with layout and PDF serving** - `afbdfe2` (feat)
2. **Task 2: Wire streaming chat handler with warning display and status updates** - included in `afbdfe2` (implemented together with Task 1)

**Plan metadata:** (pending)

## Files Created/Modified
- `web.py` - Gradio + FastAPI web chat UI with streaming, citations, category filtering, status bar, disclaimer, terminal theme
- `requirements.txt` - Added gradio>=6.8.0, click>=8.1, rich>=14.0 for Phase 7

## Decisions Made
- **Text-based status indicators:** Used `[OK]` / `[ERR]` instead of emoji for terminal aesthetic consistency and offline compatibility
- **Publisher mapping extended:** Added "Department of the Army", "NWS", "USDA FSIS", "FEMA / American Red Cross" to _PUBLISHER_TO_DIR to handle actual manifest publisher values discovered during implementation
- **System fonts only:** Font stack uses JetBrains Mono, Cascadia Code, Fira Code, monospace -- no Google Fonts CDN call, ensuring fully offline operation
- **Post-stream citation processing:** Citation-to-link conversion runs AFTER streaming completes as one final yield, avoiding broken links from partial citation text mid-token
- **Safety warnings via separate retrieve call:** After streaming completes, a separate retrieve() + collect_safety_warnings() call provides warning data for styled block prepending

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Extended publisher-to-directory mapping for actual corpus**
- **Found during:** Task 1 (build_source_map implementation)
- **Issue:** Plan's _PUBLISHER_TO_DIR used "US Army" but actual manifests use "Department of the Army" (23 docs). Also missing NWS, USDA FSIS, and "FEMA / American Red Cross" publishers.
- **Fix:** Added all actual publisher strings found in the 72 manifests, plus substring fallback matching for compound publisher names
- **Files modified:** web.py
- **Verification:** Mapping covers all 72 manifests based on grep of publisher values
- **Committed in:** afbdfe2

**2. [Rule 3 - Blocking] Accidental inclusion of pre-existing cli.py**
- **Found during:** Task 1 commit
- **Issue:** An untracked cli.py file in the working tree was staged alongside web.py and requirements.txt
- **Impact:** Minimal -- cli.py is a valid Phase 7 file that belongs to plan 07-02 (CLI tool). It was already in the working directory before this plan started.
- **Files affected:** cli.py (not created by this plan)

---

**Total deviations:** 1 auto-fixed (1 missing critical), 1 minor commit scope issue
**Impact on plan:** Publisher mapping extension was necessary for the source-to-PDF mapping to work with the actual corpus. No scope creep.

## Issues Encountered
None -- plan executed smoothly. Both tasks implemented together since web.py is a single-file application where layout (Task 1) and behavior (Task 2) are naturally co-located.

## User Setup Required
None - no external service configuration required. The web UI starts via `python web.py` after the existing pipeline prerequisites (Ollama running, knowledge base embedded).

## Next Phase Readiness
- Web UI complete and ready for Phase 7 Plan 2 (CLI tool)
- requirements.txt already includes click and rich dependencies needed by cli.py
- Pipeline integration proven: gen.answer_stream(), retrieve.retrieve(), collect_safety_warnings() all wired
- FastAPI health endpoint available for monitoring/deployment (Phase 8)

## Self-Check: PASSED

- [x] web.py exists
- [x] requirements.txt exists
- [x] 07-01-SUMMARY.md exists
- [x] Commit afbdfe2 exists in git log

---
*Phase: 07-user-interfaces*
*Completed: 2026-03-02*
