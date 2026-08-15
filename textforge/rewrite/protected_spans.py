"""Protected span extraction and restoration.

Extracts spans that must be preserved verbatim through rewriting (LaTeX, code,
URLs, citations, numbers, etc.) and replaces them with stable placeholders.
Restoration is deterministic and reversible.
"""

from __future__ import annotations

import re

from textforge.models import ProtectedSpan, ProtectedSpanKind

_PLACEHOLDER_TEMPLATE = "<TF_PROTECTED_{idx:04d}>"

# Order matters: longer/more specific patterns first to avoid partial matches.
_PATTERNS: list[tuple[ProtectedSpanKind, re.Pattern[str]]] = [
    # Display LaTeX: $$ ... $$ or \[ ... \]
    (ProtectedSpanKind.DISPLAY_LATEX, re.compile(r"\$\$[\s\S]*?\$\$", re.DOTALL)),
    (ProtectedSpanKind.DISPLAY_LATEX, re.compile(r"\\\[[\s\S]*?\\\]", re.DOTALL)),
    # Equation labels: \label{...} \eqref{...} \ref{...}
    (ProtectedSpanKind.EQUATION_LABEL, re.compile(r"\\(?:label|eqref|ref)\{[^}]+\}")),
    # Markdown code blocks: ```...```
    (ProtectedSpanKind.CODE_BLOCK, re.compile(r"```[\s\S]*?```", re.DOTALL)),
    # Inline code: `...`
    (ProtectedSpanKind.INLINE_CODE, re.compile(r"`[^`\n]+`")),
    # Inline LaTeX: $ ... $ (single dollar, not empty)
    (ProtectedSpanKind.INLINE_LATEX, re.compile(r"(?<!\$)\$(?!\$)(?!\s)([^\$\n]+?)(?<!\s)\$(?!\$)")),
    # Inline LaTeX: \( ... \)
    (ProtectedSpanKind.INLINE_LATEX, re.compile(r"\\\(.*?\\\)")),
    # DOIs
    (ProtectedSpanKind.DOI, re.compile(r"(?:https?://doi\.org/|doi:)10\.\d{4,}/[^\s]+")),
    # URLs
    (ProtectedSpanKind.URL, re.compile(r"https?://[^\s\])<>\"']+")),
    # Citations: [12], [Smith, 2024], (Smith et al., 2024)
    (ProtectedSpanKind.CITATION, re.compile(r"\[[A-Z][a-zA-Z]*(?:\s+et\s+al\.?)?,\s*\d{4}[a-z]?\]")),
    (ProtectedSpanKind.CITATION, re.compile(r"\([A-Z][a-zA-Z]*(?:\s+et\s+al\.?)?,\s*\d{4}[a-z]?\)")),
    (ProtectedSpanKind.CITATION, re.compile(r"\[\d+(?:,\s*\d+)*\]")),
    # Quoted text: "..." or '...'
    (ProtectedSpanKind.QUOTED_TEXT, re.compile(r'"[^"\n]{2,}"')),
    (ProtectedSpanKind.QUOTED_TEXT, re.compile(r"\u201c[^\u201d\n]{2,}\u201d")),
    # Scientific notation: 1.5e10, 3.2E-4
    (ProtectedSpanKind.SCIENTIFIC, re.compile(r"-?\d+\.?\d*[eE][+-]?\d+")),
    # Percentages: 42%, 3.14%
    (ProtectedSpanKind.PERCENTAGE, re.compile(r"-?\d+\.?\d*%")),
    # Decimals: 3.14, -0.5
    (ProtectedSpanKind.DECIMAL, re.compile(r"(?<!\w)-?\d+\.\d+(?!\w)")),
    # Integers: standalone numbers (word-boundary)
    (ProtectedSpanKind.INTEGER, re.compile(r"(?<!\w)-?\d+(?!\w|\.?\d)")),
    # Common math identifiers: single-letter subscripted vars like x_i, A_{ij}
    (ProtectedSpanKind.MATH_IDENTIFIER, re.compile(r"[a-zA-Z]_\{[^}]+\}")),
    (ProtectedSpanKind.MATH_IDENTIFIER, re.compile(r"[a-zA-Z]_[a-zA-Z0-9]")),
]


def extract_protected_spans(text: str) -> tuple[str, list[ProtectedSpan]]:
    """Extract protected spans and replace with placeholders.

    Returns the text with placeholders and the list of extracted spans.
    """
    spans: list[ProtectedSpan] = []
    # Collect all matches with their positions
    raw_matches: list[tuple[int, int, str, ProtectedSpanKind]] = []

    for kind, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            raw_matches.append((m.start(), m.end(), m.group(), kind))

    # Sort by start position, longer spans first for ties
    raw_matches.sort(key=lambda x: (x[0], -(x[1] - x[0])))

    # Remove overlapping matches (keep the first/longest)
    filtered: list[tuple[int, int, str, ProtectedSpanKind]] = []
    last_end = -1
    for start, end, original, kind in raw_matches:
        if start >= last_end:
            filtered.append((start, end, original, kind))
            last_end = end

    # Build result text by replacing spans with placeholders
    result_parts: list[str] = []
    prev_end = 0
    for idx, (start, end, original, kind) in enumerate(filtered):
        placeholder = _PLACEHOLDER_TEMPLATE.format(idx=idx + 1)
        result_parts.append(text[prev_end:start])
        result_parts.append(placeholder)
        spans.append(ProtectedSpan(
            placeholder=placeholder,
            original=original,
            start=start,
            end=end,
            kind=kind,
        ))
        prev_end = end
    result_parts.append(text[prev_end:])

    return "".join(result_parts), spans


def restore_protected_spans(text: str, spans: list[ProtectedSpan]) -> str:
    """Restore placeholders to original text. Deterministic and reversible."""
    result = text
    # Restore in reverse order of placeholder index to avoid offset issues
    for span in reversed(spans):
        result = result.replace(span.placeholder, span.original)
    return result
