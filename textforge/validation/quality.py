"""Quality validation checks."""

from __future__ import annotations

import re

from textforge.models import QualityCheckResult


def check_quality(text: str) -> QualityCheckResult:
    """Run deterministic quality checks on text."""
    issues: list[str] = []

    # Placeholder leakage
    if re.search(r"<TF_PROTECTED_\d{4}>", text):
        issues.append("Placeholder leakage detected: unreplaced <TF_PROTECTED_XXXX> found")

    # Malformed Markdown: unclosed code blocks
    code_block_count = text.count("```")
    if code_block_count % 2 != 0:
        issues.append("Malformed Markdown: odd number of ``` delimiters")

    # Unbalanced LaTeX delimiters
    if text.count("$$") % 2 != 0:
        issues.append("Unbalanced LaTeX: odd number of $$ delimiters")

    inline_dollars = len(re.findall(r"(?<!\$)\$(?!\$)", text))
    if inline_dollars % 2 != 0:
        issues.append("Unbalanced LaTeX: odd number of inline $ delimiters")

    if text.count("\\[") != text.count("\\]"):
        issues.append("Unbalanced LaTeX: \\[ and \\] count mismatch")

    if text.count("\\(") != text.count("\\)"):
        issues.append("Unbalanced LaTeX: \\( and \\) count mismatch")

    # Duplicate sentences
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    seen: set[str] = set()
    for s in sentences:
        normalized = s.lower().strip()
        if len(normalized) > 20 and normalized in seen:
            issues.append(f"Duplicate sentence detected: {s[:60]}...")
        seen.add(normalized)

    # Truncated output (ends mid-sentence without punctuation)
    stripped = text.rstrip()
    if stripped and stripped[-1] not in ".!?\"')]:}\u201d" and len(stripped) > 50:
        issues.append("Possible truncated output: text does not end with terminal punctuation")

    # Empty paragraphs
    paragraphs = re.split(r"\n\s*\n", text)
    empty_count = sum(1 for p in paragraphs if not p.strip())
    if empty_count > 0:
        issues.append(f"Empty paragraph(s) detected: {empty_count}")

    # Obvious grammar corruption: repeated words
    if re.search(r"\b(\w+)\s+\1\b", text, re.IGNORECASE):
        # Filter common legitimate repetitions
        for m in re.finditer(r"\b(\w+)\s+\1\b", text, re.IGNORECASE):
            word = m.group(1).lower()
            if word not in {"that", "had", "the", "is", "was", "very", "so", "no", "bye"}:
                issues.append(f"Possible grammar corruption: repeated word '{m.group()}'")
                break

    return QualityCheckResult(
        passed=len(issues) == 0,
        issues=issues,
    )
