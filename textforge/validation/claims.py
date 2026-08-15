"""Claim preservation validation."""

from __future__ import annotations

import json
import re

from textforge.models import ClaimComparisonResult
from textforge.providers.base import RewriteProvider
from textforge.rewrite.prompts import CLAIM_EXTRACTION_PROMPT


async def extract_claims(text: str, provider: RewriteProvider) -> list[str]:
    """Extract atomic factual claims from text using LLM."""
    prompt = CLAIM_EXTRACTION_PROMPT.format(text=text)
    response = await provider.structured_output(
        [{"role": "user", "content": prompt}],
        temperature=0.0,
    )
    try:
        raw = response.text.strip()
        json_match = re.search(r"\[[\s\S]*\]", raw)
        if json_match:
            claims = json.loads(json_match.group())
        else:
            claims = json.loads(raw)
        return [str(c) for c in claims]
    except (json.JSONDecodeError, ValueError):
        return []


async def compare_claims(
    source: str,
    candidate: str,
    provider: RewriteProvider,
) -> ClaimComparisonResult:
    """Extract and compare claims between source and candidate."""
    source_claims = await extract_claims(source, provider)
    candidate_claims = await extract_claims(candidate, provider)

    # Simple set-based comparison by normalized text
    source_normalized = {c.lower().strip() for c in source_claims}
    candidate_normalized = {c.lower().strip() for c in candidate_claims}

    preserved = list(source_normalized & candidate_normalized)
    missing = list(source_normalized - candidate_normalized)
    added = list(candidate_normalized - source_normalized)

    total = len(source_normalized)
    score = len(preserved) / total if total > 0 else 1.0

    return ClaimComparisonResult(
        source_claims=source_claims,
        candidate_claims=candidate_claims,
        preserved=preserved,
        missing=missing,
        added=added,
        score=score,
    )
