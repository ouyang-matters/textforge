"""Aggregation utilities for watermark benchmark metrics."""

from __future__ import annotations

import math
import statistics
from typing import Any


def aggregate_metrics(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate statistics over benchmark samples."""
    if not samples:
        return {}

    numeric_keys = [
        "character_edit_ratio",
        "token_edit_ratio",
        "semantic_similarity",
        "claim_preservation",
        "detector_score_before",
        "detector_score_after",
        "detector_confidence_before",
        "detector_confidence_after",
    ]

    result: dict[str, Any] = {"count": len(samples)}

    for key in numeric_keys:
        values = [s[key] for s in samples if s.get(key) is not None]
        if not values:
            continue

        stats: dict[str, float | None] = {
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "std": statistics.stdev(values) if len(values) > 1 else 0.0,
            "min": min(values),
            "max": max(values),
        }

        # Quantiles
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        if n >= 4:
            stats["q25"] = sorted_vals[n // 4]
            stats["q75"] = sorted_vals[(3 * n) // 4]

        result[key] = stats

    # Detection rate
    detected_before = [s for s in samples if s.get("detector_score_before") is not None]
    detected_after = [s for s in samples if s.get("detector_score_after") is not None]

    if detected_before:
        threshold = 0.5
        rate = sum(1 for s in detected_before if (s.get("detector_score_before") or 0) > threshold)
        result["detection_rate_before"] = rate / len(detected_before)

    if detected_after:
        threshold = 0.5
        rate = sum(1 for s in detected_after if (s.get("detector_score_after") or 0) > threshold)
        result["detection_rate_after"] = rate / len(detected_after)

    # Validation pass rate
    validated = [s for s in samples if s.get("validation_passed") is not None]
    if validated:
        result["validation_pass_rate"] = sum(
            1 for s in validated if s["validation_passed"]
        ) / len(validated)

    # Confidence intervals (95% CI using normal approximation)
    for key in numeric_keys:
        values = [s[key] for s in samples if s.get(key) is not None]
        if len(values) >= 2:
            mean = statistics.mean(values)
            se = statistics.stdev(values) / math.sqrt(len(values))
            result.setdefault(key, {})
            if isinstance(result[key], dict):
                result[key]["ci_95_lower"] = mean - 1.96 * se
                result[key]["ci_95_upper"] = mean + 1.96 * se

    return result
