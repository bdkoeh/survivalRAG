# Phase 7: User Interfaces - Research

**Researched:** 2026-03-02
**Domain:** Web chat UI (Gradio + FastAPI), CLI tool (Click + Rich), PDF serving
**Confidence:** HIGH

## Summary

Phase 7 builds two user interfaces over the existing Python pipeline: a browser-based chat UI using Gradio mounted on a FastAPI app, and a CLI tool using Click for argument parsing and Rich for terminal-formatted markdown output. The pipeline already provides the complete backend via `gen.answer()` (non-streaming) and `gen.answer_stream()` (streaming) entry points with category filtering, citation verification, and safety warning surfacing.

Gradio 6.8.0 (latest, released 2026-02-27) provides `gr.Blocks` for full layout control, `gr.Chatbot` for message display with markdown rendering, and native streaming via Python generators. It embeds its own FastAPI instance, which can be mounted onto a parent FastAPI app using `gr.mount_gradio_app()`, allowing the same server to serve source PDFs from `sources/originals/` for clickable citation links. The terminal-style dark aesthetic uses Gradio's theming system with custom CSS.

For the CLI, Click provides subcommand routing (`survivalrag ask`, `survivalrag` for REPL) with `--category` and `--mode` flags, while Rich renders markdown with syntax highlighting, colored warnings, and bold text in the terminal. Both are mature, well-documented libraries. The existing `ask.py` REPL serves as a working proof-of-concept that already calls `gen.answer_stream()`.

**Primary recommendation:** Use `gr.Blocks` (not `ChatInterface`) for full layout control over the disclaimer banner, status bar, category pills, and response mode toggle. Mount on FastAPI with `gr.mount_gradio_app()` to co-serve PDFs.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Web framework:** Gradio (Python-native, built-in chat component, streaming support, minimal code)
- **Layout:** Minimal terminal-style (dark background, monospace font, command-line aesthetic)
- **Category filter:** Clickable tag pills above the input. Toggle on/off, active ones highlighted. Categories: medical, water, shelter, fire, food, navigation, signaling, tools, first_aid
- **Response mode selector:** Toggle buttons (Full / Compact / Ultra) near the send button. Default to Full
- **Citation format:** Inline references in response text, as the pipeline already generates: (Source: FM 21-76, p.45)
- **Source linking:** Citations are clickable links that open locally-served source PDFs at the cited page. FastAPI serves PDFs from `sources/originals/` with page anchors. Works fully offline
- **Safety warnings:** Rendered as colored warning blocks (amber/red border) at the top of the response. Visually distinct from normal content
- **Source context:** Show LLM response only (no raw retrieved chunks panel). Citations themselves point to the source
- **CLI invocation:** Both single-shot and REPL. `survivalrag ask "query"` for one-off. `survivalrag` with no args drops into interactive REPL
- **CLI output formatting:** Rich markdown with color (using `rich` or similar). Bold warnings, colored headers. Field-manual style readable in terminal
- **CLI category filtering:** `--category` flag, comma-separated: `survivalrag ask --category medical,water "query"`
- **CLI response mode:** `--mode` flag: `survivalrag ask --mode compact "query"`. Default to full
- **Web disclaimer:** Persistent banner at top: "This is a reference tool, not medical advice. Never use as a substitute for professional medical care."
- **Web status bar:** Compact status line below the disclaimer showing: Ollama connection health (green/red), model name, knowledge base size (chunk count), active response mode
- **CLI disclaimer:** Short one-liner on REPL startup: "Reference tool only -- not medical advice." No disclaimer on single-shot mode (pipe-friendly)

