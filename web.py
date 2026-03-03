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
from gradio.themes.base import Base
from gradio.themes.utils import colors, sizes
from starlette.staticfiles import StaticFiles

import pipeline.generate as gen
import pipeline.retrieve as retrieve

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

class TerminalTheme(Base):
    """Dark terminal-style theme with monospace fonts and sharp corners."""

    def __init__(self) -> None:
        super().__init__(
            primary_hue=colors.green,
            secondary_hue=colors.gray,
            neutral_hue=colors.gray,
            radius_size=sizes.radius_none,
            font=("JetBrains Mono", "Cascadia Code", "Fira Code", "monospace"),
            font_mono=("JetBrains Mono", "Cascadia Code", "Fira Code", "monospace"),
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


# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

CUSTOM_CSS = """
#disclaimer {
    background: #1a1200 !important;
    border: 2px solid #d29922 !important;
    border-radius: 0 !important;
    padding: 8px 16px !important;
    margin-bottom: 4px !important;
}
#status-bar {
    font-size: 0.85em !important;
    padding: 4px 16px !important;
    opacity: 0.8;
}
#category-pills label {
    border: 1px solid #30363d !important;
    border-radius: 2px !important;
    padding: 4px 10px !important;
    font-size: 0.85em !important;
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

def chat_respond(
    message: str,
    history: list[dict],
    selected_categories: list[str],
    mode: str,
) -> Iterator[list[dict]]:
    """Stream response tokens to Gradio chatbot with citation links and warnings.

    This is a generator function that yields updated chat history with each new
    token from the LLM. After streaming completes, a final yield includes
    post-processed citations (converted to clickable PDF links) and prepended
    safety warning blocks.

    Args:
        message: The user's query text.
        history: Chat history as list of OpenAI-style message dicts.
        selected_categories: List of selected category strings from CheckboxGroup.
        mode: Response mode ("full", "compact", "ultra").

    Yields:
        Updated history list with streaming assistant response.
    """
    if not message or not message.strip():
        return

    # Add user message to history
    history = history + [{"role": "user", "content": message}]

    try:
        categories = selected_categories if selected_categories else None
        status, tokens = gen.answer_stream(
            query_text=message,
            categories=categories,
            mode=mode,
        )

        if status == "refused":
            # Refusal: yield the single refusal message
            refusal_text = "".join(tokens)
            yield history + [{"role": "assistant", "content": refusal_text}]
            return

        # Stream tokens -- yield raw partial text during streaming
        partial = ""
        for token in tokens:
            partial += token
            yield history + [{"role": "assistant", "content": partial}]

        # After streaming completes: post-process the final response
        # 1. Convert citations to clickable PDF links
        final_text = citations_to_links(partial)

        # 2. Prepend safety warnings if available
        try:
            from pipeline.prompt import collect_safety_warnings

            chunks = retrieve.retrieve(message, categories=categories)
            warnings = collect_safety_warnings(chunks)
            warning_html = format_warnings_html(warnings)
            if warning_html:
                final_text = warning_html + "\n\n" + final_text
        except Exception:
            logger.debug("Could not collect safety warnings", exc_info=True)

        # Final yield with fully post-processed response
        yield history + [{"role": "assistant", "content": final_text}]

    except ConnectionError:
        error_msg = (
            "Ollama is not running. Please start Ollama and refresh the page."
        )
        yield history + [{"role": "assistant", "content": error_msg}]
    except RuntimeError as e:
        yield history + [{"role": "assistant", "content": f"Error: {e}"}]
    except Exception:
        logger.error("Unexpected error in chat handler", exc_info=True)
        yield history + [
            {"role": "assistant", "content": "An unexpected error occurred. Check the server logs for details."}
        ]


# ---------------------------------------------------------------------------
# Gradio Blocks layout
# ---------------------------------------------------------------------------

demo = gr.Blocks(
    theme=TerminalTheme(),
    css=CUSTOM_CSS,
    title="SurvivalRAG",
)

with demo:
    # Persistent disclaimer banner
    gr.Markdown(
        "**DISCLAIMER:** This is a reference tool, not medical advice. "
        "Never use as a substitute for professional medical care.",
        elem_id="disclaimer",
    )

    # Status bar (updated on page load)
    status_bar = gr.Markdown("Checking system...", elem_id="status-bar")

    # Chat display
    chatbot = gr.Chatbot(
        height=500,
        elem_id="chatbot",
        type="messages",
    )

    # Category filter pills
    with gr.Row():
        categories = gr.CheckboxGroup(
            choices=[
                "medical", "water", "shelter", "fire", "food",
                "navigation", "signaling", "tools", "first_aid",
            ],
            label="Filter by category",
            elem_id="category-pills",
        )

    # Input row: mode selector, text input, send button
    with gr.Row():
        mode_radio = gr.Radio(
            choices=["full", "compact", "ultra"],
            value="full",
            label="Mode",
            elem_id="mode-selector",
        )
        msg_textbox = gr.Textbox(
            placeholder="Ask a survival question...",
            show_label=False,
            scale=4,
        )
        submit_btn = gr.Button("Send", variant="primary", scale=1)

    # Wire events: submit button click and textbox enter
    submit_btn.click(
        fn=chat_respond,
        inputs=[msg_textbox, chatbot, categories, mode_radio],
        outputs=[chatbot],
    ).then(
        fn=lambda: "",
        outputs=[msg_textbox],
    )

    msg_textbox.submit(
        fn=chat_respond,
        inputs=[msg_textbox, chatbot, categories, mode_radio],
        outputs=[chatbot],
    ).then(
        fn=lambda: "",
        outputs=[msg_textbox],
    )

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
app = gr.mount_gradio_app(app, demo, path="/")


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
