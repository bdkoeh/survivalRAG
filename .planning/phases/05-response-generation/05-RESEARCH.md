# Phase 5: Response Generation - Research

**Researched:** 2026-03-01
**Domain:** LLM response generation via Ollama, streaming, citation verification, safety-first formatting
**Confidence:** HIGH

## Summary

Phase 5 transforms the retrieval pipeline output (structured result dicts from `pipeline/prompt.py`) into LLM-generated responses via Ollama. The existing codebase already uses the `ollama` Python library (>=0.6.1) for embedding; the same library provides `ollama.generate()` and `ollama.chat()` with native streaming support (`stream=True` returns `Iterator[GenerateResponse]`). The phase needs a new `pipeline/generate.py` module that: (1) validates model availability at startup, (2) calls the LLM with mode-specific system prompts, (3) streams tokens via Python generators, (4) runs post-generation citation verification using fuzzy substring matching, and (5) applies light post-processing to enforce field-manual formatting when small LLMs ignore instructions.

The architecture follows the established pattern: module-level state with `init()`, environment variable configuration (`SURVIVALRAG_MODEL`, `SURVIVALRAG_TEMPERATURE`), structured result dicts as inter-module contracts, and the same `ollama` library already in `requirements.txt`. No new dependencies are needed -- `difflib.SequenceMatcher` from stdlib handles fuzzy citation matching, and all post-processing is regex-based.

**Primary recommendation:** Use `ollama.generate()` (not `ollama.chat()`) with `stream=True` for token-by-token generation, matching the existing single-prompt pattern from `assemble_prompt()`. Lock temperature to 0.2, top_p to 0.85, and repeat_penalty to 1.1 for factual/safety-critical content. Default model: `llama3.2:3b` (2GB, 128K native context, good RAG/instruction-following performance).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Model is configurable via SURVIVALRAG_MODEL env var -- supports any Ollama-compatible model
- Temperature and generation parameters are locked to safe defaults for medical/survival content (not user-configurable) -- reduces hallucination risk
- Startup validation checks that the configured model is available in Ollama before accepting queries -- fails fast with a clear "run ollama pull <model>" message
- Python generator (yield tokens) for streaming -- CLI prints directly, web UI wraps in SSE
- Both `generate_stream()` (generator) and `generate()` (full response) methods provided
- Three response modes: full, compact, ultra (~200 chars for mesh radio)
- Each mode has its own system prompt instructing the LLM on length and style -- single LLM call per query, no post-processing summarization
- Post-generation verification (after full response complete, not during streaming)
- Fuzzy matching: citation is valid if it's a substring of or closely matches the source_document metadata field -- handles abbreviations and partial titles
- On verification failure: keep the response but append a visible warning ("Note: Some citations could not be verified against source documents.")
- Verification results (pass/fail, which citations matched) both logged AND returned as structured data in the response dict for Phase 6 evaluation framework
- System prompt instructs field-manual style + light post-processing to catch when small LLMs ignore formatting instructions
- Safety warnings rendered as bold prefix block at top of response, before answer content -- unmissable, field-manual style
- Ultra-short mode (~200 chars): strip citations (no room), keep critical safety warnings -- safety first even at minimum length