### Claude's Discretion
- Citation verification failure display (how to present unverified citations to the user)
- Response mode toggle button styling to fit terminal-style layout
- Exact color scheme and terminal-style visual design details
- Rich markdown library choice for CLI output

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| WEBUI-01 | Browser-based chat interface accessible at localhost after Docker startup | Gradio `gr.Blocks` + `gr.mount_gradio_app()` on FastAPI; serves at localhost:7860 (or custom port). Gradio 6.8.0 includes its own uvicorn server. |
| WEBUI-02 | User can type a query and receive a streamed response with citations | `gen.answer_stream()` returns `(status, token_generator)`. Gradio chat function uses `yield` for streaming. Tokens flow directly from Ollama through pipeline to browser. |
| WEBUI-03 | Category filter selector allows scoping queries to specific topics | `gr.CheckboxGroup` or custom button pills with `elem_classes` + CSS. Pass selected categories to `gen.answer_stream(categories=[...])`. |
| WEBUI-04 | Citations displayed with source document name, section, and page number | Pipeline already generates inline `(Source: FM 21-76, p.45)` citations. Post-process response text to convert citation strings to clickable `<a href="/pdf/{agency}/{file}#page=N">` links. |
| WEBUI-05 | Visible disclaimer states this is a reference tool, not medical advice | `gr.Markdown` element with `elem_id="disclaimer"` at top of layout. Custom CSS for amber/red border styling. Persistent (not dismissable). |
| WEBUI-06 | System status indicator shows whether system is ready | FastAPI health endpoint checks Ollama connectivity + ChromaDB collection count. Status bar `gr.Markdown` element updated on page load and periodically. Shows model name, chunk count, connection status. |
| CLI-01 | User can query from the command line (`survivalrag ask "query"`) | Click `@cli.command()` for `ask` subcommand. Entry point via `[project.scripts]` in pyproject.toml or direct `python -m survivalrag`. |
| CLI-02 | Responses formatted for terminal output with markdown rendering | Rich `Console` + `Markdown` class renders LLM response with colors, bold warnings, numbered lists. Safety warnings rendered with Rich `Panel` in red/amber. |
| CLI-03 | Category filtering available via CLI flag | Click `@click.option("--category", ...)` with comma-separated parsing. Passes list to `gen.answer_stream(categories=[...])`. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| gradio | >=6.8.0 | Web chat UI framework | Python-native, built-in chat component, streaming via generators, theming system, mounts on FastAPI. Latest release 2026-02-27. |
| fastapi | (bundled by Gradio) | HTTP server, PDF serving, health endpoints | Gradio 6.x bundles FastAPI internally. Use `gr.mount_gradio_app()` to add custom routes for PDF serving. |
| uvicorn | (bundled by Gradio) | ASGI server | Bundled with Gradio; `gr.Blocks.launch()` or direct `uvicorn` invocation. |
| click | >=8.1 | CLI argument parsing | Industry standard for Python CLIs. Decorator-based subcommands, automatic help generation. |
| rich | >=14.0 | Terminal markdown rendering | Standard for rich terminal output. Markdown class renders bold, colors, code blocks, tables. Version 14.1.0 latest (2026-02-19). |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| starlette | (bundled by FastAPI) | StaticFiles mounting | Serve PDFs from `sources/originals/` via `app.mount("/pdf", StaticFiles(...))` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| gr.Blocks (full layout) | gr.ChatInterface (high-level) | ChatInterface is simpler but lacks control for custom banner, status bar, and category pills layout. Blocks required for this UI. |
| Click (CLI) | argparse (stdlib) | argparse has no dependencies but requires more boilerplate. Click provides better subcommand support and automatic help. |
| Rich (terminal) | plain print | Rich provides markdown rendering, colored panels for warnings, and table formatting that plain print cannot. |

**Installation:**
```bash
pip install "gradio>=6.8.0" "click>=8.1" "rich>=14.0"
```

## Architecture Patterns

