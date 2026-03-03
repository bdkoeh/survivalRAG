"""SurvivalRAG Web Chat UI -- Gradio + FastAPI with terminal-style dark theme.

Browser-based chat interface for the SurvivalRAG knowledge base. Provides:
- Terminal-style dark theme with monospace fonts and sharp corners
- Persistent disclaimer banner (reference tool, not medical advice)
- System status bar showing Ollama health, model name, and chunk count
- Category filter pills for scoping queries to specific topics
- Response mode toggle (Full / Compact / Ultra)
- Streaming chat responses with token-by-token display
- Clickable citation links to locally-served source PDFs with page anchors
- Safety warnings displayed as visually distinct colored blocks

Architecture: Gradio Blocks mounted on FastAPI via gr.mount_gradio_app().
FastAPI serves source PDFs from sources/originals/ at /pdf/ for citation linking.
Pipeline initialization (retrieve.init, gen.init) happens BEFORE the server starts.

Usage:
    python web.py
"""

import logging
import os
import re
from pathlib import Path
from typing import Iterator

import gradio as gr
import yaml
from fastapi import FastAPI
from gradio.themes import Soft
from starlette.staticfiles import StaticFiles

import pipeline.generate as gen
import pipeline.retrieve as retrieve
from pipeline.rewrite import rewrite_with_context

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Source-to-PDF mapping (built at startup from manifests)
# ---------------------------------------------------------------------------

_SOURCE_TO_PDF: dict[str, str] = {}

# Map publisher strings from manifests to subdirectory names in sources/originals/
_PUBLISHER_TO_DIR: dict[str, str] = {
    "Department of the Army": "military",
    "US Army": "military",
    "US Marine Corps": "military",
    "US Navy": "military",
    "Department of the Air Force": "usaf",
    "USAF": "usaf",
    "FEMA": "fema",
    "FEMA / American Red Cross": "fema",
    "CDC": "cdc",
    "EPA": "epa",
    "USDA": "usda",
    "USDA FSIS": "usda",
    "NOAA": "noaa",
    "NWS": "noaa",
    "USCG": "uscg",
    "NPS": "nps",
    "DHS": "dhs",
    "HHS": "hhs",
}


def build_source_map() -> None:
    """Scan sources/manifests/*.yaml to build source_document -> PDF relative path mapping.

    Populates _SOURCE_TO_PDF with entries mapping document designations and titles
    to their relative PDF paths under sources/originals/ (e.g. "military/FM-21-76.pdf").
    """
    manifests_dir = Path("sources/manifests")
    if not manifests_dir.exists():
        logger.warning("Manifests directory not found: %s", manifests_dir)
        return

    count = 0
    for manifest_path in sorted(manifests_dir.glob("*.yaml")):
        try:
            with open(manifest_path) as f:
                data = yaml.safe_load(f)

            if not data:
                continue

            doc = data.get("document", {})
            source = data.get("source", {})

            file_name = doc.get("file_name", "")
            title = doc.get("title", "")
            designation = doc.get("designation", "")
            publisher = source.get("publisher", "")

            if not file_name:
                continue

            # Resolve subdirectory from publisher
            subdir = _PUBLISHER_TO_DIR.get(publisher)
            if not subdir:
                # Try partial matching for compound publisher names
                for pub_key, pub_dir in _PUBLISHER_TO_DIR.items():
                    if pub_key in publisher or publisher in pub_key:
                        subdir = pub_dir
                        break

            if not subdir:
                logger.debug(
                    "Unknown publisher '%s' for %s, skipping", publisher, file_name
                )
                continue

            relative_path = f"{subdir}/{file_name}"

            # Map by designation (e.g. "FM 21-76") -- primary key
            if designation:
                _SOURCE_TO_PDF[designation] = relative_path
                count += 1

            # Map by title as fallback (e.g. "US Army Survival Manual")
            if title and title != designation:
                _SOURCE_TO_PDF[title] = relative_path
                count += 1

        except Exception:
            logger.warning("Failed to parse manifest: %s", manifest_path, exc_info=True)

    logger.info("Source-to-PDF mapping built: %d entries from manifests", count)


# ---------------------------------------------------------------------------
# Terminal-style Gradio theme
# ---------------------------------------------------------------------------

DARK_THEME = Soft(
    primary_hue="green",
    neutral_hue="gray",
)


# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

CUSTOM_CSS = """
#page-title { font-size: 2rem; margin: 0 0 8px 0; font-weight: 700; }
/* Hide settings gear and footer */
button[aria-label="Settings"], [id*="settings"] { display: none !important; }
footer { display: none !important; }
#disclaimer {
    text-align: center;
    font-size: 0.8em;
    opacity: 0.5;
    margin: 8px 0 0 0;
    padding: 0;
}
#status-bar {
    font-size: 0.85em !important;
    padding: 4px 16px !important;
    opacity: 0.8;
}
/* Safety warning blocks in responses */
.warning-block {
    border-left: 4px solid #d29922;
    background: #1a1200;
    padding: 8px 12px;
    margin-bottom: 8px;
}
.danger-block {
    border-left: 4px solid #da3633;
    background: #1a0000;
    padding: 8px 12px;
    margin-bottom: 8px;
}
"""


