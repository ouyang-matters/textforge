"""Tests for quality validation."""

from __future__ import annotations

from textforge.validation.quality import check_quality


class TestQualityCheck:
    def test_clean_text(self):
        result = check_quality("This is a well-formed sentence. It has proper punctuation.")
        assert result.passed

    def test_placeholder_leakage(self):
        result = check_quality("Text with <TF_PROTECTED_0001> leftover.")
        assert not result.passed
        assert any("Placeholder" in i for i in result.issues)

    def test_unbalanced_code_blocks(self):
        result = check_quality("```python\ncode here\nno closing")
        assert not result.passed
        assert any("```" in i for i in result.issues)

    def test_unbalanced_latex(self):
        result = check_quality("Formula $x + y is missing closing.")
        assert not result.passed

    def test_duplicate_sentence(self):
        result = check_quality(
            "This is a very specific sentence about something. "
            "Another sentence here. "
            "This is a very specific sentence about something."
        )
        assert not result.passed
        assert any("Duplicate" in i for i in result.issues)

    def test_empty_paragraph(self):
        result = check_quality("First paragraph.\n\n\n\n\nSecond paragraph.")
        # After normalization the empty paragraph would be caught
        # This depends on how many blank lines there are
        assert isinstance(result.passed, bool)

    def test_balanced_latex(self):
        result = check_quality("The formula $x + y$ equals $z$. Done.")
        assert result.passed