### Recommended Project Structure
```
survivalrag/
├── web.py              # Gradio + FastAPI web server (main entry point for web UI)
├── cli.py              # Click-based CLI tool
├── pipeline/           # Existing pipeline modules (unchanged)
│   ├── generate.py     # gen.answer(), gen.answer_stream()
│   ├── retrieve.py     # retrieve.init(), retrieve.retrieve()
│   ├── prompt.py       # prompt.query()
│   └── ...
├── sources/
│   └── originals/      # PDF files served by FastAPI
├── ask.py              # Existing REPL proof-of-concept (superseded by cli.py)
└── requirements.txt    # Updated with gradio, click, rich
```

### Pattern 1: Gradio Blocks with Custom Layout
**What:** Use `gr.Blocks()` instead of `gr.ChatInterface()` for full control over layout.
**When to use:** When you need custom components (disclaimer banner, status bar, category pills) alongside the chatbot.
**Example:**
```python
# Source: https://www.gradio.app/guides/creating-a-custom-chatbot-with-blocks
import gradio as gr

with gr.Blocks(
    theme=terminal_theme,  # Custom dark theme
    css=CUSTOM_CSS,
    title="SurvivalRAG",
) as demo:
    # Disclaimer banner (persistent, not dismissable)
    gr.Markdown(
        "**DISCLAIMER:** This is a reference tool, not medical advice. "
        "Never use as a substitute for professional medical care.",
        elem_id="disclaimer",
    )

    # Status bar
    status = gr.Markdown("Checking system...", elem_id="status-bar")

    # Chatbot display
    chatbot = gr.Chatbot(
        height=500,
        layout="panel",
        render_markdown=True,
        elem_id="chatbot",
    )

    # Category pills (CheckboxGroup styled as pills via CSS)
    with gr.Row():
        categories = gr.CheckboxGroup(
            choices=["medical", "water", "shelter", "fire", "food",
                     "navigation", "signaling", "tools", "first_aid"],
            label="Categories",
            elem_id="category-pills",
        )

    # Input row
    with gr.Row():
        mode = gr.Radio(
            choices=["full", "compact", "ultra"],
            value="full",
            label="Mode",
            elem_id="mode-selector",
        )
        msg = gr.Textbox(
            placeholder="Ask a survival question...",
            show_label=False,
            scale=4,
        )
        submit = gr.Button("Send", scale=1)
```

### Pattern 2: Streaming Chat with Generator Function
**What:** Gradio streaming via Python generator that yields partial responses.
**When to use:** For the main chat response function.
**Example:**
```python
# Source: https://www.gradio.app/guides/creating-a-custom-chatbot-with-blocks
def respond(message, history, categories, mode):
    """Stream response tokens to Gradio chatbot."""
    # Add user message to history
    history = history + [{"role": "user", "content": message}]

    # Get streaming response from pipeline
    status, tokens = gen.answer_stream(
        query_text=message,
        categories=categories or None,
        mode=mode,
    )

    # Stream tokens to chatbot
    partial = ""
    for token in tokens:
        partial += token
        # Post-process: convert citations to clickable links
        display = post_process_citations(partial)
        yield history + [{"role": "assistant", "content": display}]
```

### Pattern 3: FastAPI + Gradio Mount for PDF Serving
**What:** Mount Gradio on a FastAPI app that also serves static PDF files.
**When to use:** When citations need to link to locally-served source PDFs.
**Example:**
```python
# Source: https://www.gradio.app/docs/gradio/mount_gradio_app
from fastapi import FastAPI
from starlette.staticfiles import StaticFiles
import gradio as gr

app = FastAPI()

# Health check endpoint
@app.get("/api/health")
def health():
    try:
        ollama.show(gen._model)
        return {"status": "ok", "model": gen._model, "chunks": collection.count()}
    except Exception:
        return {"status": "error"}

# Serve source PDFs for citation linking
app.mount("/pdf", StaticFiles(directory="sources/originals"), name="pdf")

# Mount Gradio at root
app = gr.mount_gradio_app(app, demo, path="/")
```