### Claude's Discretion
- Default Ollama model when no env var is set
- Exact safe temperature/parameter values
- Citation format in user-facing responses (inline parenthetical vs footnote-style)
- Light post-processor implementation approach
- Compact mode length target

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RESP-01 | Every response cites which source document and section the information came from | System prompt instructs citations; post-generation verification via fuzzy matching validates them; citation format pattern documented in Code Examples |
| RESP-02 | Safety warnings from source material are preserved and surfaced in responses | Safety warnings already collected by `collect_safety_warnings()` in prompt.py; system prompt mandates inclusion; post-processor ensures bold warning block at top of response |
| RESP-03 | When retrieved context is insufficient, the system explicitly refuses | Already implemented: `build_response()` returns `status="refused"` with canned `REFUSAL_MESSAGE` when no chunks pass threshold; generate module checks status before LLM call |
| RESP-04 | Responses formatted as concise, actionable steps (field-manual style) | Mode-specific system prompts enforce numbered steps, bullets, bold warnings; light post-processor regex catches violations |
| RESP-05 | System never provides medical diagnoses -- reference tool only | System prompt explicitly prohibits diagnosis; disclaimer appended to every response; post-processor can check for diagnostic language patterns |
| RESP-06 | Responses streamed token-by-token | `ollama.generate(stream=True)` returns `Iterator[GenerateResponse]`, wrapped in Python generator yielding `response.response` fragments |
| RESP-07 | Post-generation verification checks cited sources match retrieved chunks | `verify_citations()` function extracts citation references from response text, fuzzy-matches against chunk metadata `source_document` fields using `difflib.SequenceMatcher` |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| ollama | >=0.6.1 | LLM generation + streaming | Already in requirements.txt for embedding; `generate(stream=True)` returns `Iterator[GenerateResponse]` with `response.response` token fragments |
| difflib | stdlib | Fuzzy citation matching | `SequenceMatcher.ratio()` provides Ratcliff/Obershelp similarity; no external dependency; sufficient for substring/abbreviation matching |
| re | stdlib | Light post-processing | Regex-based formatting enforcement; standard approach for text cleanup |
| logging | stdlib | Structured logging | Matches established pattern across all pipeline modules |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| os | stdlib | Environment variable config | `SURVIVALRAG_MODEL`, generation parameter overrides (internal only) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ollama Python lib | Raw HTTP requests to /api/generate | HTTP approach used in some tutorials but ollama lib is already a dependency, handles streaming/parsing, typed responses |
| difflib.SequenceMatcher | rapidfuzz / thefuzz | External dependency for marginal speed gain; citation lists are small (<20 items), stdlib is sufficient |
| ollama.generate() | ollama.chat() | chat() uses message arrays; our prompt is pre-assembled as a single string by assemble_prompt(), so generate() is the natural fit |

**Installation:**
```bash
# No new packages needed -- ollama already in requirements.txt
pip install -r requirements.txt
```

## Architecture Patterns

### Recommended Module Structure
```
pipeline/
├── generate.py          # NEW: LLM generation, streaming, verification
├── prompt.py            # EXISTING: prompt assembly, system prompt, refusal
├── retrieve.py          # EXISTING: hybrid search + RRF
├── embed.py             # EXISTING: Ollama embedding (pattern reference)
├── _chromadb_compat.py  # EXISTING: Python 3.14 compatibility
└── __init__.py          # EXISTING: package init
```

### Pattern 1: Module-Level State with init()
**What:** Validate model availability at module init time, store config in module globals
**When to use:** Application startup, before accepting queries
**Example:**
```python
# Source: Established pattern from pipeline/retrieve.py, pipeline/embed.py

import os
import logging
import ollama

logger = logging.getLogger(__name__)

# Module-level state
_model: str = ""
_validated: bool = False

# Locked safe defaults for medical/survival content
_SAFE_OPTIONS = {
    "temperature": 0.2,
    "top_p": 0.85,
    "top_k": 20,
    "repeat_penalty": 1.1,
    "num_predict": 1024,   # max tokens for full mode
}

DEFAULT_MODEL = "llama3.2:3b"

def init(model: str = None) -> None:
    """Validate model availability and store config."""
    global _model, _validated

    _model = model or os.environ.get("SURVIVALRAG_MODEL", DEFAULT_MODEL)

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
    logger.info("Generation model validated: %s", _model)
```

### Pattern 2: Streaming Generator with Token Yield
**What:** Wrap `ollama.generate(stream=True)` in a Python generator that yields token strings
**When to use:** CLI prints directly, web UI wraps in SSE
**Example:**
```python
# Source: Ollama Python library docs (github.com/ollama/ollama-python)

def generate_stream(prompt: str, mode: str = "full") -> Iterator[str]:
    """Yield response tokens one at a time."""
    if not _validated:
        raise RuntimeError("Generation engine not initialized. Call init() first.")

    system = _get_system_prompt(mode)
    options = _get_options(mode)

    for chunk in ollama.generate(
        model=_model,
        prompt=prompt,
        system=system,
        options=options,
        stream=True,
    ):
        token = chunk.response if hasattr(chunk, 'response') else chunk.get("response", "")
        if token:
            yield token
```