# ---------------------------------------------------------------------------
# Citation-to-link post-processing
# ---------------------------------------------------------------------------

# Pattern: (Source: DocName, p.N) or (Source: DocName, p. N)
_CITATION_PATTERN = re.compile(
    r'\(Source:\s*([^,\)]+?),\s*p\.?\s*(\d+)\)'
)

# Extended pattern: (Source: DocName, Section: X, Page: N)
_CITATION_PATTERN_EXT = re.compile(
    r'\(Source:\s*([^,\)]+?),\s*Section:\s*[^,]+,\s*Page:\s*(\d+)\)'
)


def citations_to_links(response_text: str) -> str:
    """Convert inline (Source: DocName, p.N) citations to clickable markdown links.

    Looks up each cited document in _SOURCE_TO_PDF and replaces the citation text
    with a markdown link pointing to /pdf/{subdir}/{filename}#page={N}. If no
    mapping is found, the citation is left as plain text.

    Also handles the (Source: DocName, Section: X, Page: N) variant.
    """

    def _replace(match: re.Match) -> str:
        doc_name = match.group(1).strip()
        page = match.group(2)

        # Try exact match first
        pdf_path = _SOURCE_TO_PDF.get(doc_name)

        # Try substring match if exact match fails
        if not pdf_path:
            for key, path in _SOURCE_TO_PDF.items():
                if doc_name.lower() in key.lower() or key.lower() in doc_name.lower():
                    pdf_path = path
                    break

        if pdf_path and page:
            return f"([Source: {doc_name}, p.{page}](/pdf/{pdf_path}#page={page}))"
        return match.group(0)

    # Process extended pattern first (more specific), then standard pattern
    result = _CITATION_PATTERN_EXT.sub(_replace, response_text)
    result = _CITATION_PATTERN.sub(_replace, result)
    return result


# ---------------------------------------------------------------------------
# Safety warning HTML formatter
# ---------------------------------------------------------------------------

def format_warnings_html(warnings: list[dict]) -> str:
    """Format safety warnings as styled HTML blocks for chatbot display.

    Args:
        warnings: List of warning dicts from collect_safety_warnings(), each with
            keys: source_document, section_header, warning_level, warning_text, page_number.

    Returns:
        Joined HTML string of styled warning blocks, or empty string if no warnings.
    """
    if not warnings:
        return ""

    blocks: list[str] = []
    for w in warnings:
        level = w.get("warning_level", "warning")
        css_class = "danger-block" if level == "danger" else "warning-block"
        source = w.get("source_document", "Unknown")
        page = w.get("page_number", "?")
        text = w.get("warning_text", "")

        block = (
            f'<div class="{css_class}">'
            f"<strong>WARNING</strong> (Source: {source}, p.{page}): {text}"
            f"</div>"
        )
        blocks.append(block)

    return "\n".join(blocks)


# ---------------------------------------------------------------------------
# System status check
# ---------------------------------------------------------------------------

def check_system_status() -> str:
    """Return formatted markdown status string for the status bar.

    Checks Ollama connectivity, model name, and knowledge base chunk count.
    Uses text-based indicators ([OK] / [ERR]) for terminal aesthetic.
    """
    parts: list[str] = []

    # Ollama connection check
    try:
        import ollama as _ollama
        _ollama.show(gen._model)
        parts.append(f"[OK] Ollama: {gen._model}")
    except Exception:
        parts.append("[ERR] Ollama: disconnected")

    # Knowledge base chunk count
    try:
        count = retrieve._collection.count()
        parts.append(f"KB: {count:,} chunks")
    except Exception:
        parts.append("KB: unavailable")

    return " | ".join(parts)


# ---------------------------------------------------------------------------
# Streaming chat handler
# ---------------------------------------------------------------------------

def _extract_text(content) -> str:
    """Extract plain text from Gradio 6 content (list of dicts or string)."""
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict))
    return content or ""


def _history_to_plain(history: list[dict]) -> list[dict]:
    """Convert Gradio 6 history to plain string dicts for the rewriter."""
    return [
        {"role": m.get("role", "user"), "content": _extract_text(m.get("content", ""))}
        for m in history
    ]


def add_user_message(
    message: str,
    history: list[dict],
) -> tuple[str, list[dict]]:
    """Add user message to chat and clear the input box immediately."""
    if not message or not message.strip():
        return "", history
    history = history + [{"role": "user", "content": message}]
    return "", history