### Pattern 4: Click CLI with Subcommands
**What:** Click-based CLI with `ask` subcommand and REPL fallback.
**When to use:** For the `survivalrag` command-line tool.
**Example:**
```python
# Source: https://click.palletsprojects.com/en/stable/
import click
from rich.console import Console
from rich.markdown import Markdown

console = Console()

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """SurvivalRAG: Offline survival knowledge base."""
    if ctx.invoked_subcommand is None:
        # No subcommand -> enter REPL
        repl()

@cli.command()
@click.argument("query")
@click.option("--category", "-c", default=None, help="Comma-separated categories")
@click.option("--mode", "-m", default="full", type=click.Choice(["full", "compact", "ultra"]))
def ask(query, category, mode):
    """Ask a survival question."""
    categories = category.split(",") if category else None
    status, tokens = gen.answer_stream(query, categories=categories, mode=mode)
    response = "".join(tokens)
    console.print(Markdown(response))
```

### Pattern 5: Terminal-Style Gradio Theme
**What:** Custom Gradio theme with dark background, monospace fonts, sharp corners.
**When to use:** For the terminal-aesthetic web UI.
**Example:**
```python
# Source: https://www.gradio.app/guides/theming-guide
from gradio.themes.base import Base
from gradio.themes.utils import colors, fonts, sizes

class TerminalTheme(Base):
    def __init__(self):
        super().__init__(
            primary_hue=colors.green,      # Terminal green accent
            secondary_hue=colors.gray,
            neutral_hue=colors.gray,
            spacing_size=sizes.spacing_sm,
            radius_size=sizes.radius_none,  # Sharp corners
            text_size=sizes.text_md,
            font=(fonts.GoogleFont("JetBrains Mono"), "monospace"),
            font_mono=(fonts.GoogleFont("JetBrains Mono"), "monospace"),
        )
        super().set(
            body_background_fill="#0d1117",
            body_background_fill_dark="#0d1117",
            body_text_color="#c9d1d9",
            body_text_color_dark="#c9d1d9",
            block_background_fill="#161b22",
            block_background_fill_dark="#161b22",
            input_background_fill="#0d1117",
            input_background_fill_dark="#0d1117",
            button_primary_background_fill="#238636",
            button_primary_background_fill_dark="#238636",
        )
```

### Anti-Patterns to Avoid
- **Using ChatInterface instead of Blocks:** ChatInterface is convenient but cannot accommodate the disclaimer banner, status bar, or category pills in the required layout. Blocks is mandatory for this UI.
- **Re-implementing streaming:** The pipeline already provides `gen.answer_stream()` returning a Python generator. Do not buffer the full response before displaying -- yield tokens directly.
- **Client-side citation parsing with JavaScript:** Keep citation-to-link conversion in Python (server-side) before sending to Gradio. Gradio's markdown renderer handles `<a>` tags.
- **Installing a separate ASGI server:** Gradio bundles uvicorn. Do not add another server dependency.
- **Hard-coding PDF paths in citations:** Build PDF URLs dynamically from chunk metadata (`source_document` -> filename mapping via manifests).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Terminal markdown rendering | Custom ANSI escape code formatter | `rich.Markdown` + `rich.Console` | Rich handles bold, italic, code blocks, tables, colors, and terminal width detection |
| CLI argument parsing | Manual `sys.argv` parsing | Click decorators | Click handles subcommands, --help, type validation, error messages |
| Web chat UI framework | Custom HTML/JS/WebSocket server | Gradio `gr.Blocks` + `gr.Chatbot` | Gradio handles WebSocket streaming, message history, markdown rendering, responsive layout |
| PDF serving | Custom file server endpoint | `StaticFiles(directory=...)` from Starlette | Handles Content-Type, caching, range requests, security |
| Dark theme CSS | Manual CSS from scratch | Gradio theme class + `.set()` overrides | Theme system handles CSS variables, dark mode, component targeting consistently |
| REPL input loop | Manual `input()` loop with error handling | Click `invoke_without_command` + Rich prompt | Click handles REPL gracefully with Ctrl+C/Ctrl+D, Rich handles styled prompts |

