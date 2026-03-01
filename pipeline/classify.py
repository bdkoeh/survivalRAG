"""LLM-based content classification via Ollama structured output.

Classifies document sections by content type (procedure, reference_table,
safety_warning, general), assigns 1-3 content categories from the 9-category
taxonomy, and detects military warning levels (WARNING, CAUTION, NOTE).

Requires Ollama running at localhost:11434 with a loaded model (default:
llama3.1:8b). Uses structured output (JSON schema via Pydantic) for
deterministic, parseable classification results.
"""

import logging
import time

import ollama

from pipeline.models import SectionClassification

logger = logging.getLogger(__name__)


CLASSIFICATION_PROMPT = """You are classifying sections of US military survival manuals and government emergency preparedness documents.

Classify this section into:
- primary_type: The main content type (procedure, reference_table, safety_warning, general)
  - procedure: Step-by-step instructions, how-to guides, action sequences
  - reference_table: Data tables, lookup charts, comparison matrices
  - safety_warning: Standalone warnings, cautions, or safety notices
  - general: Introductions, background, narrative, definitions, non-actionable content

- secondary_types: Any additional types present (e.g., a procedure containing a warning)

- categories: 1-3 categories from [medical, water, shelter, fire, food, navigation, signaling, tools, first_aid]
  - medical: Diseases, medications, dosages, ongoing care, preventive medicine
  - first_aid: Immediate emergency treatment (bleeding control, CPR, splinting, shock)
  - water: Water procurement, purification, storage, safety
  - shelter: Building shelters, insulation, site selection
  - fire: Fire starting, maintenance, signaling fires
  - food: Food procurement, preservation, edible plants, hunting
  - navigation: Map reading, compass use, celestial navigation, terrain association
  - signaling: Rescue signals, mirror, smoke, ground-to-air
  - tools: Improvised tools, knives, cordage, containers

- warning_level: If a WARNING (death/injury risk), CAUTION (equipment damage), or NOTE is present
- warning_text: The exact warning text if present

Respond in the specified JSON format.

SECTION TEXT:
{section_text}"""


def check_ollama_ready(model: str = "llama3.1:8b") -> bool:
    """Verify Ollama is running and the required model is available.

    Connects to Ollama at localhost:11434 and checks if the specified
    model is loaded. Prints clear error messages with setup instructions
    if not ready.

    Args:
        model: Model name to check for (default: llama3.1:8b).

    Returns:
        True if Ollama is running and model is available, False otherwise.
    """
    try:
        models_response = ollama.list()
        available = [m.model for m in models_response.models]
        if not any(model in m for m in available):
            print(f"ERROR: Model '{model}' not found.")
            print(f"Available models: {available}")
            print(f"Run: ollama pull {model}")
            return False
        logger.info(f"Ollama ready with model {model}")
        return True
    except Exception as e:
        print(f"ERROR: Cannot connect to Ollama at localhost:11434: {e}")
        print("Make sure Ollama is running:")
        print("  1. Install Ollama: https://ollama.com/download")
        print("  2. Start Ollama: ollama serve")
        print(f"  3. Pull model: ollama pull {model}")
        return False


def classify_section(
    section_text: str, model: str = "llama3.1:8b"
) -> SectionClassification:
    """Classify a single section using Ollama structured output.

    Sends the section text to Ollama with a classification prompt and
    the SectionClassification Pydantic schema as the output format.
    Uses temperature=0 for deterministic results.

    Input is truncated to 4000 characters to avoid variable tokenization
    effects and ensure consistent classification.

    Args:
        section_text: Markdown text of the section to classify.
        model: Ollama model to use (default: llama3.1:8b).

    Returns:
        SectionClassification with content type, categories, and warnings.
    """
    response = ollama.chat(
        model=model,
        messages=[
            {
                "role": "user",
                "content": CLASSIFICATION_PROMPT.format(
                    section_text=section_text[:4000]
                ),
            }
        ],
        format=SectionClassification.model_json_schema(),
        options={"temperature": 0, "num_ctx": 4096},
    )
    return SectionClassification.model_validate_json(response.message.content)


def classify_section_with_retry(
    section_text: str,
    model: str = "llama3.1:8b",
    max_retries: int = 3,
) -> SectionClassification:
    """Classify a section with retry logic for transient Ollama errors.

    Wraps classify_section() with retries for connection issues and
    malformed JSON responses. Uses exponential backoff between retries.

    Args:
        section_text: Markdown text of the section to classify.
        model: Ollama model to use (default: llama3.1:8b).
        max_retries: Maximum number of retry attempts (default: 3).

    Returns:
        SectionClassification with content type, categories, and warnings.

    Raises:
        RuntimeError: If all retry attempts fail.
    """
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            return classify_section(section_text, model)
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                wait = 2 ** attempt  # exponential backoff: 2s, 4s, 8s
                logger.warning(
                    f"Classification attempt {attempt}/{max_retries} failed: {e}. "
                    f"Retrying in {wait}s..."
                )
                time.sleep(wait)
            else:
                logger.error(
                    f"Classification failed after {max_retries} attempts: {e}"
                )

    raise RuntimeError(
        f"Classification failed after {max_retries} attempts. "
        f"Last error: {last_error}"
    )
