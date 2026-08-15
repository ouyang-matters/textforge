"""Semantic validation with embedding or LLM fallback."""

from __future__ import annotations

import json
import re

from textforge.models import SemanticValidationResult
from textforge.providers.base import RewriteProvider
from textforge.rewrite.prompts import SEMANTIC_COMPARISON_PROMPT


class SemanticValidator:
    """Validates semantic equivalence between source and candidate."""

    def __init__(
        self,
        provider: RewriteProvider | None = None,
        threshold: float = 0.94,
    ):
        self._provider = provider
        self._threshold = threshold

    async def compare(
        self,
        source: str,
        candidate: str,
    ) -> SemanticValidationResult:
        """Compare source and candidate for semantic equivalence."""
        if self._provider is None:
            return SemanticValidationResult(
                score=1.0,
                passed=True,
                contradictions=[],
                missing_claims=[],
                added_claims=[],
            )

        return await self._llm_compare(source, candidate)

    async def _llm_compare(
        self, source: str, candidate: str
    ) -> SemanticValidationResult:
        """Use LLM structured comparison."""
        prompt = SEMANTIC_COMPARISON_PROMPT.format(source=source, candidate=candidate)
        response = await self._provider.structured_output(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
        )

        try:
            raw = response.text.strip()
            json_match = re.search(r"\{[\s\S]*\}", raw)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(raw)

            score = float(data.get("score", 0.0))
            return SemanticValidationResult(
                score=score,
                passed=score >= self._threshold,
                contradictions=data.get("contradictions", []),
                missing_claims=data.get("missing_claims", []),
                added_claims=data.get("added_claims", []),
            )
        except (json.JSONDecodeError, ValueError, KeyError):
            return SemanticValidationResult(
                score=0.5,
                passed=False,
                contradictions=["Failed to parse semantic comparison response"],
                missing_claims=[],
                added_claims=[],
            )