**Key insight:** The pipeline already handles all the hard work (retrieval, generation, verification, safety warnings). The UI phase is purely presentation -- wiring existing `gen.answer_stream()` to two different output surfaces.

## Common Pitfalls

### Pitfall 1: Gradio Chatbot Message Format Mismatch
**What goes wrong:** Gradio 6.x uses OpenAI-style message format (`{"role": "user", "content": "..."}`) not the old tuple format.
**Why it happens:** Older Gradio examples use `[(user_msg, bot_msg)]` tuple format which is deprecated.
**How to avoid:** Always use dict format: `{"role": "user", "content": msg}` and `{"role": "assistant", "content": response}`.
**Warning signs:** TypeError or empty chatbot display.

### Pitfall 2: Blocking the Event Loop During Init
**What goes wrong:** `retrieve.init()` and `gen.init()` take time (loading BM25 index, validating Ollama model). If called inside a Gradio event handler, the UI freezes.
**Why it happens:** Pipeline initialization is synchronous and can take several seconds.
**How to avoid:** Call `retrieve.init()` and `gen.init()` BEFORE `demo.launch()`, at module import time. The status bar can update afterward.
**Warning signs:** UI shows "Loading..." forever, or first query times out.

### Pitfall 3: PDF Page Anchors Browser Compatibility
**What goes wrong:** `#page=N` fragment identifier works in Chrome and Firefox PDF viewers but behavior varies.
**Why it happens:** PDF fragment identifiers are not universally standardized. Chrome uses `#page=N`, Firefox (PDF.js) uses `#page=N` too but with caveats on first load.
**How to avoid:** Use the `#page=N` format which is the most widely supported. Accept that some browsers may not scroll to the exact page. This is a progressive enhancement, not a hard requirement.
**Warning signs:** PDF opens but does not scroll to the cited page.

### Pitfall 4: Gradio CSS Specificity Fights
**What goes wrong:** Custom CSS does not override Gradio's default styles.
**Why it happens:** Gradio's internal styles have high specificity. Custom CSS needs `!important` or high-specificity selectors.
**How to avoid:** Use `elem_id` on components and target with `#id` selectors. Use `!important` when needed. Test in browser DevTools.
**Warning signs:** Styles appear in CSS but components render with default appearance.

### Pitfall 5: Citation Link Construction from Metadata
**What goes wrong:** Citation text in LLM response does not exactly match metadata fields, making it impossible to construct PDF links.
**Why it happens:** Small LLMs produce inconsistent citation formats (abbreviated names, missing page numbers, etc.).
**How to avoid:** Use the same fuzzy matching from `generate.verify_citations()` to extract citation components. Map `source_document` metadata to actual PDF filenames using a lookup table. The pipeline already provides `verification.details` with matched sources.
**Warning signs:** Citation links point to wrong PDFs or have broken page anchors.

### Pitfall 6: Click Entry Point Not Working Without pyproject.toml
**What goes wrong:** `survivalrag` command is not available after `pip install -e .`.
**Why it happens:** No pyproject.toml or setup.py defines the console_scripts entry point.
**How to avoid:** Create a minimal pyproject.toml with `[project.scripts]` section. Alternatively, use `python -m survivalrag` with a `__main__.py` as the primary invocation (simpler, no packaging needed).
**Warning signs:** `command not found: survivalrag` after installation.

## Code Examples

