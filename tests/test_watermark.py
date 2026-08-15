"""Tests for watermark detector interface and benchmark aggregation."""

from __future__ import annotations

import pytest

from textforge.models import WatermarkResult
from textforge.watermark.base import WatermarkDetector
from textforge.watermark.metrics import aggregate_metrics
from textforge.watermark.synthid_adapter import SynthIDReferenceAdapter


class MockDetector:
    name = "mock_detector"

    def detect(self, text: str) -> WatermarkResult:
        return WatermarkResult(
            detector=self.name,
            score=0.85,
            confidence=0.9,
            detected=True,
            metadata={"length": len(text)},
        )


class TestWatermarkDetector:
    def test_mock_detector_interface(self):
        detector = MockDetector()
        assert isinstance(detector, WatermarkDetector)
        result = detector.detect("test text")
        assert result.detector == "mock_detector"
        assert result.score == 0.85
        assert result.detected is True

    def test_synthid_adapter_graceful_fallback(self):
        adapter = SynthIDReferenceAdapter()
        result = adapter.detect("test text")
        assert result.detector == "synthid_reference"
        # Score is None when synthid-text is not installed
        if not adapter.available:
            assert result.score is None
            assert "error" in result.metadata


class TestBenchmarkAggregation:
    def test_empty_samples(self):
        result = aggregate_metrics([])
        assert result == {}

    def test_basic_aggregation(self):
        samples = [
            {
                "character_edit_ratio": 0.1,
                "token_edit_ratio": 0.08,
                "semantic_similarity": 0.98,
                "claim_preservation": 1.0,
                "detector_score_before": 0.9,
                "detector_score_after": 0.3,
                "detector_confidence_before": 0.95,
                "detector_confidence_after": 0.4,
                "validation_passed": True,
            },
            {
                "character_edit_ratio": 0.2,
                "token_edit_ratio": 0.15,
                "semantic_similarity": 0.95,
                "claim_preservation": 0.9,
                "detector_score_before": 0.85,
                "detector_score_after": 0.25,
                "detector_confidence_before": 0.9,
                "detector_confidence_after": 0.35,
                "validation_passed": True,
            },
        ]
        result = aggregate_metrics(samples)
        assert result["count"] == 2
        assert "character_edit_ratio" in result
        assert result["character_edit_ratio"]["mean"] == pytest.approx(0.15)
        assert result["validation_pass_rate"] == 1.0

    def test_detection_rate(self):
        samples = [
            {"detector_score_before": 0.9, "detector_score_after": 0.3,
             "validation_passed": True},
            {"detector_score_before": 0.8, "detector_score_after": 0.6,
             "validation_passed": False},
            {"detector_score_before": 0.3, "detector_score_after": 0.1,
             "validation_passed": True},
        ]
        result = aggregate_metrics(samples)
        assert result["detection_rate_before"] == pytest.approx(2 / 3)
        assert result["detection_rate_after"] == pytest.approx(1 / 3)
