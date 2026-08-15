"""Provenance persistence store."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from textforge.models import TextArtifact, WatermarkResult
from textforge.provenance.models import (
    ArtifactRow,
    Base,
    BenchmarkRunRow,
    BenchmarkSampleRow,
    TransformationRow,
    ValidationResultRow,
    WatermarkResultRow,
)


class ProvenanceStore:
    def __init__(self, database_url: str = "sqlite+aiosqlite:///./textforge.db"):
        self._engine = create_async_engine(database_url, echo=False)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    async def init_db(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self._engine.dispose()

    async def save_artifact(
        self,
        artifact: TextArtifact,
        *,
        rewrite_provider: str | None = None,
        rewrite_model: str | None = None,
        validation_results: list[dict[str, Any]] | None = None,
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                row = ArtifactRow(
                    id=str(artifact.id),
                    original_text=artifact.original_text,
                    output_text=artifact.text,
                    source_provider=artifact.source_provider,
                    source_model=artifact.source_model,
                    rewrite_provider=rewrite_provider,
                    rewrite_model=rewrite_model,
                    source_hash=artifact.source_hash,
                    output_hash=artifact.output_hash,
                    metrics=artifact.metrics,
                    created_at=datetime.now(UTC),
                )
                session.add(row)

                for t in artifact.transformations:
                    session.add(TransformationRow(
                        artifact_id=str(artifact.id),
                        name=t.name,
                        input_hash=t.input_hash,
                        output_hash=t.output_hash,
                        provider=t.provider,
                        model=t.model,
                        parameters=t.parameters,
                        timestamp=t.timestamp,
                    ))

                if validation_results:
                    for v in validation_results:
                        session.add(ValidationResultRow(
                            artifact_id=str(artifact.id),
                            validator=v.get("validator", "unknown"),
                            score=v.get("score"),
                            passed=v.get("passed", False),
                            details=v.get("details"),
                            timestamp=datetime.now(UTC),
                        ))

    async def get_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(ArtifactRow).where(ArtifactRow.id == artifact_id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return {
                "id": row.id,
                "original_text": row.original_text,
                "output_text": row.output_text,
                "source_provider": row.source_provider,
                "source_model": row.source_model,
                "rewrite_provider": row.rewrite_provider,
                "rewrite_model": row.rewrite_model,
                "source_hash": row.source_hash,
                "output_hash": row.output_hash,
                "metrics": row.metrics,
                "created_at": str(row.created_at),
            }

    async def save_watermark_result(
        self,
        artifact_id: str | None,
        benchmark_run_id: str | None,
        result: WatermarkResult,
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                session.add(WatermarkResultRow(
                    artifact_id=artifact_id,
                    benchmark_run_id=benchmark_run_id,
                    detector=result.detector,
                    score=result.score,
                    confidence=result.confidence,
                    detected=result.detected,
                    metadata_json=result.metadata,
                    timestamp=datetime.now(UTC),
                ))

    async def create_benchmark_run(
        self, run_id: str, name: str, config: dict[str, Any]
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                session.add(BenchmarkRunRow(
                    id=run_id,
                    name=name,
                    config=config,
                    status="running",
                    started_at=datetime.now(UTC),
                ))

    async def save_benchmark_sample(self, sample: dict[str, Any]) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                session.add(BenchmarkSampleRow(**sample))

    async def complete_benchmark_run(self, run_id: str) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(
                    select(BenchmarkRunRow).where(BenchmarkRunRow.id == run_id)
                )
                row = result.scalar_one_or_none()
                if row:
                    row.status = "completed"
                    row.completed_at = datetime.now(UTC)

    async def get_benchmark_run(self, run_id: str) -> dict[str, Any] | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(BenchmarkRunRow).where(BenchmarkRunRow.id == run_id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None

            samples_result = await session.execute(
                select(BenchmarkSampleRow).where(BenchmarkSampleRow.run_id == run_id)
            )
            samples = samples_result.scalars().all()

            return {
                "id": row.id,
                "name": row.name,
                "config": row.config,
                "status": row.status,
                "started_at": str(row.started_at),
                "completed_at": str(row.completed_at) if row.completed_at else None,
                "samples": [
                    {
                        "sample_id": s.sample_id,
                        "source_length": s.source_length,
                        "output_length": s.output_length,
                        "profile": s.profile,
                        "transformation": s.transformation,
                        "domain": s.domain,
                        "language": s.language,
                        "character_edit_ratio": s.character_edit_ratio,
                        "token_edit_ratio": s.token_edit_ratio,
                        "semantic_similarity": s.semantic_similarity,
                        "claim_preservation": s.claim_preservation,
                        "detector_score_before": s.detector_score_before,
                        "detector_score_after": s.detector_score_after,
                        "detector_confidence_before": s.detector_confidence_before,
                        "detector_confidence_after": s.detector_confidence_after,
                        "validation_passed": s.validation_passed,
                    }
                    for s in samples
                ],
            }
