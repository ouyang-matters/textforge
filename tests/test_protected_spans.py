"""Tests for protected span extraction and restoration."""

from __future__ import annotations

from textforge.rewrite.protected_spans import extract_protected_spans, restore_protected_spans


class TestProtectedSpanRoundTrip:
    """Byte-for-byte restoration tests."""

    def test_empty_text(self):
        text = ""
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_no_protected_content(self):
        text = "This is a plain sentence with no special content."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_display_latex(self):
        text = "Consider the equation $$E = mc^2$$ which is fundamental."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text
        assert any(s.kind.value == "display_latex" for s in spans)

    def test_display_latex_brackets(self):
        text = r"The formula \[x = \frac{-b}{2a}\] is important."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_inline_latex(self):
        text = "The variable $x$ is defined as $y + z$."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_inline_latex_parens(self):
        text = r"We define \(f(x) = x^2\) as the function."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_code_block(self):
        text = "Here is code:\n```python\ndef foo():\n    return 42\n```\nEnd."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text
        assert any(s.kind.value == "code_block" for s in spans)

    def test_inline_code(self):
        text = "Use the `print()` function and `len()` method."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text
        assert any(s.kind.value == "inline_code" for s in spans)

    def test_urls(self):
        text = "Visit https://example.com/path?q=1 for details."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text
        assert any(s.kind.value == "url" for s in spans)

    def test_dois(self):
        text = "See doi:10.1234/abc.def for the reference."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text
        assert any(s.kind.value == "doi" for s in spans)

    def test_citation_numeric(self):
        text = "As shown in [12], the result holds."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text
        assert any(s.kind.value == "citation" for s in spans)

    def test_citation_author_year_bracket(self):
        text = "According to [Smith, 2024], the method works."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_citation_author_year_paren(self):
        text = "As noted by (Smith et al., 2024), results improve."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_integers(self):
        text = "There are 42 items and 7 categories."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_decimals(self):
        text = "The ratio is 3.14 and the margin is 0.05."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_scientific_notation(self):
        text = "The value is 1.5e10 and the error is 3.2E-4."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_percentages(self):
        text = "Accuracy improved by 15.3% over the baseline of 92%."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_equation_labels(self):
        text = r"See Equation \ref{eq:main} and \eqref{eq:secondary}."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_quoted_text(self):
        text = 'He said "hello world" and she replied "goodbye".'
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_complex_mixed_content(self):
        text = (
            "In [Smith, 2024], the authors show that $E = mc^2$ holds for "
            "values up to 1.5e10. The code `energy = mass * c**2` computes this. "
            "See https://physics.org/paper for details. Results improved by 42%.\n\n"
            "$$\\int_0^\\infty e^{-x} dx = 1$$\n\n"
            "As noted in [3], this is 99.7% accurate."
        )
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_multiple_citations(self):
        text = "Studies [1,2,3] and [Smith, 2024] confirm this."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_math_identifiers(self):
        text = r"The variable x_i converges to x_{max} as n grows."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_placeholders_are_stable(self):
        text = "The value is 42 and the URL is https://example.com."
        processed1, spans1 = extract_protected_spans(text)
        processed2, spans2 = extract_protected_spans(text)
        assert processed1 == processed2
        assert len(spans1) == len(spans2)
        for s1, s2 in zip(spans1, spans2):
            assert s1.placeholder == s2.placeholder
            assert s1.original == s2.original

    def test_negative_numbers(self):
        text = "The temperature dropped to -15 degrees and -3.5 was recorded."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text
