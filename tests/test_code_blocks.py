"""Tests for code block preservation."""

from textforge.rewrite.protected_spans import extract_protected_spans, restore_protected_spans


class TestCodeBlockPreservation:
    def test_fenced_code_block(self):
        text = "Example:\n```python\ndef hello():\n    print('world')\n```\nEnd."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_inline_code(self):
        text = "Use `len(array)` to get the length."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_multiple_code_blocks(self):
        text = (
            "First block:\n```\ncode1\n```\n\n"
            "Second block:\n```javascript\nconst x = 1;\n```\n\nDone."
        )
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_inline_code_multiple(self):
        text = "Compare `foo()` with `bar()` and `baz()`."
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text

    def test_code_block_with_numbers(self):
        text = "```python\nx = 42\ny = 3.14\n```"
        processed, spans = extract_protected_spans(text)
        restored = restore_protected_spans(processed, spans)
        assert restored == text
        # The whole code block should be one span
        code_spans = [s for s in spans if s.kind.value == "code_block"]
        assert len(code_spans) == 1