### Complete Gradio Chat Function with Streaming
```python
# Verified pattern from Gradio 6.x docs + existing pipeline API
import pipeline.retrieve as retrieve
import pipeline.generate as gen

def chat_respond(message, history, selected_categories, mode):
    """Handle a chat message: stream response with citations.

    Args:
        message: User's query text.
        history: List of message dicts (OpenAI format).
        selected_categories: List of selected category strings (from CheckboxGroup).
        mode: Response mode string ("full", "compact", "ultra").

    Yields:
        Updated history with streaming assistant response.
    """
    if not message.strip():
        return

    # Add user message
    history = history + [{"role": "user", "content": message}]

    # Get streaming response
    categories = selected_categories if selected_categories else None
    status, tokens = gen.answer_stream(
        query_text=message,
        categories=categories,
        mode=mode,
    )

    # Stream tokens
    partial = ""
    for token in tokens:
        partial += token
        yield history + [{"role": "assistant", "content": partial}]
```

### Rich CLI Output with Warning Panels
```python
# Verified pattern from Rich 14.x docs
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

console = Console()

def display_response(response_text, warnings=None):
    """Render pipeline response in terminal with Rich formatting."""
    # Safety warnings first (amber/red panels)
    if warnings:
        for w in warnings:
            console.print(Panel(
                f"[bold]{w['warning_text']}[/bold]",
                title=f"WARNING -- {w['source_document']}, p.{w['page_number']}",
                border_style="red",
            ))

    # Main response as rendered markdown
    console.print(Markdown(response_text))
```

### Status Bar Health Check
```python
# Pattern for web UI status indicator
import ollama

def check_system_status():
    """Return formatted status string for web UI status bar."""
    parts = []

    # Ollama connection
    try:
        ollama.show(gen._model)
        parts.append(f"🟢 Ollama: {gen._model}")
    except Exception:
        parts.append("🔴 Ollama: disconnected")

    # Knowledge base size
    try:
        count = retrieve._collection.count()
        parts.append(f"📚 KB: {count:,} chunks")
    except Exception:
        parts.append("📚 KB: unavailable")

    return " | ".join(parts)
```

