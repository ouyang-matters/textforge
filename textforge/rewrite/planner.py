"""Structural planner for paragraph-level analysis."""

from __future__ import annotations

import json
import re

from textforge.models import (
    ParagraphAnalysis,
    ParagraphType,
    StructuralAnalysisResult,
)
from textforge.providers.base import RewriteProvider
from textforge.rewrite.prompts import STRUCTURAL_ANALYSIS_PROMPT


def _split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs by blank lines."""
    paragraphs = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paragraphs if p.strip()]


def _count_sentences(text: str) -> int:
    """Count sentences heuristically."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return len([s for s in sentences if s.strip()])


def _has_placeholders(text: str) -> bool:
    return bool(re.search(r"<TF_PROTECTED_\d{4}>", text))


def analyze_structure_deterministic(text: str) -> StructuralAnalysisResult:
    """Deterministic paragraph analysis without an LLM."""
    paragraphs = _split_paragraphs(text)
    analyses: list[ParagraphAnalysis] = []

    for idx, para in enumerate(paragraphs):
        para_lower = para.lower()
        sentence_count = _count_sentences(para)
        has_protected = _has_placeholders(para)

        # Classify paragraph type heuristically
        if re.match(r"```", para):
            ptype = ParagraphType.CODE_RELATED
        elif re.match(r'["\u201c]', para):
            ptype = ParagraphType.QUOTATION
        elif re.match(r"(\d+[\.\)]\s|[-*]\s)", para):
            ptype = ParagraphType.ENUMERATION
        elif any(w in para_lower for w in ["for example", "for instance", "e.g.", "such as"]):
            ptype = ParagraphType.EXAMPLE
        elif any(w in para_lower for w in ["is defined as", "refers to", "means that", "definition"]):
            ptype = ParagraphType.DEFINITION
        elif any(w in para_lower for w in ["however", "therefore", "thus", "consequently", "moreover"]):
            ptype = ParagraphType.ARGUMENT
        elif any(w in para_lower for w in ["in this section", "next", "finally", "in conclusion"]):
            ptype = ParagraphType.TRANSITION
        elif has_protected or any(w in para_lower for w in ["algorithm", "equation", "formula", "theorem"]):
            ptype = ParagraphType.TECHNICAL_EXPLANATION
        else:
            ptype = ParagraphType.OTHER

        analyses.append(ParagraphAnalysis(
            index=idx,
            text=para,
            paragraph_type=ptype,
            sentence_count=sentence_count,
            has_protected_content=has_protected,
        ))

    return StructuralAnalysisResult(
        paragraphs=analyses,
        total_paragraphs=len(analyses),
        total_sentences=sum(a.sentence_count for a in analyses),
    )


async def analyze_structure_with_llm(
    text: str, provider: RewriteProvider, model: str | None = None
) -> StructuralAnalysisResult:
    """Use LLM for structural analysis, falling back to deterministic."""
    try:
        prompt = STRUCTURAL_ANALYSIS_PROMPT.format(text=text)
        response = await provider.structured_output(
            [{"role": "user", "content": prompt}],
            model=model,
            temperature=0.0,
        )
        raw = response.text.strip()
        # Extract JSON from response
        json_match = re.search(r"\[[\s\S]*\]", raw)
        if not json_match:
            return analyze_structure_deterministic(text)

        items = json.loads(json_match.group())
        paragraphs = _split_paragraphs(text)
        analyses: list[ParagraphAnalysis] = []

        for item in items:
            idx = item.get("index", 0)
            if idx >= len(paragraphs):
                continue
            ptype_str = item.get("paragraph_type", "other")
            try:
                ptype = ParagraphType(ptype_str)
            except ValueError:
                ptype = ParagraphType.OTHER

            analyses.append(ParagraphAnalysis(
                index=idx,
                text=paragraphs[idx] if idx < len(paragraphs) else "",
                paragraph_type=ptype,
                sentence_count=item.get("sentence_count", _count_sentences(paragraphs[idx])),
                has_protected_content=item.get("has_protected_content", False),
            ))

        return StructuralAnalysisResult(
            paragraphs=analyses,
            total_paragraphs=len(analyses),
            total_sentences=sum(a.sentence_count for a in analyses),
        )
    except Exception:
        return analyze_structure_deterministic(text)
