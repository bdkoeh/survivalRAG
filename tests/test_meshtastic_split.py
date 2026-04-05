"""Unit tests for Meshtastic message splitting and text processing.

Tests the pure functions in pipeline/meshtastic_bridge.py that have no
external dependencies. These can run without the meshtastic package installed.
"""

import pytest

from pipeline.meshtastic_bridge import (
    split_for_mesh,
    strip_markdown_for_mesh,
    prepend_warnings,
)


# ---------------------------------------------------------------------------
# strip_markdown_for_mesh
# ---------------------------------------------------------------------------

class TestStripMarkdown:
    def test_removes_bold_markers(self):
        assert strip_markdown_for_mesh("**WARNING:** Do not eat") == "WARNING: Do not eat"

    def test_removes_citations(self):
        text = "Boil water for 1 min (Source: FM 21-76, p.45) to purify."
        assert strip_markdown_for_mesh(text) == "Boil water for 1 min to purify."

    def test_removes_multiple_citations(self):
        text = "Step 1 (Source: FM 21-76, p.10). Step 2 (Source: FM 7-22, p.5)."
        result = strip_markdown_for_mesh(text)
        assert "(Source:" not in result
        assert "Step 1" in result
        assert "Step 2" in result

    def test_collapses_newlines(self):
        text = "Line 1\n\n\n\nLine 2"
        assert strip_markdown_for_mesh(text) == "Line 1\n\nLine 2"

    def test_collapses_spaces(self):
        text = "Word   word    word"
        assert strip_markdown_for_mesh(text) == "Word word word"

    def test_strips_whitespace(self):
        assert strip_markdown_for_mesh("  hello  ") == "hello"

    def test_empty_string(self):
        assert strip_markdown_for_mesh("") == ""

    def test_plain_text_unchanged(self):
        text = "Boil water for 1 minute at a rolling boil."
        assert strip_markdown_for_mesh(text) == text


# ---------------------------------------------------------------------------
# prepend_warnings
# ---------------------------------------------------------------------------

class TestPrependWarnings:
    def test_no_warnings(self):
        assert prepend_warnings("Response text", []) == "Response text"

    def test_single_warning(self):
        warnings = [{
            "warning_level": "warning",
            "warning_text": "May cause burns",
            "source_document": "FM 21-76",
        }]
        result = prepend_warnings("Response text", warnings)
        assert result.startswith("WARNING: May cause burns")
        assert "Response text" in result

    def test_caution_level(self):
        warnings = [{
            "warning_level": "caution",
            "warning_text": "Use with care",
        }]
        result = prepend_warnings("Response", warnings)
        assert result.startswith("CAUTION: Use with care")

    def test_only_first_warning_used(self):
        warnings = [
            {"warning_level": "warning", "warning_text": "First warning"},
            {"warning_level": "caution", "warning_text": "Second warning"},
        ]
        result = prepend_warnings("Response", warnings)
        assert "First warning" in result
        assert "Second warning" not in result

    def test_empty_warning_text(self):
        warnings = [{"warning_level": "warning", "warning_text": ""}]
        assert prepend_warnings("Response", []) == "Response"

    def test_none_warnings(self):
        assert prepend_warnings("Response", None or []) == "Response"


# ---------------------------------------------------------------------------
# split_for_mesh
# ---------------------------------------------------------------------------

