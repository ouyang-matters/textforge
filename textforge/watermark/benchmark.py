"""Watermark benchmark framework."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from textforge.provenance.store import ProvenanceStore
from textforge.rewrite.engine import RewriteEngine, compute_edit_metrics
from textforge.watermark.base import WatermarkDetector
from textforge.watermark.metrics import aggregate_metrics


class BenchmarkConfig:
    def __init__(self, data: dict[str, Any]):
        self.name: str = data.get("name", "unnamed")
        self.languages: list[str] = data.get("languages", ["en"])
        self.domains: list[str] = data.get("domains", ["general"])
        self.profiles: list[str] = data.get("profiles", ["minimal", "natural", "academic"])
        self.lengths: list[int] = data.get("lengths", [256, 512, 1024])
        self.samples_per_cell: int = data.get("samples_per_cell", 20)
        self.raw = data

    @classmethod
    def from_yaml(cls, path: str | Path) -> BenchmarkConfig:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls(data)


class BenchmarkRunner:
    """Run controlled watermark robustness experiments."""

    def __init__(
        self,
        engine: RewriteEngine,
        detector: WatermarkDetector | None = None,
        store: ProvenanceStore | None = None,
    ):
        self._engine = engine
        self._detector = detector
        self._store = store

    async def run(
        self,
        config: BenchmarkConfig,
        texts: list[str] | None = None,
    ) -> BenchmarkResult:
        """Run a benchmark experiment.

        If texts are not provided, uses placeholder texts for the dimensions
        specified in the config. In production use, callers should provide
        watermarked texts for which they own the configuration.
        """
        from textforge.config import RewriteProfile

        run_id = str(uuid4())
        if self._store:
            await self._store.create_benchmark_run(run_id, config.name, config.raw)

        samples: list[dict[str, Any]] = []
        input_texts = texts or [
            "Sample text for benchmarking. " * (length // 40 + 1)
            for length in config.lengths
        ]

        for domain in config.domains:
            for language in config.languages:
                for profile_name in config.profiles:
                    try:
                        profile = RewriteProfile(profile_name)
                    except ValueError:
                        continue

                    for text in input_texts:
                        for sample_idx in range(config.samples_per_cell):
                            sample = await self._run_single(
                                run_id=run_id,
                                text=text,
                                profile=profile,
                                domain=domain,
                                language=language,
                                sample_idx=sample_idx,
                            )
                            samples.append(sample)

                            if self._store:
                                await self._store.save_benchmark_sample(sample)

        if self._store:
            await self._store.complete_benchmark_run(run_id)

        return BenchmarkResult(
            run_id=run_id,
            config=config,
            samples=samples,
            aggregated=aggregate_metrics(samples),
        )

    async def _run_single(
        self,
        run_id: str,
        text: str,
        profile: Any,
        domain: str,
        language: str,
        sample_idx: int,
    ) -> dict[str, Any]:
        sample_id = f"{run_id}_{domain}_{language}_{profile.value}_{sample_idx}"

        # Detect before
        score_before = None
        confidence_before = None
        if self._detector:
            wr_before = self._detector.detect(text)
            score_before = wr_before.score
            confidence_before = wr_before.confidence

        # Rewrite
        try:
            artifact = await self._engine.rewrite(text, profile=profile)
            output = artifact.text
            metrics = compute_edit_metrics(text, output)
            validation_passed = True
            semantic_sim = artifact.metrics.get("semantic_similarity")
        except Exception:
            output = text
            metrics = compute_edit_metrics(text, text)
            validation_passed = False
            semantic_sim = None

        # Detect after
        score_after = None
        confidence_after = None
        if self._detector:
            wr_after = self._detector.detect(output)
            score_after = wr_after.score
            confidence_after = wr_after.confidence

        return {
            "run_id": run_id,
            "sample_id": sample_id,
            "source_length": len(text),
            "output_length": len(output),
            "profile": profile.value,
            "transformation": f"rewrite_{profile.value}",
            "domain": domain,
            "language": language,
            "character_edit_ratio": metrics.character_edit_ratio,
            "token_edit_ratio": metrics.token_edit_ratio,
            "semantic_similarity": semantic_sim,
            "claim_preservation": None,
            "detector_score_before": score_before,
            "detector_score_after": score_after,
            "detector_confidence_before": confidence_before,
            "detector_confidence_after": confidence_after,
            "validation_passed": validation_passed,
        }


class BenchmarkResult:
    """Result of a benchmark run."""

    def __init__(
        self,
        run_id: str,
        config: BenchmarkConfig,
        samples: list[dict[str, Any]],
        aggregated: dict[str, Any],
    ):
        self.run_id = run_id
        self.config = config
        self.samples = samples
        self.aggregated = aggregated

    def to_csv(self) -> str:
        if not self.samples:
            return ""
        fieldnames = [
            "sample_id", "source_length", "output_length", "profile",
            "transformation", "character_edit_ratio", "token_edit_ratio",
            "semantic_similarity", "claim_preservation",
            "detector_score_before", "detector_score_after",
            "detector_confidence_before", "detector_confidence_after",
            "validation_passed",
        ]
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(self.samples)
        return output.getvalue()

    def to_json(self) -> str:
        return json.dumps(
            {
                "run_id": self.run_id,
                "config": self.config.raw,
                "samples": self.samples,
                "aggregated": self.aggregated,
            },
            indent=2,
            default=str,
        )