### Pattern 3: Structured Response Dict Contract
**What:** Return a structured dict with response text, verification results, and metadata
**When to use:** Every generation call returns this for Phase 6 evaluation and Phase 7 UI consumption
**Example:**
```python
# Source: Established pattern from pipeline/prompt.py build_response()

def generate(prompt: str, chunks: list[dict], mode: str = "full") -> dict:
    """Generate full response and run verification."""
    # Collect all tokens
    tokens = list(generate_stream(prompt, mode=mode))
    response_text = "".join(tokens)

    # Post-process formatting
    response_text = _post_process(response_text, mode=mode)

    # Verify citations (skip for ultra mode -- no citations)
    verification = verify_citations(response_text, chunks) if mode != "ultra" else {
        "passed": True, "skipped": True, "reason": "ultra mode strips citations"
    }

    # Append warning if verification failed
    if not verification["passed"] and not verification.get("skipped"):
        response_text += (
            "\n\nNote: Some citations could not be verified "
            "against source documents."
        )

    return {
        "response": response_text,
        "mode": mode,
        "model": _model,
        "verification": verification,
    }
```

### Pattern 4: Mode-Specific System Prompts
**What:** Each response mode (full, compact, ultra) has its own system prompt variant
**When to use:** Single LLM call per query with mode-appropriate instructions
**Example:**
```python
# Source: CONTEXT.md locked decisions

# Full mode system prompt -- extends the base from prompt.py
SYSTEM_PROMPT_FULL = (
    "You are a survival and emergency preparedness reference tool. "
    "Answer ONLY using the reference context provided. "
    "Do not use your own knowledge.\n\n"
    "FORMAT RULES:\n"
    "- Cite sources as (Source: <document name>, p.<page>)\n"
    "- Number steps for procedures\n"
    "- Use bullets for lists\n"
    "- Bold all safety warnings with **WARNING:**\n"
    "- Start with any safety warnings BEFORE the answer\n"
    "- You are a reference tool, NOT a medical provider. Never diagnose."
)

SYSTEM_PROMPT_COMPACT = (
    "You are a survival reference tool. Answer ONLY from the provided context. "
    "Be brief: max 3-4 short paragraphs. Cite sources. "
    "Bold warnings. Never diagnose."
)

SYSTEM_PROMPT_ULTRA = (
    "You are a survival reference tool. Answer in under 200 characters. "
    "Use telegram style: short phrases, no articles. "
    "Include critical safety warnings. No citations (no room). "
    "Never diagnose."
)
```

### Anti-Patterns to Avoid
- **Calling LLM on refusal path:** When `build_response()` returns `status="refused"`, return the canned refusal message directly -- never send a "I don't know" prompt to the LLM (wastes tokens, risks hallucination)
- **User-configurable temperature:** Temperature, top_p, top_k, and repeat_penalty must be locked to safe defaults for medical/safety content -- user-tunable parameters risk creative/hallucinatory responses
- **Post-processing summarization for compact/ultra:** Each mode uses its own system prompt; do NOT generate a full response then summarize -- that doubles LLM calls and latency
- **Streaming citation verification:** Verification runs AFTER the full response is collected, not during streaming -- partial text cannot be reliably parsed for citations
- **Using ollama.chat() with pre-assembled prompts:** The prompt from `assemble_prompt()` is a single string with system+context+query baked in; use `ollama.generate(prompt=..., system=...)` to pass the system prompt separately and the assembled context+query as the prompt

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fuzzy string matching | Custom Levenshtein implementation | `difflib.SequenceMatcher` (stdlib) | Handles substring matching, abbreviations, partial titles; well-tested; sufficient for <20 citation comparisons |
| Ollama HTTP streaming | Raw `requests` + NDJSON parsing | `ollama.generate(stream=True)` | Library handles connection management, JSON parsing, typed responses; already a dependency |
| Model validation | Custom HTTP health check | `ollama.show(model)` / `ollama.list()` | Raises `ResponseError` with clear error when model unavailable; matches embed.py pattern |
| Token counting | Custom tokenizer | `num_predict` option in Ollama | Let Ollama handle token limits; model-specific tokenization handled internally |

**Key insight:** The `ollama` Python library already handles all the hard parts (streaming, connection management, model validation). The response generation module is primarily prompt engineering, verification logic, and formatting -- not infrastructure.

## Common Pitfalls

