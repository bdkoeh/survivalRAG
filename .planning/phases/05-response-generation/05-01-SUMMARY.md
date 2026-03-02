---
phase: 05-response-generation
plan: 01
subsystem: generation
tags: [ollama, llm, streaming, system-prompts, response-modes]

# Dependency graph
requires:
  - phase: 04-retrieval-pipeline
    provides: "prompt assembly (assemble_prompt, build_response, query) producing structured prompt strings"
provides:
  - "Core LLM generation engine: init(), generate_stream(), generate()"
  - "Three mode-specific system prompts (full, compact, ultra) with locked safe parameters"
  - "Phase 5 -> Phase 6/7 response contract dict (response, mode, model, verification)"
affects: [05-response-generation, 06-evaluation, 07-user-interfaces]

# Tech tracking
tech-stack:
  added: [ollama-generate-api]
  patterns: [streaming-generator, mode-specific-prompts, locked-safe-defaults]

key-files:
  created: [pipeline/generate.py]
  modified: []

key-decisions:
  - "Used ollama.generate() not ollama.chat() -- prompt from assemble_prompt() is pre-assembled string"
  - "System prompts are per-mode constants, not runtime-constructed -- matches locked decision of single LLM call per query"
  - "Generation parameters locked (temperature 0.2, top_p 0.85) to minimize hallucination on medical content"
  - "Ultra mode system prompt caps at 200 chars telegram style with no citations (no room)"

patterns-established:
  - "Streaming generator pattern: generate_stream() yields tokens, generate() collects them"
  - "Mode-option separation: _get_system_prompt() for instructions, _get_options() for generation params"
  - "Module-level state with init() validation gate matching embed.py and retrieve.py pattern"

requirements-completed: [RESP-03, RESP-04, RESP-05, RESP-06]

# Metrics
duration: 2min
completed: 2026-03-02
---

# Phase 5 Plan 01: LLM Generation Engine Summary

**Ollama streaming generation engine with three response modes (full/compact/ultra), mode-specific system prompts, and locked safe parameters for medical/survival content**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-02T01:41:14Z
- **Completed:** 2026-03-02T01:43:05Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Created pipeline/generate.py (278 lines) with complete generation engine
- Three distinct system prompts: full (detailed with citations), compact (3-4 paragraphs), ultra (200-char telegram style)
- Locked safe generation parameters: temperature 0.2, top_p 0.85, top_k 20, num_ctx 8192
- Streaming generation via Python generator pattern for CLI and web UI consumption
- Model validation at startup with clear "ollama pull" error message

## Task Commits

Each task was committed atomically:

1. **Task 1: Create generation module with init, config, and system prompts** - `92877f5` (feat)
2. **Task 2: Add generate_stream() and generate() functions** - included in `92877f5` (module written as single coherent unit)

**Plan metadata:** (pending)

## Files Created/Modified
- `pipeline/generate.py` - Core LLM generation engine: init(), generate_stream(), generate(), DEFAULT_MODEL, three system prompts, safe parameter defaults

## Decisions Made
- Used ollama.generate() not ollama.chat() because prompt from assemble_prompt() is a pre-assembled string with system context already structured
- System prompts defined as per-mode constants rather than runtime-constructed templates -- single LLM call per query with no post-processing summarization
- Generation parameters locked and not user-configurable to prevent hallucination-prone high-temperature settings on medical/safety content
- Ultra mode system prompt uses telegram style (short phrases, no articles, no citations) to fit within 200-char constraint for mesh radio
- Tasks 1 and 2 committed together since the module was written as a coherent unit (both tasks modify the same single file)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Generation engine ready for Plan 05-02 to add citation verification, post-processing, and full pipeline integration
- generate() returns structured dict with verification=None placeholder for Plan 05-02
- chunks parameter accepted by generate() but unused (reserved for Plan 05-02 citation verification)
- Requires `ollama pull llama3.2:3b` (or SURVIVALRAG_MODEL env var set) before runtime use

## Self-Check: PASSED

- pipeline/generate.py: FOUND
- 05-01-SUMMARY.md: FOUND
- Commit 92877f5: FOUND

---
*Phase: 05-response-generation*
*Completed: 2026-03-02*
