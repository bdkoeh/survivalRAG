"""Query spell correction with domain-aware dictionary.

Builds a custom dictionary from the actual corpus (processed/sections/**/*.md)
so domain-specific terms like tourniquet, hemostasis, CBRN, botulinum are never
"corrected" away.  Uses pyspellchecker (Levenshtein distance=2) for unknowns.

Usage:
    from pipeline.spellcheck import correct_query
    fixed = correct_query("diareah emergancy nukuler")
"""

import logging
import re
from pathlib import Path

from spellchecker import SpellChecker

logger = logging.getLogger(__name__)

SECTIONS_DIR = Path("processed/sections")
DICTIONARY_PATH = Path("processed/spellcheck/dictionary.txt")

# Module-level cache
_spell_checker: SpellChecker | None = None

# Common medical/survival misspellings that exceed edit distance 2.
# Checked before the general spellchecker so phonetic manglings still resolve.
_PHONETIC_CORRECTIONS: dict[str, str] = {
    "diareah": "diarrhea",
    "diareeah": "diarrhea",
    "diahrea": "diarrhea",
    "diarreah": "diarrhea",
    "diahrrea": "diarrhea",
    "nukuler": "nuclear",
    "nucular": "nuclear",
    "tournaquit": "tourniquet",
    "tournaquette": "tourniquet",
    "tourneket": "tourniquet",
    "hemmorrhage": "hemorrhage",
    "hemmorage": "hemorrhage",
    "hemorrage": "hemorrhage",
    "hypothermea": "hypothermia",
    "hyperthermea": "hyperthermia",
    "resusitation": "resuscitation",
    "resusatation": "resuscitation",
    "anaphylaxis": "anaphylaxis",
    "anaphilaxis": "anaphylaxis",
    "anaphilactic": "anaphylactic",
    "asfiksia": "asphyxia",
    "asfixia": "asphyxia",
    "innoculate": "inoculate",
    "innoculation": "inoculation",
    "diptheria": "diphtheria",
    "pnuemonia": "pneumonia",
    "pnemonia": "pneumonia",
}


def build_domain_dictionary() -> set[str]:
    """Scan all processed/sections/**/*.md files and extract unique words.

    Saves the word list to processed/spellcheck/dictionary.txt so it can be
    reloaded without re-scanning the corpus.

    Returns:
        Set of lowercase domain words found in the corpus.
    """
    words: set[str] = set()

    md_files = list(SECTIONS_DIR.glob("**/*.md"))
    if not md_files:
        logger.warning("No section files found in %s", SECTIONS_DIR)
        return words

    for filepath in md_files:
        try:
            text = filepath.read_text(encoding="utf-8")
            tokens = re.findall(r"[a-zA-Z]+", text)
            words.update(t.lower() for t in tokens)
        except Exception as e:
            logger.debug("Skipping %s: %s", filepath, e)

    logger.info(
        "Built domain dictionary: %d unique words from %d files",
        len(words),
        len(md_files),
    )

    # Persist to disk
    DICTIONARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    DICTIONARY_PATH.write_text(
        "\n".join(sorted(words)), encoding="utf-8"
    )
    logger.info("Saved domain dictionary to %s", DICTIONARY_PATH)

    return words


def _get_spell_checker() -> SpellChecker:
    """Return a lazily-initialized SpellChecker loaded with the domain dictionary.

    On first call, loads (or builds) the domain dictionary and adds all words
    to the checker.  Subsequent calls return the cached instance.
    """
    global _spell_checker
    if _spell_checker is not None:
        return _spell_checker

    spell = SpellChecker(language="en", distance=2)

    # Load domain dictionary (from disk if available, otherwise build)
    if DICTIONARY_PATH.exists():
        domain_words = set(
            DICTIONARY_PATH.read_text(encoding="utf-8").split()
        )
        logger.info(
            "Loaded domain dictionary from %s (%d words)",
            DICTIONARY_PATH,
            len(domain_words),
        )
    else:
        domain_words = build_domain_dictionary()

    if domain_words:
        spell.word_frequency.load_words(list(domain_words))

    _spell_checker = spell
    return spell


def correct_query(text: str) -> str:
    """Spell-correct a search query while preserving domain terms and acronyms.

    Rules:
      - Words < 3 characters are passed through unchanged.
      - All-caps tokens of 2-6 characters (acronyms like CBRN, CPR) are kept.
      - Known words (English + domain dictionary) are kept.
      - Unknown words are replaced with the best correction candidate.
      - Original casing is preserved (first-char upper if original was upper).

    Args:
        text: Raw query string.

    Returns:
        Corrected query string.
    """
    spell = _get_spell_checker()
    tokens = text.split()
    corrected: list[str] = []

    for token in tokens:
        # Strip surrounding punctuation for checking, reattach after
        stripped = token.strip(".,;:!?\"'()-")
        prefix = token[: len(token) - len(token.lstrip(".,;:!?\"'()-"))]
        suffix = token[len(prefix) + len(stripped) :]

        # Skip short words
        if len(stripped) < 3:
            corrected.append(token)
            continue

        # Skip all-caps acronyms (2-6 chars)
        if stripped.isupper() and 2 <= len(stripped) <= 6:
            corrected.append(token)
            continue

        lower = stripped.lower()

        # Check phonetic corrections map first (handles high-distance medical typos)
        if lower in _PHONETIC_CORRECTIONS:
            candidate = _PHONETIC_CORRECTIONS[lower]
            if stripped[0].isupper():
                candidate = candidate[0].upper() + candidate[1:]
            corrected.append(prefix + candidate + suffix)
            logger.debug("Phonetic correction '%s' -> '%s'", stripped, candidate)
            continue

        # Check if word is known
        if lower in spell:
            corrected.append(token)
            continue

        # Attempt correction
        candidate = spell.correction(lower)
        if candidate and candidate != lower:
            # Preserve original casing style
            if stripped[0].isupper():
                candidate = candidate[0].upper() + candidate[1:]
            corrected.append(prefix + candidate + suffix)
            logger.debug("Corrected '%s' -> '%s'", stripped, candidate)
        else:
            # No better candidate found; keep original
            corrected.append(token)

    return " ".join(corrected)