### Pitfall 1: Small LLMs Ignoring System Prompt Formatting
**What goes wrong:** Models like llama3.2:3b sometimes produce prose paragraphs instead of numbered steps, omit citations, or forget to bold warnings -- especially with longer context
**Why it happens:** Small models have limited instruction-following capacity; long retrieval context pushes system prompt out of effective attention window
**How to avoid:** (1) Put formatting rules in BOTH system prompt AND at the end of the user prompt (sandwich technique), (2) Apply light regex post-processing to catch violations, (3) Keep system prompts short and directive
**Warning signs:** Responses without numbered steps for procedure queries; warnings without bold markers; missing source citations

### Pitfall 2: Ollama Default Context Window Too Small
**What goes wrong:** Ollama defaults `num_ctx` to 2048 tokens, but assembled prompts with 5 chunks can easily exceed this, causing silent truncation of context
**Why it happens:** Ollama's default is conservative; llama3.2:3b supports 128K tokens natively but Ollama caps it
**How to avoid:** Set `num_ctx: 8192` (or higher) in options dict; matches the 4K-8K context window target from Phase 4 decisions (SURVIVALRAG_MAX_CHUNKS=5)
**Warning signs:** Responses that only reference the first 1-2 chunks; truncated or incomplete answers; model appears to "forget" parts of the context

### Pitfall 3: Citation Extraction Regex Too Brittle
**What goes wrong:** LLMs produce citations in inconsistent formats: "(Source: FM 21-76, p.45)", "[FM 21-76 p45]", "(FM 21-76)", "according to FM 21-76" -- a rigid regex misses most of them
**Why it happens:** Small LLMs don't strictly follow citation format instructions
**How to avoid:** Use multiple regex patterns to extract citation candidates; normalize both candidates and source metadata (lowercase, strip whitespace) before fuzzy matching; accept partial matches above 0.6 similarity threshold
**Warning signs:** High false-negative rate in citation verification (citations exist but not detected)

### Pitfall 4: Streaming + Verification Race Condition
**What goes wrong:** Trying to verify citations during streaming, or returning the response before verification completes
**Why it happens:** Desire to show verification results alongside streamed response
**How to avoid:** Architecture is clear: streaming yields tokens -> caller collects full text -> `verify_citations()` runs on complete text -> verification result returned in response dict. For `generate_stream()`, caller is responsible for post-collection verification
**Warning signs:** Incomplete or incorrect verification results

### Pitfall 5: Ultra Mode Exceeding Character Limit
**What goes wrong:** LLM generates responses well over 200 chars despite instruction
**Why it happens:** Character-level length control is unreliable with token-based generation; LLMs think in tokens, not characters
**How to avoid:** Set aggressive `num_predict` for ultra mode (e.g., 80 tokens ~ 200 chars); post-process to truncate at sentence boundary if over limit; accept that output may occasionally be slightly over/under 200 chars
**Warning signs:** Ultra responses consistently >300 chars

### Pitfall 6: Model Not Pulled Before First Query
**What goes wrong:** Application starts, user sends query, gets cryptic error from Ollama
**Why it happens:** `init()` not called or model not pre-pulled
**How to avoid:** `init()` calls `ollama.show()` which raises `ResponseError` if model not available; catch and format as user-friendly message: "Model 'X' is not available. Run: ollama pull X"
**Warning signs:** `ResponseError` exceptions in logs at startup

## Code Examples