def chat_respond(
    history: list[dict],
) -> Iterator[list[dict]]:
    """Stream response tokens to Gradio chatbot with citation links and warnings.

    Args:
        history: Chat history as list of OpenAI-style message dicts.

    Yields:
        Updated history list with streaming assistant response.
    """
    if not history:
        return

    # Extract plain text from Gradio 6 content format
    message = _extract_text(history[-1].get("content", ""))
    if not message or not message.strip():
        return

    try:
        query_text = rewrite_with_context(message, _history_to_plain(history))
        status, tokens = gen.answer_stream(
            query_text=query_text,
            categories=None,
            mode="full",
        )

        if status == "refused":
            refusal_text = "".join(tokens)
            yield history + [{"role": "assistant", "content": refusal_text}]
            return

        # Stream tokens
        partial = ""
        for token in tokens:
            partial += token
            yield history + [{"role": "assistant", "content": partial}]

        # Post-process: convert citations to clickable PDF links
        final_text = citations_to_links(partial)

        # Prepend safety warnings if available
        try:
            from pipeline.prompt import collect_safety_warnings

            chunks = retrieve.retrieve(message, categories=None)
            warnings = collect_safety_warnings(chunks)
            warning_html = format_warnings_html(warnings)
            if warning_html:
                final_text = warning_html + "\n\n" + final_text
        except Exception:
            logger.debug("Could not collect safety warnings", exc_info=True)

        yield history + [{"role": "assistant", "content": final_text}]

    except ConnectionError:
        yield history + [{"role": "assistant", "content": "Ollama is not running. Please start Ollama and refresh the page."}]
    except RuntimeError as e:
        yield history + [{"role": "assistant", "content": f"Error: {e}"}]
    except Exception:
        logger.error("Unexpected error in chat handler", exc_info=True)
        yield history + [{"role": "assistant", "content": "An unexpected error occurred. Check the server logs for details."}]


# ---------------------------------------------------------------------------
# Gradio Blocks layout
# ---------------------------------------------------------------------------

demo = gr.Blocks(
    title="SurvivalRAG",
)

with demo:
    # Page title
    gr.HTML('<h1 id="page-title">survival<span style="color:#22c55e">RAG</span></h1>')

    # Status bar (updated on page load)
    status_bar = gr.Markdown("Checking system...", elem_id="status-bar")

    # Chat display
    chatbot = gr.Chatbot(
        height=500,
        elem_id="chatbot",
    )

    # Input row: text input, send button
    with gr.Row():
        msg_textbox = gr.Textbox(
            placeholder="Ask a survival question...",
            show_label=False,
            scale=4,
        )
        submit_btn = gr.Button("Send", variant="primary", scale=1)

    # Wire events: clear input + show user message, then stream response
    submit_btn.click(
        fn=add_user_message,
        inputs=[msg_textbox, chatbot],
        outputs=[msg_textbox, chatbot],
    ).then(
        fn=chat_respond,
        inputs=[chatbot],
        outputs=[chatbot],
    )

    msg_textbox.submit(
        fn=add_user_message,
        inputs=[msg_textbox, chatbot],
        outputs=[msg_textbox, chatbot],
    ).then(
        fn=chat_respond,
        inputs=[chatbot],
        outputs=[chatbot],
    )

    gr.HTML('<p id="disclaimer">This is a reference tool, not a substitute for professional medical care.</p>')

    # Update status bar on page load
    demo.load(
        fn=lambda: check_system_status(),
        outputs=[status_bar],
    )


# ---------------------------------------------------------------------------
# FastAPI app with PDF serving and Gradio mount
# ---------------------------------------------------------------------------

app = FastAPI(title="SurvivalRAG")


@app.get("/api/health")
def health() -> dict:
    """Health check endpoint for monitoring."""
    status_info: dict = {"status": "ok"}
    try:
        import ollama as _ollama
        _ollama.show(gen._model)
        status_info["model"] = gen._model
        status_info["ollama"] = "connected"
    except Exception:
        status_info["ollama"] = "disconnected"
        status_info["status"] = "degraded"

    try:
        status_info["chunks"] = retrieve._collection.count()
    except Exception:
        status_info["chunks"] = None

    return status_info


# Serve source PDFs for citation linking
_pdf_dir = Path("sources/originals")
if _pdf_dir.exists():
    app.mount("/pdf", StaticFiles(directory=str(_pdf_dir)), name="pdf")
else:
    logger.warning("PDF directory not found: %s -- citation links will not work", _pdf_dir)

# Mount Gradio at root
app = gr.mount_gradio_app(
    app, demo, path="/",
    theme=DARK_THEME,
    css=CUSTOM_CSS,
    app_kwargs={"default_config": {"theme_mode": "dark"}},
)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Build source-to-PDF mapping from manifests
    build_source_map()

    # Initialize pipeline BEFORE server starts (Pitfall 2 from RESEARCH.md)
    retrieve.init(chroma_path="./data/chroma")
    gen.init()

    logger.info("Starting SurvivalRAG web UI at http://0.0.0.0:7860")
    uvicorn.run(app, host="0.0.0.0", port=7860)
