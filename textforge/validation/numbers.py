"""Deterministic numeric preservation validation."""

from __future__ import annotations

import re
from collections import Counter

from textforge.models import NumberPreservationResult

# Patterns for number extraction, ordered from most specific to least
_NUMBER_PATTERNS = [
    # Scientific notation: 1.5e10, 3.2E-4
    re.compile(r"-?\d+\.?\d*[eE][+-]?\d+"),
    # Percentages: 42%, 3.14%
    re.compile(r"-?\d+\.?\d*%"),
    # Fractions: 1/2, 3/4
    re.compile(r"-?\d+/\d+"),
    # Decimals: 3.14, -0.5
    re.compile(r"-?\d+\.\d+"),
    # Integers (standalone)
    re.compile(r"(?<!\w)-?\d+(?!\w|\.?\d|[eE])"),
]


def extract_numbers(text: str) -> list[str]:
    """Extract all numbers from text as strings."""
    numbers: list[str] = []
    # Track positions to avoid overlapping matches
    used_positions: set[int] = set()

    for pattern in _NUMBER_PATTERNS:
        for m in pattern.finditer(text):
            # Skip if this position was already matched
            if any(pos in used_positions for pos in range(m.start(), m.end())):
                continue
            numbers.append(m.group())
            for pos in range(m.start(), m.end()):
                used_positions.add(pos)

    return sorted(numbers)


def validate_numbers(
    source_numbers: list[str],
    candidate_numbers: list[str],
) -> NumberPreservationResult:
    """Validate exact multiset equality of numbers."""
    source_counter = Counter(source_numbers)
    candidate_counter = Counter(candidate_numbers)

    missing: list[str] = []
    added: list[str] = []

    for num, count in source_counter.items():
        diff = count - candidate_counter.get(num, 0)
        if diff > 0:
            missing.extend([num] * diff)

    for num, count in candidate_counter.items():
        diff = count - source_counter.get(num, 0)
        if diff > 0:
            added.extend([num] * diff)

    return NumberPreservationResult(
        source_numbers=source_numbers,
        candidate_numbers=candidate_numbers,
        missing=missing,
        added=added,
        passed=len(missing) == 0 and len(added) == 0,
    )