### Citation Verification with Fuzzy Matching
```python
# Source: Python stdlib difflib docs, CONTEXT.md fuzzy matching decision

import re
from difflib import SequenceMatcher

def extract_citations(response_text: str) -> list[str]:
    """Extract citation references from LLM response text.

    Handles multiple formats small LLMs produce:
    - (Source: FM 21-76, p.45)
    - [FM 21-76, p45]
    - (FM 21-76)
    - per FM 21-76
    """
    patterns = [
        r'\(Source:\s*([^,\)]+)',           # (Source: <doc>, ...)
        r'\[([^\]]+?)(?:,\s*p\.?\s*\d+)?\]',  # [<doc>, p.XX]
        r'\(([A-Z][A-Z\s\-\d\.]+\d+)\)',    # (FM 21-76) style
        r'(?:per|from|in)\s+([A-Z][A-Z\s\-\d\.]+\d+)',  # per FM 21-76
    ]
    citations = []
    for pattern in patterns:
        citations.extend(re.findall(pattern, response_text))

    # Normalize: strip whitespace, deduplicate
    return list(set(c.strip() for c in citations if c.strip()))


def verify_citations(
    response_text: str,
    retrieved_chunks: list[dict],
    threshold: float = 0.6,
) -> dict:
    """Verify that citations in response match retrieved chunk sources.

    Returns structured verification result for Phase 6 evaluation.
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

    # Collect unique source documents from retrieved chunks
    source_docs = set()
    for chunk in retrieved_chunks:
        meta = chunk.get("metadata", {})
        doc = meta.get("source_document", "")
        if doc:
            source_docs.add(doc)

    details = []
    verified = 0

    for citation in citations:
        best_match = ""
        best_score = 0.0

        for source in source_docs:
            # Check substring match first (fast path)
            if citation.lower() in source.lower() or source.lower() in citation.lower():
                best_match = source
                best_score = 1.0
                break

            # Fuzzy match (slow path)
            score = SequenceMatcher(
                None, citation.lower(), source.lower()
            ).ratio()
            if score > best_score:
                best_score = score
                best_match = source

        matched = best_score >= threshold
        if matched:
            verified += 1

        details.append({
            "citation": citation,
            "matched_source": best_match if matched else None,
            "score": round(best_score, 3),
            "verified": matched,
        })

    return {
        "passed": verified == len(citations),
        "citations_found": len(citations),
        "citations_verified": verified,
        "citations_failed": len(citations) - verified,
        "details": details,
    }
```

### Light Post-Processor
```python
# Source: CONTEXT.md decision on post-processing

import re

def _post_process(text: str, mode: str = "full") -> str:
    """Light post-processing to enforce formatting when LLMs ignore instructions.

    Does NOT rewrite content -- only fixes formatting markers.
    """
    if mode == "ultra":
        # Truncate to ~200 chars at sentence boundary
        if len(text) > 220:
            # Find last sentence boundary before 200 chars
            truncated = text[:200]
            last_period = truncated.rfind(".")
            last_excl = truncated.rfind("!")
            boundary = max(last_period, last_excl)
            if boundary > 100:  # reasonable boundary found
                text = text[:boundary + 1]
            else:
                text = truncated.rstrip() + "..."
        return text

    # Ensure WARNING lines are bold-formatted
    text = re.sub(
        r'(?m)^(WARNING|CAUTION|DANGER):\s*',
        r'**\1:** ',
        text,
    )

    # Ensure numbered steps have consistent formatting
    # Fix "1)" or "1." without space
    text = re.sub(r'(?m)^(\d+)[.\)]\s*', r'\1. ', text)

    return text
```

### Complete Query-to-Response Flow
```python
# Source: Integration of prompt.py contract with generate.py

from pipeline.prompt import query as pipeline_query

def answer(
    query_text: str,
    categories: list[str] = None,
    mode: str = "full",
) -> dict:
    """Full pipeline: query -> retrieve -> prompt -> generate -> verify.

    Main entry point for Phase 7 CLI and web UI.
    """
    # Step 1: Retrieve + assemble prompt (Phase 4 contract)
    result = pipeline_query(query_text, categories=categories)

    # Step 2: Handle refusal path (no LLM call)
    if result["status"] == "refused":
        return {
            "response": result["message"],
            "mode": mode,
            "model": _model,
            "status": "refused",
            "verification": None,
        }

    # Step 3: Generate response with verification
    gen_result = generate(
        prompt=result["prompt"],
        chunks=result["chunks"],
        mode=mode,
    )
    gen_result["status"] = "ok"
    gen_result["warnings"] = result["warnings"]

    return gen_result
```

