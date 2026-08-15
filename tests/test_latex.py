"""Tests for LaTeX preservation through protected spans."""

from textforge.rewrite.protected_spans import extract_protected_spans, restore_protected_spans


class TestLatexPreservation:
    def test_display_latex_dollars(self):
        text = "The equation is:\n$$E = mc^2$$\nwhich is fundamental."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_display_latex_brackets(self):
        text = r"We have \[f(x) = \int_0^1 g(t) dt\] as the solution."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_inline_latex_dollars(self):
        text = "Given $x = 5$ and $y = 3$, compute $x + y$."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_inline_latex_parens(self):
        text = r"The term \(a^2 + b^2\) equals \(c^2\)."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_complex_latex(self):
        text = (
            "Consider $$\\sum_{i=1}^{n} x_i = S$$ and "
            "the integral $\\int_0^\\infty e^{-x} dx$."
        )
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_equation_labels(self):
        text = r"See \ref{eq:main} and compare with \eqref{eq:aux}."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_mixed_latex_and_code(self):
        text = (
            "The formula $x^2 + y^2$ can be computed with `x**2 + y**2`.\n\n"
            "```python\nresult = x**2 + y**2\n```\n\n"
            "$$\\frac{a}{b} = c$$"
        )
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text
