"""LLM response generation with citation verification and full pipeline integration.

Provides the complete generation engine for SurvivalRAG: model validation at startup,
streaming token-by-token generation via Python generator, three response modes
(full, compact, ultra) with distinct system prompts, citation verification via
fuzzy matching against source documents, and full pipeline entry points that wire
query -> retrieve -> prompt -> generate -> verify into a single call.

Temperature and generation parameters are locked to safe defaults and are NOT
user-configurable -- this prevents hallucination-prone high-temperature settings
on medical/safety content.

Exports:
    init            - Validate and set generation model
    generate_stream - Stream LLM tokens (Python generator)
    generate        - Generate complete response with verification
    answer          - Full pipeline entry point (query -> response)
    answer_stream   - Streaming pipeline entry point
    extract_citations - Extract citations from response text
    verify_citations  - Verify citations against source documents

Usage:
    import pipeline.generate as gen
    gen.init()  # validates model is available

    # Full pipeline (preferred):
    result = gen.answer("how to purify water")

    # Streaming:
    status, tokens = gen.answer_stream("how to purify water")
    for token in tokens:
        print(token, end="", flush=True)
"""

import logging
import os
import re
from difflib import SequenceMatcher
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
# Citation verification
# ---------------------------------------------------------------------------

# Regex patterns for extracting citations from LLM responses.
# Small LLMs produce inconsistent citation formats (Pitfall 3 from research),
# so we match several common patterns.
_CITATION_PATTERNS: list[re.Pattern] = [
    re.compile(r'\(Source:\s*([^,\)]+)'),          # (Source: FM 21-76, ...)
    re.compile(r'\[([^\]]+?)(?:,\s*p\.?\s*\d+)?\]'),  # [FM 21-76, p.45]
    re.compile(r'\(([A-Z][A-Z\s\-\d\.]+\d+)\)'),  # (FM 21-76)
    re.compile(r'(?:per|from|in)\s+([A-Z][A-Z\s\-\d\.]+\d+)'),  # per FM 21-76
]


def extract_citations(response_text: str) -> list[str]:
    """Extract citation references from LLM response text.

    Uses multiple regex patterns to handle the inconsistent citation formats
    produced by small LLMs. Deduplicates and normalizes results.

    Args:
        response_text: The raw LLM response text.

    Returns:
        List of unique citation strings (e.g., ["FM 21-76", "FM 3-05.70"]).
    """
    found: set[str] = set()

    for pattern in _CITATION_PATTERNS:
        for match in pattern.finditer(response_text):
            citation = match.group(1).strip()
            if citation:
                found.add(citation)

    return list(found)


def verify_citations(
    response_text: str,
    retrieved_chunks: list[dict],
    threshold: float = 0.6,
) -> dict:
    """Verify that citations in the response match retrieved source documents.

    Post-generation verification: extracts citations from the response text and
    fuzzy-matches them against the source_document metadata of retrieved chunks.
    Results are both logged and returned as structured data for Phase 6 evaluation.

    Args:
        response_text: The LLM response text containing citations.
        retrieved_chunks: The chunks that were used to build the prompt.
        threshold: Minimum similarity score for a citation to be considered
            verified. Default 0.6 handles abbreviations and partial titles.

    Returns:
        Structured dict with verification results:
        - passed: True if ALL citations verified (or none found)
        - citations_found: Number of unique citations extracted
        - citations_verified: Number successfully matched to sources
        - citations_failed: Number that could not be matched
        - details: List of per-citation match results
        - note: Optional explanatory note
    """
    citations = extract_citations(response_text)

    if not citations:
        return {
            "passed": True,
            "citations_found": 0,
            "citations_verified": 0,
            "citations_failed": 0,
            "details": [],
            "note": "No citations found in response",
        }

    # Collect unique source_document values from chunk metadata
    source_docs: set[str] = set()
    for chunk in retrieved_chunks:
        metadata = chunk.get("metadata", {})
        source_doc = metadata.get("source_document")
        if source_doc:
            source_docs.add(source_doc)

    details: list[dict] = []
    verified_count = 0

    for citation in citations:
        best_score = 0.0
        best_source: Optional[str] = None

        for source in source_docs:
            # Fast path: substring match
            if citation.lower() in source.lower() or source.lower() in citation.lower():
                best_score = 1.0
                best_source = source
                break

            # Slow path: fuzzy matching
            score = SequenceMatcher(None, citation.lower(), source.lower()).ratio()
            if score > best_score:
                best_score = score
                best_source = source

        is_verified = best_score >= threshold
        if is_verified:
            verified_count += 1

        details.append({
            "citation": citation,
            "matched_source": best_source if is_verified else None,
            "score": round(best_score, 3),
            "verified": is_verified,
        })

    failed_count = len(citations) - verified_count
    passed = failed_count == 0

    logger.info(
        "Citation verification: %d found, %d verified, %d failed, passed=%s",
        len(citations),
        verified_count,
        failed_count,
        passed,
    )

    return {
        "passed": passed,
        "citations_found": len(citations),
        "citations_verified": verified_count,
        "citations_failed": failed_count,
        "details": details,
    }


# ---------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------