### Streaming Entry Point for UIs
```python
# Source: CONTEXT.md streaming contract decision

def answer_stream(
    query_text: str,
    categories: list[str] = None,
    mode: str = "full",
) -> tuple[str, Iterator[str]]:
    """Streaming variant: returns status + token generator.

    CLI usage: for token in gen: print(token, end="", flush=True)
    Web UI: wrap generator in SSE EventSourceResponse

    Returns:
        Tuple of (status, generator). If status is "refused",
        generator yields the refusal message as a single token.
    """
    result = pipeline_query(query_text, categories=categories)

    if result["status"] == "refused":
        def _refused():
            yield result["message"]
        return "refused", _refused()

    return "ok", generate_stream(result["prompt"], mode=mode)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Direct HTTP calls to Ollama /api/generate | `ollama` Python library with typed responses | ollama-python 0.3+ (2024) | Typed `GenerateResponse` objects, built-in streaming iterators, error handling |
| Single system prompt for all modes | Mode-specific system prompts | Current best practice (2025) | Better length/format control per output mode |
| No citation verification | Post-generation verification with fuzzy matching | Emerging pattern (2025, e.g., CiteFix) | Catches hallucinated citations; improves trust |
| Fixed context window (2K) | Configurable num_ctx matching model capacity | Ollama default vs model capability | Prevents silent context truncation |

**Deprecated/outdated:**
- `ollama.generate()` returning raw dicts: Newer versions (0.4+) return typed `GenerateResponse` objects, but dict-style access still works for backwards compat; code should handle both (as embed.py does)

## Open Questions

1. **Optimal num_predict per mode**
   - What we know: Ultra ~80 tokens, Full ~1024 tokens are reasonable starting points
   - What's unclear: Compact mode target -- somewhere between 256-512 tokens; needs empirical testing
   - Recommendation: Start with 512 for compact, tune based on Phase 6 evaluation

2. **Citation format preference (inline vs footnote)**
   - What we know: User left this to Claude's discretion; both work for small LLMs
   - What's unclear: Which format small LLMs follow more reliably
   - Recommendation: Use inline parenthetical `(Source: <doc>, p.<page>)` -- simpler for LLMs to produce consistently; footnote-style requires numbering coordination that small models struggle with

3. **Context window sizing**
   - What we know: Ollama defaults to 2048, llama3.2:3b supports 128K, assembled prompts with 5 chunks likely 2K-4K tokens
   - What's unclear: Exact token count of typical assembled prompts in this corpus
   - Recommendation: Set num_ctx to 8192 as safe default; monitor prompt sizes in logging

4. **Post-processor scope**
   - What we know: User wants "light" post-processing; regex for WARNING formatting and step numbering
   - What's unclear: How aggressively to reformat; risk of altering medical content
   - Recommendation: Keep post-processor strictly structural (bold markers, number formatting) -- NEVER modify content words, dosages, or measurements

## Sources

### Primary (HIGH confidence)
- Ollama Python library README (github.com/ollama/ollama-python) - generate/chat API, streaming, Options type, error handling
- Ollama API documentation (docs.ollama.com/api) - /api/generate endpoint, parameters, response format, streaming NDJSON
- Ollama Modelfile reference (docs.ollama.com/modelfile) - parameter defaults (temperature 0.8, top_p 0.9, num_ctx 2048, num_predict -1)
- Python difflib documentation (docs.python.org/3/library/difflib.html) - SequenceMatcher API
- Existing codebase: pipeline/embed.py, pipeline/prompt.py, pipeline/retrieve.py - established patterns

### Secondary (MEDIUM confidence)
- Ollama llama3.2:3b model page (ollama.com/library/llama3.2) - 3.21B params, Q4_K_M quantization, 2GB size
- Artificial Analysis benchmark (artificialanalysis.ai) - llama3.2:3b 128K context window, instruction-following capability
- Multiple sources on temperature settings for factual RAG: 0.2 temperature, 0.85 top_p consistently recommended across guides (markaicode.com, dasroot.net, localaiops.com)
- CiteFix paper (arxiv.org/abs/2504.15629) - post-processing citation correction approach, 15.46% accuracy improvement

### Tertiary (LOW confidence)
- Ultra-short response mode (~200 chars): No direct precedent found for character-constrained LLM output in RAG literature; technique relies on `num_predict` token limiting + post-processing truncation; needs empirical validation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - ollama library already in use, generate() API well-documented, no new dependencies
- Architecture: HIGH - follows established module patterns (init/generate/verify), contracts well-defined by existing prompt.py
- Pitfalls: HIGH - small LLM formatting issues well-documented in RAG literature; context window truncation is a known Ollama default issue
- Citation verification: MEDIUM - fuzzy matching approach is sound but citation extraction regex patterns need empirical tuning against actual LLM output
- Ultra-short mode: LOW - no precedent; relies on untested combination of token limiting + truncation

**Research date:** 2026-03-01
**Valid until:** 2026-03-31 (stable domain; ollama library API unlikely to break)
