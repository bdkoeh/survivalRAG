"""LLM response generation via Ollama with streaming and mode-specific prompts.

Provides the core generation engine for SurvivalRAG: model validation at startup,
streaming token-by-token generation via Python generator, and three response modes
(full, compact, ultra) with distinct system prompts and safe parameter defaults
locked for medical/survival content.

Temperature and generation parameters are locked to safe defaults and are NOT
user-configurable -- this prevents hallucination-prone high-temperature settings
on medical/safety content.

Usage:
    import pipeline.generate as gen
    gen.init()  # validates model is available
    for token in gen.generate_stream(prompt, mode="full"):
        print(token, end="", flush=True)
"""

import logging
import os
from typing import Iterator, Optional

import ollama

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state (matching retrieve.py / embed.py pattern)
# ---------------------------------------------------------------------------
_model: str = ""
_validated: bool = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default generation model -- 2GB, 128K context, good instruction-following
DEFAULT_MODEL = "llama3.2:3b"

# Locked medical/safety generation defaults -- NOT user-configurable.
# Low temperature + tight top-p/top-k to minimize hallucination on medical content.
_SAFE_OPTIONS: dict = {
    "temperature": 0.2,
    "top_p": 0.85,
    "top_k": 20,
    "repeat_penalty": 1.1,
    "num_ctx": 8192,  # Prevents silent context truncation (Pitfall 2 from research)
}

# Per-mode token limits (num_predict)
_MODE_OPTIONS: dict = {
    "full": 1024,
    "compact": 512,
    "ultra": 80,
}

# ---------------------------------------------------------------------------
# System prompts -- one per mode (single LLM call per query, no post-processing)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_FULL = (
    "You are a survival and emergency preparedness reference tool. You provide "
    "information from official US government field manuals, medical handbooks, "
    "and emergency guides.\n"
    "\n"
    "RULES:\n"
    "- Answer ONLY using the reference context provided below. Do not use your "
    "own knowledge.\n"
    "- If the provided context does not contain enough information to answer, "
    "say so clearly.\n"
    "- Cite your sources as (Source: <document name>, p.<page>).\n"
    "- Number steps for procedures. Use bullets for lists.\n"
    "- Bold all safety warnings with **WARNING:**.\n"
    "- Start with safety warnings BEFORE the answer when warnings are present.\n"
    "- Never diagnose conditions.\n"
    "\n"
    "You are a reference tool, NOT a medical provider. Never diagnose conditions."
)

SYSTEM_PROMPT_COMPACT = (
    "You are a survival and emergency preparedness reference tool.\n"
    "\n"
    "RULES:\n"
    "- Answer ONLY from the provided context. Max 3-4 short paragraphs.\n"
    "- Cite sources by document name and page.\n"
    "- Bold all safety warnings with **WARNING:**.\n"
    "- Never diagnose conditions.\n"
    "\n"
    "You are a reference tool, NOT a medical provider."
)

