"""Tests for edit metrics computation."""

from textforge.rewrite.engine import compute_edit_metrics


class TestEditMetrics:
    def test_identical_texts(self):
        m = compute_edit_metrics("Hello world.", "Hello world.")
        assert m.character_edit_ratio == 0.0
        assert m.sentence_count_delta == 0
        assert m.paragraph_count_delta == 0
        assert m.length_ratio == 1.0

    def test_different_texts(self):
        m = compute_edit_metrics("Hello world.", "Goodbye world.")
        assert m.character_edit_ratio > 0.0
        assert m.token_edit_ratio > 0.0

    def test_added_sentence(self):
        m = compute_edit_metrics("One sentence.", "One sentence. Two sentences.")
        assert m.sentence_count_delta == 1

    def test_added_paragraph(self):
        m = compute_edit_metrics("Para one.", "Para one.\n\nPara two.")
        assert m.paragraph_count_delta == 1

    def test_length_ratio(self):
        m = compute_edit_metrics("Short.", "This is a much longer text.")
        assert m.length_ratio > 1.0

    def test_shorter_output(self):
        m = compute_edit_metrics("This is a longer piece of text.", "Short.")
        assert m.length_ratio < 1.0
