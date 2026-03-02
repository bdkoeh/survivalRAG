# Phase 7: User Interfaces - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Non-technical users can interact with the knowledge base through a browser-based chat UI, and power users can query from the command line. Both interfaces provide category filtering, citation display, safety disclaimers, and system status. The web UI streams responses and serves source PDFs for offline citation linking.

</domain>

<decisions>
## Implementation Decisions

### Web chat framework & layout
- **Framework:** Gradio (Python-native, built-in chat component, streaming support, minimal code)
- **Layout:** Minimal terminal-style (dark background, monospace font, command-line aesthetic)
- **Category filter:** Clickable tag pills above the input. Toggle on/off, active ones highlighted. Categories: medical, water, shelter, fire, food, navigation, signaling, tools, first_aid
- **Response mode selector:** Toggle buttons (Full / Compact / Ultra) near the send button. Default to Full

### Citation & source display
- **Citation format:** Inline references in response text, as the pipeline already generates: (Source: FM 21-76, p.45)
- **Source linking:** Citations are clickable links that open locally-served source PDFs at the cited page. FastAPI serves PDFs from `sources/originals/` with page anchors. Works fully offline
- **Safety warnings:** Rendered as colored warning blocks (amber/red border) at the top of the response. Visually distinct from normal content
- **Source context:** Show LLM response only (no raw retrieved chunks panel). Citations themselves point to the source

### CLI tool design
- **Invocation:** Both single-shot and REPL. `survivalrag ask "query"` for one-off questions. `survivalrag` with no args drops into interactive REPL
- **Output formatting:** Rich markdown with color (using `rich` or similar). Bold warnings, colored headers. Field-manual style readable in terminal
- **Category filtering:** `--category` flag, comma-separated: `survivalrag ask --category medical,water "query"`
- **Response mode:** `--mode` flag: `survivalrag ask --mode compact "query"`. Default to full

### Disclaimer & status indicators
- **Web disclaimer:** Persistent banner at the top of the chat UI: "This is a reference tool, not medical advice. Never use as a substitute for professional medical care."
- **Web status bar:** Compact status line below the disclaimer banner showing: Ollama connection health (green/red), model name, knowledge base size (chunk count), active response mode
- **CLI disclaimer:** Short one-liner on REPL startup: "Reference tool only -- not medical advice." No disclaimer on single-shot mode (pipe-friendly)

### Claude's Discretion
- Citation verification failure display (how to present unverified citations to the user)
- Response mode toggle button styling to fit terminal-style layout
- Exact color scheme and terminal-style visual design details
- Rich markdown library choice for CLI output

</decisions>

<specifics>
## Specific Ideas

- Terminal-style aesthetic: dark background, monospace font, command-line feel. This fits the survival/field-manual theme and distinguishes the project
- Source PDFs should be linkable from inline citations with page-level anchors (PDF.js `#page=N` or similar)
- Tag pills for category filtering provide visual affordance while maintaining the terminal aesthetic
- CLI should be scriptable: single-shot mode produces clean output suitable for piping

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pipeline.generate.answer()`: Full pipeline entry point (query -> retrieve -> prompt -> generate -> verify). Returns structured dict with `response`, `status`, `verification`, `warnings`
- `pipeline.generate.answer_stream()`: Streaming variant returning `(status, token_generator)`. Comments say "For web UI: wrap the generator in SSE"
- `pipeline.retrieve.retrieve()`: Hybrid search with category filtering via `categories` parameter
- `pipeline.retrieve.init()` and `pipeline.generate.init()`: Module initialization needed at startup
- `ask.py`: Existing CLI REPL proof-of-concept with `/compact` and `/ultra` prefix parsing

### Established Patterns
- Python-based pipeline, Ollama for LLM, ChromaDB for vector store
- Three response modes: full (1024 tokens), compact (512 tokens), ultra (80 tokens/~200 chars for mesh)
- Structured result dicts as module contracts (status, response, verification, warnings)
- Environment variables for config: `SURVIVALRAG_MODEL`, `SURVIVALRAG_MAX_CHUNKS`, `SURVIVALRAG_RELEVANCE_THRESHOLD`
- Module-level state initialized via `init()` functions

### Integration Points
- `gen.answer()` and `gen.answer_stream()` are the main entry points for both web UI and CLI
- Chunk metadata includes: `source_document`, `section_header`, `page_number`, `categories`, `warning_text`
- Source manifests in `sources/manifests/*.yaml` contain `primary_url` and document metadata
- Original PDFs in `sources/originals/{agency}/` for local serving
- No web framework currently installed -- Gradio needs to be added to requirements.txt

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 07-user-interfaces*
*Context gathered: 2026-03-02*