SYSTEM_PROMPT_ULTRA = (
    "Survival reference tool. Under 200 chars. Telegram style: short phrases, "
    "no articles. Include critical safety warnings. No citations. Never diagnose."
)


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def init(model: Optional[str] = None) -> None:
    """Validate and set the generation model.

    Checks that the specified model is available via Ollama. If no model is
    provided, checks the SURVIVALRAG_MODEL environment variable, then falls
    back to DEFAULT_MODEL.

    Args:
        model: Model name to use for generation. If None, uses env var or default.

    Raises:
        RuntimeError: If the model is not available in Ollama.
        ConnectionError: If Ollama is not running.
    """
    global _model, _validated

    # Resolve model: argument > env var > default
    if model:
        _model = model
    else:
        _model = os.environ.get("SURVIVALRAG_MODEL", DEFAULT_MODEL)

    # Validate model is available via ollama.show()
    try:
        ollama.show(_model)
    except ollama.ResponseError:
        raise RuntimeError(
            f"Model '{_model}' is not available. "
            f"Run: ollama pull {_model}"
        )
    except Exception as e:
        if "connection" in str(e).lower() or "refused" in str(e).lower():
            raise ConnectionError(
                "Ollama is not running. Start it with: ollama serve"
            )
        raise

    _validated = True
    logger.info("Generation engine initialized with model: %s", _model)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_system_prompt(mode: str) -> str:
    """Return the system prompt for the given response mode.

    Args:
        mode: One of "full", "compact", "ultra".

    Returns:
        The system prompt string for the mode.

    Raises:
        ValueError: If mode is not recognized.
    """
    prompts = {
        "full": SYSTEM_PROMPT_FULL,
        "compact": SYSTEM_PROMPT_COMPACT,
        "ultra": SYSTEM_PROMPT_ULTRA,
    }
    if mode not in prompts:
        raise ValueError(
            f"Unknown response mode '{mode}'. Must be one of: full, compact, ultra"
        )
    return prompts[mode]


def _get_options(mode: str) -> dict:
    """Build Ollama generation options for the given response mode.

    Starts with the locked safe defaults and overrides num_predict based
    on the mode's token limit.

    Args:
        mode: One of "full", "compact", "ultra".

    Returns:
        Options dict for ollama.generate().
    """
    options = _SAFE_OPTIONS.copy()
    options["num_predict"] = _MODE_OPTIONS[mode]
    return options


# ---------------------------------------------------------------------------
# Generation functions
# ---------------------------------------------------------------------------

def generate_stream(prompt: str, mode: str = "full") -> Iterator[str]:
    """Stream LLM response tokens for the given prompt.

    Yields tokens one at a time as they are generated. The caller can print
    them directly (CLI) or wrap in SSE (web UI).

    Uses ollama.generate() (NOT ollama.chat()) because the prompt from
    assemble_prompt() is a pre-assembled string. The system prompt is passed
    separately via the `system` parameter.

    Args:
        prompt: The assembled context+query prompt string.
        mode: Response mode ("full", "compact", "ultra"). Controls system
            prompt and token limit.

    Yields:
        Non-empty token strings as they are generated.

    Raises:
        RuntimeError: If init() has not been called.
        ValueError: If mode is not recognized.
    """
    if not _validated:
        raise RuntimeError(
            "Generation engine not initialized. Call init() first."
        )

    system = _get_system_prompt(mode)
    options = _get_options(mode)

    logger.debug("Generating response: mode=%s, model=%s", mode, _model)

    response = ollama.generate(
        model=_model,
        prompt=prompt,
        system=system,
        options=options,
        stream=True,
    )

    for chunk in response:
        # Handle both attribute and dict access (Ollama version compat)
        if hasattr(chunk, "response"):
            token = chunk.response
        else:
            token = chunk.get("response", "")

        if token:
            yield token


def generate(prompt: str, chunks: list[dict], mode: str = "full") -> dict:
    """Generate a complete LLM response and return as structured dict.

    Collects all tokens from generate_stream() and returns the full response
    in a structured dict that serves as the Phase 5 -> Phase 6/7 contract.

    The `chunks` parameter is accepted for the verification step that will
    be added by Plan 05-02. Currently unused.

    Args:
        prompt: The assembled context+query prompt string.
        chunks: Retrieved chunks (for future citation verification).
        mode: Response mode ("full", "compact", "ultra").

    Returns:
        Dict with keys:
        - response: The full response text.
        - mode: The response mode used.
        - model: The model name used.
        - verification: None (populated by Plan 05-02).
    """
    tokens = list(generate_stream(prompt, mode=mode))
    response_text = "".join(tokens)

    logger.info(
        "Generated response: mode=%s, length=%d chars",
        mode,
        len(response_text),
    )

    return {
        "response": response_text,
        "mode": mode,
        "model": _model,
        "verification": None,  # Populated by Plan 05-02
    }
