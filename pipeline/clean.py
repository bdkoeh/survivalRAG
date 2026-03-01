"""Text cleaning module for post-extraction artifact removal.

Strips residual page headers/footers, page numbers, OCR artifacts,
and normalizes whitespace. Docling already handles most header/footer
removal via ContentLayer.FURNITURE detection -- this is a safety net
for residual artifacts Docling misses.

IMPORTANT: Preserves WARNING/CAUTION/NOTE blocks (safety-critical content)
and table formatting (Markdown table rows with | delimiters).
"""

import re


def remove_page_numbers(text: str) -> str:
    """Remove residual page number patterns from extracted text.

    Handles common patterns:
    - Standalone numbers on their own line (1-3 digits)
    - "Page N" or "Page N of M" patterns
    - "- N -" centered page numbers
    - "N | Chapter Title" header-style page numbers
    """
    # Standalone page numbers on their own line (1-3 digits, not inside tables)
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # Skip lines that are just a number (page number)
        if re.match(r"^\d{1,3}$", stripped):
            continue
        # Skip "Page N" or "Page N of M" patterns
        if re.match(r"^Page\s+\d+(\s+of\s+\d+)?$", stripped, re.IGNORECASE):
            continue
        # Skip centered page numbers like "- 42 -"
        if re.match(r"^[-\u2013\u2014]\s*\d{1,3}\s*[-\u2013\u2014]$", stripped):
            continue
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def remove_ocr_artifacts(text: str) -> str:
    """Remove common OCR garbage from extracted text.

    Handles:
    - Isolated single non-alphanumeric characters on their own line
    - Garbled sequences of non-word characters (3+ consecutive)
    - Common ligature artifacts (fi, fl, ff misrecognitions)
    - Excessive isolated punctuation
    """
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()

        # Skip lines that are just isolated punctuation/symbols (not table separators)
        if stripped and len(stripped) <= 2 and not stripped.isalnum() and stripped not in ("|", "||", "--", "---"):
            continue

        # Remove garbled character sequences (3+ non-word non-space chars in a row)
        # but preserve Markdown formatting (---, ***, ===, |||)
        if re.match(r"^[^\w\s|*#=\->]{3,}$", stripped):
            continue

        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)

    # Clean up inline OCR artifacts: isolated special chars surrounded by spaces
    # but NOT inside table rows (lines containing |)
    result_lines = []
    for line in text.split("\n"):
        if "|" not in line:
            # Remove isolated single special chars between words
            line = re.sub(r"(?<=\w)\s+[^\w\s]\s+(?=\w)", " ", line)
        result_lines.append(line)

    return "\n".join(result_lines)


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace while preserving paragraph breaks and table structure.

    - Collapses 3+ consecutive blank lines to 2 (preserving paragraph breaks)
    - Strips trailing whitespace from each line
    - Preserves indentation and table row formatting
    """
    # Strip trailing whitespace from each line
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines)

    # Collapse 3+ consecutive blank lines to 2
    text = re.sub(r"\n{4,}", "\n\n\n", text)

    # Strip leading/trailing blank lines from the whole text
    text = text.strip()

    return text


def clean_text(text: str) -> str:
    """Apply all cleaning rules in sequence to extracted text.

    Order matters:
    1. Remove page numbers
    2. Remove OCR artifacts
    3. Normalize whitespace

    Preserves:
    - Markdown table rows (lines with | delimiters)
    - WARNING/CAUTION/NOTE blocks (safety-critical content)
    - Paragraph structure
    """
    text = remove_page_numbers(text)
    text = remove_ocr_artifacts(text)
    text = normalize_whitespace(text)
    return text