def _post_process(text: str, mode: str = "full") -> str:
    """Apply light structural formatting to LLM output.

    CRITICAL: Never modifies content words, dosages, or measurements --
    strictly structural formatting only. Enforces bold safety warnings and
    consistent numbered step formatting for field-manual style output.

    Args:
        text: The raw LLM response text.
        mode: Response mode ("full", "compact", "ultra").

    Returns:
        Formatted response text.
    """
    if mode == "ultra":
        # Ultra mode: truncate to ~200 chars at sentence boundary
        if len(text) > 220:
            # Find last sentence boundary before 200 chars
            truncated = text[:200]
            last_period = truncated.rfind(".")
            last_excl = truncated.rfind("!")
            boundary = max(last_period, last_excl)

            if boundary > 100:
                text = text[: boundary + 1]
            else:
                text = text[:200] + "..."
        return text

    # Full and compact modes: structural formatting only
    # Ensure WARNING/CAUTION/DANGER lines are bold
    text = re.sub(
        r"(?m)^(WARNING|CAUTION|DANGER):\s*",
        r"**\1:** ",
        text,
    )

    # Ensure numbered steps have consistent formatting
    text = re.sub(r"(?m)^(\d+)[.\)]\s*", r"\1. ", text)

    return text


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
    """Generate a complete LLM response with post-processing and citation verification.

    Collects all tokens from generate_stream(), applies structural post-processing,
    and runs citation verification against retrieved chunks. Returns the full response
    in a structured dict that serves as the Phase 5 -> Phase 6/7 contract.

    Post-generation verification runs AFTER full response is complete, NOT during
    streaming (Pitfall 4 from research). On verification failure the response is
    kept but a visible warning is appended.

    Args:
        prompt: The assembled context+query prompt string.
        chunks: Retrieved chunks used to build the prompt. Used for citation
            verification against source_document metadata.
        mode: Response mode ("full", "compact", "ultra").

    Returns:
        Dict with keys:
        - response: The post-processed response text.
        - mode: The response mode used.
        - model: The model name used.
        - verification: Structured citation verification dict, or skipped marker
            for ultra mode.
    """
    tokens = list(generate_stream(prompt, mode=mode))
    response_text = "".join(tokens)

    # Apply structural post-processing (bold warnings, numbered steps, ultra truncation)
    response_text = _post_process(response_text, mode=mode)

    # Citation verification
    if mode == "ultra":
        # Ultra mode strips citations entirely, so verification is skipped
        verification = {
            "passed": True,
            "skipped": True,
            "reason": "ultra mode strips citations",
        }
    else:
        verification = verify_citations(response_text, chunks)

        # On verification failure: keep response, append visible warning
        if not verification["passed"]:
            response_text += (
                "\n\nNote: Some citations could not be verified "
                "against source documents."
            )

    logger.info(
        "Generated response: mode=%s, length=%d chars, verification=%s",
        mode,
        len(response_text),
        "skipped" if verification.get("skipped") else verification["passed"],
    )

    return {
        "response": response_text,
        "mode": mode,
        "model": _model,
        "verification": verification,
    }


# ---------------------------------------------------------------------------
# Full pipeline integration entry points
# ---------------------------------------------------------------------------

def answer(
    query_text: str,
    categories: list[str] = None,
    mode: str = "full",
) -> dict:
    """Full pipeline: query -> retrieve -> prompt -> generate -> verify.

    Main entry point for Phase 7 CLI and web UI. Wires all pipeline stages
    together in a single call. Handles the refusal path (no relevant chunks)
    WITHOUT calling the LLM -- the canned refusal message is returned directly.

    Args:
        query_text: The user's natural language query.
        categories: Optional list of categories to filter retrieval (OR logic).
        mode: Response mode ("full", "compact", "ultra").

    Returns:
        Dict with keys:
        - response: The response text (or refusal message).
        - mode: The response mode used.
        - model: The model name used.
        - status: "ok" or "refused".
        - verification: Citation verification dict (None if refused).
        - warnings: List of safety warning dicts from retrieved chunks.
    """
    # Function-level import to avoid circular dependency
    from pipeline.prompt import query as pipeline_query

    result = pipeline_query(query_text, categories=categories)

    # Refusal path: short-circuit WITHOUT calling the LLM
    if result["status"] == "refused":
        return {
            "response": result["message"],
            "mode": mode,
            "model": _model,
            "status": "refused",
            "verification": None,
        }

    # Success path: generate response with verification
    gen_result = generate(
        prompt=result["prompt"],
        chunks=result["chunks"],
        mode=mode,
    )
    gen_result["status"] = "ok"
    gen_result["warnings"] = result["warnings"]

    return gen_result


def answer_stream(
    query_text: str,
    categories: list[str] = None,
    mode: str = "full",
) -> tuple[str, Iterator[str]]:
    """Streaming variant: returns (status, token_generator).

    For CLI: ``for token in gen: print(token, end='', flush=True)``
    For web UI: wrap the generator in SSE.

    The refusal path yields the refusal message as a single token (no LLM call).
    For the ok path, the caller is responsible for collecting full text and
    running verify_citations() post-collection if verification is needed.

    Args:
        query_text: The user's natural language query.
        categories: Optional list of categories to filter retrieval (OR logic).
        mode: Response mode ("full", "compact", "ultra").

    Returns:
        Tuple of (status, generator) where:
        - status: "ok" or "refused"
        - generator: Iterator yielding response tokens (or single refusal message)
    """
    # Function-level import to avoid circular dependency
    from pipeline.prompt import query as pipeline_query

    result = pipeline_query(query_text, categories=categories)

    # Refusal path: yield canned message as single token, no LLM call
    if result["status"] == "refused":
        return ("refused", iter([result["message"]]))

    # Success path: stream tokens from LLM
    return ("ok", generate_stream(result["prompt"], mode=mode))
