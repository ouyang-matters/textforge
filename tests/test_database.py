"""Tests for database persistence."""

from __future__ import annotations

from uuid import uuid4

import pytest

from textforge.models import TextArtifact, TransformationRecord, WatermarkResult
from textforge.provenance.hashing import sha256_hash
from textforge.provenance.store import ProvenanceStore


@pytest.fixture
async def store():
    s = ProvenanceStore("sqlite+aiosqlite:///")
    await s.init_db()
    yield s
    await s.close()


class TestProvenanceStore:
    @pytest.mark.asyncio
    async def test_save_and_retrieve_artifact(self, store):
        artifact = TextArtifact(
            text="rewritten text",
            original_text="original text",
            source_provider="anthropic",
            source_model="test-model",
            source_hash=sha256_hash("original text"),
            output_hash=sha256_hash("rewritten text"),
            transformations=[
                TransformationRecord(
                    name="rewrite_academic",
                    input_hash=sha256_hash("original text"),
                    output_hash=sha256_hash("rewritten text"),
                    provider="anthropic",
                    model="test-model",
                )
            ],
        )

        await store.save_artifact(
            artifact, rewrite_provider="anthropic", rewrite_model="test-model"
        )
        data = await store.get_artifact(str(artifact.id))

        assert data is not None
        assert data["id"] == str(artifact.id)
        assert data["source_hash"] == sha256_hash("original text")
        assert data["output_hash"] == sha256_hash("rewritten text")

    @pytest.mark.asyncio
    async def test_artifact_not_found(self, store):
        data = await store.get_artifact("nonexistent-id")
        assert data is None

    @pytest.mark.asyncio
    async def test_save_watermark_result(self, store):
        wr = WatermarkResult(
            detector="test_detector",
            score=0.85,
            confidence=0.9,
            detected=True,
        )
        await store.save_watermark_result(None, None, wr)

    @pytest.mark.asyncio
    async def test_benchmark_run(self, store):
        run_id = str(uuid4())
        await store.create_benchmark_run(run_id, "test", {"profiles": ["minimal"]})

        sample = {
            "run_id": run_id,
            "sample_id": "s1",
            "source_length": 100,
            "output_length": 95,
            "profile": "minimal",
            "transformation": "rewrite_minimal",
            "domain": "general",
            "language": "en",
            "character_edit_ratio": 0.1,
            "token_edit_ratio": 0.08,
            "semantic_similarity": 0.98,
            "claim_preservation": 1.0,
            "validation_passed": True,
        }
        await store.save_benchmark_sample(sample)
        await store.complete_benchmark_run(run_id)

        data = await store.get_benchmark_run(run_id)
        assert data is not None
        assert data["status"] == "completed"
        assert len(data["samples"]) == 1
