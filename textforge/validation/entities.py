"""Entity preservation validation."""

from __future__ import annotations

import re

from textforge.models import EntityComparisonResult


def extract_entities(text: str) -> set[str]:
    """Extract entities deterministically: proper nouns, abbreviations,
    citations, named methods, variable names, technical terms."""
    entities: set[str] = set()

    # Abbreviations (2+ uppercase letters)
    for m in re.finditer(r"\b[A-Z]{2,}\b", text):
        entities.add(m.group())

    # Capitalized words (potential proper nouns), skip sentence starts
    for m in re.finditer(r"(?<![.!?]\s)(?<!\n)\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", text):
        entities.add(m.group())

    # CamelCase identifiers
    for m in re.finditer(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b", text):
        entities.add(m.group())

    # snake_case and variable names
    for m in re.finditer(r"\b[a-z_][a-z0-9_]{2,}\b", text):
        val = m.group()
        if "_" in val:
            entities.add(val)

    # Method/function calls
    for m in re.finditer(r"\b(\w+)\(", text):
        entities.add(m.group(1))

    return entities


def compare_entities(source: str, candidate: str) -> EntityComparisonResult:
    """Compare entities between source and candidate."""
    source_entities = extract_entities(source)
    candidate_entities = extract_entities(candidate)

    missing = list(source_entities - candidate_entities)
    added = list(candidate_entities - source_entities)

    total = len(source_entities)
    preserved = len(source_entities & candidate_entities)
    score = preserved / total if total > 0 else 1.0

    return EntityComparisonResult(
        source_entities=sorted(source_entities),
        candidate_entities=sorted(candidate_entities),
        missing=sorted(missing),
        added=sorted(added),
        score=score,
    )