### Citation-to-Link Post-Processing
```python
import re

# Map source_document names to PDF file paths
# Built at startup from sources/manifests/*.yaml
_SOURCE_TO_PDF = {}  # e.g., {"FM 21-76": "military/FM-21-76.pdf"}

def citations_to_links(response_text):
    """Convert inline citations to clickable PDF links.

    Transforms (Source: FM 21-76, p.45) into markdown links
    that open the locally-served PDF at the cited page.
    """
    def replace_citation(match):
        doc_name = match.group(1).strip()
        page = match.group(2)

        # Look up PDF path
        pdf_path = _SOURCE_TO_PDF.get(doc_name)
        if pdf_path and page:
            return f"([Source: {doc_name}, p.{page}](/pdf/{pdf_path}#page={page}))"
        return match.group(0)  # Return unchanged if no mapping

    pattern = r'\(Source:\s*([^,]+),\s*p\.?(\d+)\)'
    return re.sub(pattern, replace_citation, response_text)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Gradio tuple chat format `[(user, bot)]` | OpenAI-style dict format `{"role": "...", "content": "..."}` | Gradio 5.x (2024) | Must use dict format in Gradio 6.x |
| `gr.ChatInterface` for everything | `gr.Blocks` for custom layouts | Ongoing | ChatInterface is still available but Blocks required for complex UIs |
| setup.py console_scripts | pyproject.toml `[project.scripts]` | PEP 621 (2021) | Modern projects use pyproject.toml for entry points |
| Custom ANSI formatting | Rich library | Rich 10+ (2021) | Rich is the de facto standard for terminal formatting in Python |
| Gradio default theme | Custom theme classes with `.set()` | Gradio 4.x+ | Full CSS variable control via Python API |

**Deprecated/outdated:**
- Gradio `gr.Interface` for chat: Use `gr.Blocks` or `gr.ChatInterface` instead
- Gradio tuple message format: Deprecated in favor of dict format
- `setup.py` for entry points: Use `pyproject.toml` for modern projects

## Open Questions

1. **Source document to PDF filename mapping**
   - What we know: Chunk metadata has `source_document` (e.g., "FM 21-76") and manifests in `sources/manifests/*.yaml` have document metadata including filenames.
   - What's unclear: The exact mapping from `source_document` string to `sources/originals/{agency}/{filename}.pdf` path. Need to inspect manifests at implementation time.
   - Recommendation: Build the mapping at startup by scanning manifests. Cache as a dict. If a citation cannot be mapped, render as plain text (no link).

2. **pyproject.toml creation for CLI entry point**
   - What we know: No pyproject.toml exists in the project. requirements.txt is the only dependency file.
   - What's unclear: Whether the user wants to create a full pyproject.toml or keep it simple.
   - Recommendation: Use `python -m survivalrag` with a `__main__.py` as the primary invocation. This requires no packaging changes. Add pyproject.toml with `[project.scripts]` entry point as a secondary invocation method if desired, but this is a Phase 8 (deployment/packaging) concern. For Phase 7, `python -m survivalrag` or direct `python cli.py` is sufficient.

3. **Gradio offline font loading**
   - What we know: Gradio theme uses `GoogleFont("JetBrains Mono")` which loads from Google Fonts CDN.
   - What's unclear: Whether Google Fonts work offline after initial load, or if they require internet.
   - Recommendation: Use system fonts as fallback: `font=("JetBrains Mono", "Cascadia Code", "Fira Code", "monospace")`. For fully offline operation, bundle a WOFF2 font file and reference it via custom CSS, or rely on system monospace fonts only.

## Sources

### Primary (HIGH confidence)
- [Gradio 6.8.0 PyPI](https://pypi.org/project/gradio/) - Version, Python support, release date
- [Gradio ChatInterface docs](https://www.gradio.app/docs/gradio/chatinterface) - API parameters, streaming support
- [Gradio Chatbot docs](https://www.gradio.app/docs/gradio/chatbot) - Message format, styling, markdown rendering
- [Gradio mount_gradio_app docs](https://www.gradio.app/docs/gradio/mount_gradio_app) - FastAPI integration, allowed_paths, static file serving
- [Gradio Theming Guide](https://www.gradio.app/guides/theming-guide) - Custom themes, CSS variables, dark mode, fonts
- [Gradio Custom CSS and JS](https://www.gradio.app/guides/custom-CSS-and-JS) - elem_id, elem_classes, css parameter
- [Gradio Controlling Layout](https://www.gradio.app/guides/controlling-layout) - Row, Column, Accordion, Sidebar
- [Gradio Creating Custom Chatbot with Blocks](https://www.gradio.app/guides/creating-a-custom-chatbot-with-blocks) - Full chatbot with Blocks, streaming
- [Rich 14.1.0 docs](https://rich.readthedocs.io/en/latest/markdown.html) - Markdown rendering in terminal
- [Rich PyPI](https://pypi.org/project/rich/) - Version, Python support
- [Click docs](https://click.palletsprojects.com/en/stable/) - Entry points, subcommands
- [FastAPI Static Files](https://fastapi.tiangolo.com/tutorial/static-files/) - StaticFiles mounting

### Secondary (MEDIUM confidence)
- [PDF Fragment Identifiers - PDF Association](https://pdfa.org/pdf-fragment-identifiers/) - `#page=N` browser support
- [Python Packaging User Guide - CLI tools](https://packaging.python.org/en/latest/guides/creating-command-line-tools/) - pyproject.toml entry points

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries verified via official docs and PyPI. Gradio 6.8.0 is current, Rich 14.1.0 is current, Click 8.x is stable.
- Architecture: HIGH - Pattern of mounting Gradio on FastAPI is well-documented. Blocks layout pattern verified in official guides. Pipeline API confirmed by reading source code.
- Pitfalls: HIGH - Message format change documented in Gradio docs. CSS specificity is a known Gradio pain point documented in guides. PDF fragment support verified via PDF Association spec.

**Research date:** 2026-03-02
**Valid until:** 2026-04-02 (30 days -- Gradio releases frequently but API is stable in 6.x)