class TestSplitForMesh:
    def test_empty_string(self):
        assert split_for_mesh("") == []

    def test_short_text_no_numbering(self):
        text = "Boil water for 1 minute."
        result = split_for_mesh(text)
        assert result == [text]
        assert "[" not in result[0]  # No part numbering

    def test_exact_boundary_single_part(self):
        # Create text exactly at chunk_size bytes
        text = "a" * 194
        result = split_for_mesh(text)
        assert len(result) == 1
        assert result[0] == text

    def test_just_over_boundary_splits(self):
        # Text just over the limit should split into 2 parts
        text = "a" * 195
        result = split_for_mesh(text)
        assert len(result) == 2
        for part in result:
            assert "[" in part  # Part numbering present

    def test_sentence_boundary_preferred(self):
        # Create two sentences where the split should happen between them
        s1 = "Boil water for one minute to kill bacteria."
        s2 = " Filter through cloth to remove sediment."
        text = s1 + s2
        # Use a chunk_size that forces a split
        result = split_for_mesh(text, chunk_size=50, max_parts=5)
        assert len(result) >= 2
        # First part should end at a sentence boundary
        first_content = result[0].split(" [")[0]
        assert first_content.endswith(".")

    def test_word_boundary_fallback(self):
        # One long sentence with no period — should split at word boundary
        text = "word " * 50  # ~250 bytes
        result = split_for_mesh(text, chunk_size=100, max_parts=5)
        assert len(result) >= 2
        for part in result:
            content = part.split(" [")[0]
            # Should not split mid-word
            assert not content.endswith("wor")

    def test_max_parts_enforced(self):
        text = "word " * 200  # Very long text
        result = split_for_mesh(text, chunk_size=50, max_parts=3)
        assert len(result) <= 3

    def test_truncation_indicated(self):
        text = "word " * 200
        result = split_for_mesh(text, chunk_size=50, max_parts=3)
        last = result[-1]
        # Last part should indicate truncation
        assert "..." in last or f"[{len(result)}/{len(result)}]" in last

    def test_part_numbering_format(self):
        text = "a " * 100
        result = split_for_mesh(text, chunk_size=50, max_parts=5)
        assert len(result) >= 2
        for i, part in enumerate(result, 1):
            expected_suffix = f"[{i}/{len(result)}]"
            assert expected_suffix in part

    def test_all_parts_under_200_bytes(self):
        """Every part including [i/n] suffix must fit in 200 bytes."""
        text = "This is a test sentence with various words. " * 20
        result = split_for_mesh(text)
        for part in result:
            byte_len = len(part.encode("utf-8"))
            assert byte_len <= 200, f"Part exceeds 200 bytes ({byte_len}): {part!r}"

    def test_utf8_multibyte_characters(self):
        # Mix of ASCII and multi-byte characters
        text = "Fiebersenkende Mittel verwenden. " * 10  # German with umlaut-free but long
        result = split_for_mesh(text, chunk_size=80, max_parts=5)
        for part in result:
            byte_len = len(part.encode("utf-8"))
            assert byte_len <= 86  # 80 + 6 for suffix

    def test_utf8_accented_characters(self):
        # Accented characters are 2 bytes each in UTF-8
        text = "Bébé à côté " * 20  # French accented
        result = split_for_mesh(text)
        for part in result:
            byte_len = len(part.encode("utf-8"))
            assert byte_len <= 200

    def test_default_chunk_size(self):
        # Default should be 194
        text = "a" * 193
        result = split_for_mesh(text)
        assert len(result) == 1  # 193 < 194, fits in one

        text = "a" * 195
        result = split_for_mesh(text)
        assert len(result) == 2  # 195 > 194, needs split

    def test_realistic_compact_response(self):
        """Simulate a realistic compact mode response."""
        response = (
            "To purify water in the field, boil it at a rolling boil for at "
            "least 1 minute. At altitudes above 6,500 feet, boil for 3 minutes. "
            "If boiling is not possible, use water purification tablets. Add one "
            "tablet per quart of clear water, two tablets for cloudy water. Wait "
            "30 minutes before drinking. You can also use a few drops of household "
            "bleach - 2 drops per quart for clear water, 4 drops for cloudy. "
            "Wait 30 minutes. Water should have a slight chlorine smell. If not, "
            "repeat and wait another 15 minutes."
        )
        result = split_for_mesh(response)
        assert len(result) <= 5
        for part in result:
            assert len(part.encode("utf-8")) <= 200

    def test_single_very_long_word(self):
        # Edge case: one word longer than chunk_size
        text = "a" * 300
        result = split_for_mesh(text, chunk_size=100, max_parts=5)
        assert len(result) >= 2
        for part in result:
            # Should still not exceed budget + suffix
            byte_len = len(part.encode("utf-8"))
            assert byte_len <= 106  # 100 + 6


# ---------------------------------------------------------------------------
# Integration: strip + prepend + split together
# ---------------------------------------------------------------------------

class TestEndToEnd:
    def test_full_pipeline(self):
        """Simulate the full text processing pipeline."""
        response = (
            "**WARNING:** Burns can be life-threatening.\n\n"
            "1. Cool the burn under running water for 10 minutes "
            "(Source: FM 21-76, p.120).\n"
            "2. Do **not** apply butter or oil.\n"
            "3. Cover with a sterile bandage (Source: TC 4-02.1, p.55)."
        )
        warnings = [{
            "warning_level": "warning",
            "warning_text": "Seek immediate medical attention for burns.",
        }]

        text = prepend_warnings(response, warnings)
        text = strip_markdown_for_mesh(text)
        parts = split_for_mesh(text)

        # Should have produced valid parts
        assert len(parts) >= 1
        for part in parts:
            assert len(part.encode("utf-8")) <= 200
            assert "**" not in part
            assert "(Source:" not in part

        # Warning should be in part 1
        assert "WARNING" in parts[0]
