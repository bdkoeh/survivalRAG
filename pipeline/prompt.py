"""Prompt assembly module for the SurvivalRAG retrieval pipeline.

Transforms retrieved chunks into structured prompts for LLM response generation.
Safety warnings are always injected first (safety-first principle), followed by
reference context blocks with source metadata for citation, and a refusal path
that short-circuits the LLM call when no chunks pass the relevance threshold.

This module is the contract between retrieval (Phase 4) and response generation
(Phase 5). It receives data from pipeline.retrieve and produces structured
result dicts consumed by the response layer.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Hard canned refusal message -- not LLM-generated
REFUSAL_MESSAGE = (
    "I don't have enough information in my knowledge base to answer that "
    "question reliably. Try rephrasing your query or broadening the "
    "category filter."
)

# System instruction for the LLM
SYSTEM_PROMPT = (
    "You are a survival and emergency preparedness reference tool. You provide "
    "information from official US government field manuals, medical handbooks, "
    "and emergency guides.\n"
    "\n"
    "RULES:\n"
    "- Answer ONLY using the reference context provided below. Do not use your "
    "own knowledge.\n"
    "- If the provided context does not contain enough information to answer, "
    "say so clearly.\n"
    "- Cite your sources by document name and page number.\n"
    "- Preserve and surface all safety warnings -- never omit or downplay them.\n"
    "- Format responses as concise, actionable steps: numbered steps for "
    "procedures, bullets for lists, bold for warnings.\n"
    "- You are a reference tool, NOT a medical provider. Never diagnose conditions."
)


def collect_safety_warnings(retrieved_chunks: list[dict]) -> list[dict]:
    """Collect and deduplicate safety warnings from retrieved chunk metadata.

    Scans all retrieved chunks for warning_text in their metadata. Deduplicates
    by warning_text content (first occurrence wins) to avoid repetitive warnings
    in the assembled prompt.

    Args:
        retrieved_chunks: List of retrieved chunk dicts from retrieve().

    Returns:
        List of unique warning dicts with keys: source_document, section_header,
        warning_level, warning_text, page_number.
    """
    seen_texts: set[str] = set()
    warnings: list[dict] = []

    for chunk in retrieved_chunks:
        metadata = chunk.get("metadata", {})
        warning_text = metadata.get("warning_text")

        # Skip chunks without warnings (None or empty string)
        if not warning_text:
            continue

        # Deduplicate by warning_text content
        if warning_text in seen_texts:
            continue

        seen_texts.add(warning_text)
        warnings.append({
            "source_document": metadata.get("source_document", "Unknown"),
            "section_header": metadata.get("section_header", "Unknown"),
            "warning_level": metadata.get("warning_level", "warning"),
            "warning_text": warning_text,
            "page_number": metadata.get("page_number", 0),
        })

    return warnings


def assemble_prompt(query: str, retrieved_chunks: list[dict]) -> str:
    """Assemble a structured prompt from retrieved chunks for LLM consumption.

    Builds the prompt in safety-first order:
    1. System prompt (LLM instructions)
    2. Safety warnings (if any) -- always BEFORE reference context
    3. Reference context blocks with source metadata
    4. User query

    Chunks arrive pre-sorted by RRF score (highest first) from retrieve()
    and are NOT re-sorted -- preserving primacy bias for small LLMs.

    Args:
        query: The user's original query string.
        retrieved_chunks: List of retrieved chunk dicts, pre-sorted by relevance.

    Returns:
        Assembled prompt string with plain text markers (=== and ---).
    """
    parts: list[str] = []

    # 1. System prompt
    parts.append(SYSTEM_PROMPT)
    parts.append("")  # blank line separator

    # 2. Safety warnings section (if any)
    warnings = collect_safety_warnings(retrieved_chunks)
    if warnings:
        parts.append("=== SAFETY WARNINGS (MUST be included in response) ===")
        for warning in warnings:
            page = warning.get("page_number", 0)
            parts.append(
                f"WARNING [{warning['source_document']}, p.{page}]: "
                f"{warning['warning_text']}"
            )
        parts.append("")  # blank line after warnings section

    # 3. Reference context section
    parts.append("=== REFERENCE CONTEXT ===")
    for i, chunk in enumerate(retrieved_chunks, start=1):
        metadata = chunk.get("metadata", {})
        source_doc = metadata.get("source_document", "Unknown")
        section = metadata.get("section_header", "Unknown")
        page = metadata.get("page_number", 0)

        parts.append(
            f"--- Source {i}: {source_doc}, Section: {section}, Page: {page} ---"
        )
        parts.append(chunk.get("text", ""))
        parts.append("")  # blank line between source blocks

    # 4. User query section
    parts.append("=== QUESTION ===")
    parts.append(query)

    prompt = "\n".join(parts)

    logger.info(
        "Prompt assembled: %d chunks, %d warnings, %d chars",
        len(retrieved_chunks),
        len(warnings),
        len(prompt),
    )

    return prompt


def build_response(query: str, retrieved_chunks: list[dict]) -> dict:
    """Build a structured response dict for Phase 5 consumption.

    Main entry point that handles both the refusal path (empty chunks) and
    the success path (prompt assembly). Returns a structured dict that serves
    as the contract with the response generation layer.

    Args:
        query: The user's original query string.
        retrieved_chunks: List of retrieved chunk dicts from retrieve().
            Empty list triggers refusal.

    Returns:
        Dict with keys:
        - status: "ok" or "refused"
        - message: refusal text (only if refused), None otherwise
        - prompt: assembled prompt string (only if ok), None otherwise
        - chunks: the retrieved chunks (for post-generation citation verification)
        - warnings: collected safety warnings (for response verification)
    """
    # Refusal path: no chunks passed threshold
    if not retrieved_chunks:
        logger.info("Query refused (no chunks passed threshold): '%s'", query)
        return {
            "status": "refused",
            "message": REFUSAL_MESSAGE,
            "prompt": None,
            "chunks": [],
            "warnings": [],
        }

    # Success path: assemble prompt
    warnings = collect_safety_warnings(retrieved_chunks)
    prompt = assemble_prompt(query, retrieved_chunks)

    return {
        "status": "ok",
        "message": None,
        "prompt": prompt,
        "chunks": retrieved_chunks,
        "warnings": warnings,
    }


def query(query_text: str, categories: Optional[list[str]] = None) -> dict:
    """Single entry point for the entire retrieval pipeline: query in, result out.

    Wires retrieve() and build_response() together. Phase 5 (Response Generation)
    calls this function and checks result["status"]:
    - "ok" + result["prompt"] -> send prompt to LLM
    - "refused" + result["message"] -> return message directly to user

    Args:
        query_text: The user's query string.
        categories: Optional list of categories to filter by (OR logic).

    Returns:
        Structured result dict from build_response().

    Raises:
        RuntimeError: If the retrieval engine is not initialized.
    """
    from pipeline.retrieve import retrieve as _retrieve

    try:
        retrieved_chunks = _retrieve(query_text, categories=categories)
    except RuntimeError as e:
        # Handle uninitialized retrieval engine gracefully
        logger.error("Retrieval engine not initialized: %s", e)
        return {
            "status": "refused",
            "message": (
                "The retrieval engine is not initialized. "
                "Please run init() before querying."
            ),
            "prompt": None,
            "chunks": [],
            "warnings": [],
        }

    result = build_response(query_text, retrieved_chunks)
    logger.info("Pipeline query: '%s' -> %s", query_text, result["status"])
    return result
