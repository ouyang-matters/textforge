"""Tests for citation preservation through protected spans."""

from textforge.rewrite.protected_spans import extract_protected_spans, restore_protected_spans


class TestCitationPreservation:
    def test_numeric_citation(self):
        text = "As shown in [12], the result holds."
        processed, spans = extract_protected_spans(text)
        assert "<TF_PROTECTED_" in processed
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_multi_numeric_citation(self):
        text = "References [1,2,3] support this."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_author_year_bracket(self):
        text = "According to [Smith, 2024], the method is valid."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_author_year_paren(self):
        text = "Results (Jones et al., 2023) confirm the hypothesis."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_multiple_citation_styles(self):
        text = (
            "As [Smith, 2024] noted and [3] confirmed, "
            "the findings (Jones et al., 2023) are significant."
        )
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_citation_with_suffix(self):
        text = "In [Brown, 2024a], the authors describe the approach."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text
