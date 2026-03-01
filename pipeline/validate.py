"""Dosage and measurement regex validation for medical content.

Auto-detects and flags potential OCR errors in dosages, measurements,
and safety-critical numbers. Flags are categorized by severity:
- "critical": High-confidence OCR corruption that likely changes meaning
- "review": Unusual values that should be spot-checked by a human

Used as a post-extraction validation step on all section content,
with results fed into verification reports.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DosageFlag:
    """A flagged dosage or measurement that may contain errors.

    Attributes:
        text: The full matched text string.
        value: The numeric value portion (may be empty for corruption patterns).
        unit: The unit portion (may be empty for corruption patterns).
        line_number: Line number in the source text (1-indexed).
        reason: Human-readable explanation of why this was flagged.
        severity: "critical" (likely corrupted) or "review" (needs spot-check).
    """

    text: str
    value: str
    unit: str
    line_number: int
    reason: str
    severity: str  # "critical" or "review"


# Pattern matches numbers followed by medical/measurement units
DOSAGE_PATTERN = re.compile(
    r"(\d+\.?\d*)\s*"
    r"(mg|mL|ml|cc|g|gr|grain|grains|mcg|"
    r"units?|tabs?|caps?|IU|oz|drops?|tsp|tbsp|L|dL|"
    r"percent|%|ppm|mmHg|bpm)\b",
    re.IGNORECASE,
)

# Patterns that suggest OCR corruption near numbers
OCR_CORRUPTION_PATTERNS = [
    # Ambiguous 1/I/l/| sequences adjacent to units (e.g., "Il mg", "ll mg")
    re.compile(r"[Il1|]{2,}\s*(mg|mL|ml|cc|g|mcg|units?|IU)", re.IGNORECASE),
    # Letter-digit confusion adjacent to units (e.g., "I0 mL" = OCR for "10 mL")
    re.compile(r"[IlO]\d\s*(mg|mL|ml|cc|g|mcg|units?|IU)", re.IGNORECASE),
    # Digit-letter confusion adjacent to units (e.g., "1O mL" = OCR for "10 mL")
    re.compile(r"\d[IlO]\s*(mg|mL|ml|cc|g|mcg|units?|IU)", re.IGNORECASE),
    # 'mg' misread as 'rng' (m -> rn OCR error)
    re.compile(r"\d+\s*rng\b", re.IGNORECASE),
    # 'mg' misread as 'ng' (m dropped)
    re.compile(r"\d+\s*ng\b(?!\s*(/|per|tube))", re.IGNORECASE),
    # Ambiguous 0/O sequences adjacent to units
    re.compile(r"[0O]{2,}\s*(mg|mL|ml|cc|g|mcg|units?)", re.IGNORECASE),
    # Implausible decimal precision (4+ decimal places before unit)
    re.compile(r"\d+\.\d{4,}\s*(mg|mL|ml|cc|g|mcg|units?|IU)", re.IGNORECASE),
    # Implausibly large values (5+ digits before mg/mL)
    re.compile(r"(?<!\d)\d{5,}\s*(mg|mL|ml|cc|g|mcg)", re.IGNORECASE),
]


def validate_dosages(text: str) -> list[DosageFlag]:
    """Find and flag potential dosage issues in extracted text.

    Scans text line-by-line for:
    1. Dosage mentions with implausible values (e.g., >10000 mg)
    2. OCR corruption patterns near numbers and units

    Args:
        text: The text content to validate (Markdown, without YAML front matter).

    Returns:
        List of DosageFlag instances for each flagged item.
    """
    flags: list[DosageFlag] = []
    seen_positions: set[tuple[int, int]] = set()  # (line, start) to avoid duplicates

    for i, line in enumerate(text.split("\n"), 1):
        # Find all dosage mentions and check for implausible values
        for match in DOSAGE_PATTERN.finditer(line):
            value, unit = match.groups()
            try:
                num = float(value)
            except ValueError:
                continue

            # Flag implausibly large dosages
            if unit.lower() in ("mg", "mcg") and num > 10000:
                pos = (i, match.start())
                if pos not in seen_positions:
                    seen_positions.add(pos)
                    flags.append(
                        DosageFlag(
                            text=match.group(),
                            value=value,
                            unit=unit,
                            line_number=i,
                            reason=f"Implausibly large dosage: {value} {unit}",
                            severity="critical",
                        )
                    )

            # Flag implausibly large volumes
            if unit.lower() in ("ml", "ml", "cc", "l") and num > 5000:
                pos = (i, match.start())
                if pos not in seen_positions:
                    seen_positions.add(pos)
                    flags.append(
                        DosageFlag(
                            text=match.group(),
                            value=value,
                            unit=unit,
                            line_number=i,
                            reason=f"Implausibly large volume: {value} {unit}",
                            severity="review",
                        )
                    )

        # Check for OCR corruption patterns
        for pattern in OCR_CORRUPTION_PATTERNS:
            for match in pattern.finditer(line):
                pos = (i, match.start())
                if pos not in seen_positions:
                    seen_positions.add(pos)
                    flags.append(
                        DosageFlag(
                            text=match.group(),
                            value="",
                            unit="",
                            line_number=i,
                            reason=f"Possible OCR corruption: '{match.group()}'",
                            severity="critical",
                        )
                    )

    return flags


def validate_section_file(file_path: Path) -> list[DosageFlag]:
    """Validate dosages in a section Markdown file.

    Reads the file, strips the YAML front matter (between --- delimiters),
    and runs validate_dosages on the remaining content.

    Args:
        file_path: Path to a section Markdown file with YAML front matter.

    Returns:
        List of DosageFlag instances for flagged items.
    """
    content = file_path.read_text(encoding="utf-8")

    # Strip YAML front matter (between first two --- lines)
    parts = content.split("---", 2)
    if len(parts) >= 3:
        # parts[0] is empty (before first ---), parts[1] is YAML, parts[2] is content
        body = parts[2]
    else:
        body = content

    return validate_dosages(body)


def generate_validation_summary(flags: list[DosageFlag]) -> str:
    """Generate a human-readable summary of dosage validation flags.

    Groups flags by severity (critical first, then review) and formats
    them for display in reports or console output.

    Args:
        flags: List of DosageFlag instances to summarize.

    Returns:
        Formatted summary string.
    """
    if not flags:
        return "No dosage flags detected."

    critical = [f for f in flags if f.severity == "critical"]
    review = [f for f in flags if f.severity == "review"]

    lines = [f"Total flags: {len(flags)} ({len(critical)} critical, {len(review)} review)"]
    lines.append("")

    if critical:
        lines.append("CRITICAL FLAGS (likely OCR corruption):")
        for f in critical:
            lines.append(f"  Line {f.line_number}: {f.reason}")
            if f.text:
                lines.append(f"    Text: '{f.text}'")
        lines.append("")

    if review:
        lines.append("REVIEW FLAGS (unusual values, needs spot-check):")
        for f in review:
            lines.append(f"  Line {f.line_number}: {f.reason}")
            if f.text:
                lines.append(f"    Text: '{f.text}'")

    return "\n".join(lines)
