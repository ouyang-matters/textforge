"""SQLAlchemy models for provenance persistence."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class ArtifactRow(Base):
    __tablename__ = "artifacts"

    id = Column(String(36), primary_key=True)
    original_text = Column(Text, nullable=False)
    output_text = Column(Text, nullable=True)
    source_provider = Column(String(64), nullable=True)
    source_model = Column(String(128), nullable=True)
    rewrite_provider = Column(String(64), nullable=True)
    rewrite_model = Column(String(128), nullable=True)
    source_hash = Column(String(64), nullable=False)
    output_hash = Column(String(64), nullable=True)
    metrics = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    transformations = relationship("TransformationRow", back_populates="artifact")
    validation_results = relationship("ValidationResultRow", back_populates="artifact")
    watermark_results = relationship("WatermarkResultRow", back_populates="artifact")


class TransformationRow(Base):
    __tablename__ = "transformations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    artifact_id = Column(String(36), ForeignKey("artifacts.id"), nullable=False)
    name = Column(String(128), nullable=False)
    input_hash = Column(String(64), nullable=False)
    output_hash = Column(String(64), nullable=False)
    provider = Column(String(64), nullable=True)
    model = Column(String(128), nullable=True)
    parameters = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC))

    artifact = relationship("ArtifactRow", back_populates="transformations")


class ValidationResultRow(Base):
    __tablename__ = "validation_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    artifact_id = Column(String(36), ForeignKey("artifacts.id"), nullable=False)
    validator = Column(String(64), nullable=False)
    score = Column(Float, nullable=True)
    passed = Column(Boolean, nullable=False)
    details = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC))

    artifact = relationship("ArtifactRow", back_populates="validation_results")


class WatermarkResultRow(Base):
    __tablename__ = "watermark_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    artifact_id = Column(String(36), ForeignKey("artifacts.id"), nullable=True)
    benchmark_run_id = Column(String(36), ForeignKey("benchmark_runs.id"), nullable=True)
    detector = Column(String(64), nullable=False)
    score = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    detected = Column(Boolean, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC))

    artifact = relationship("ArtifactRow", back_populates="watermark_results")


class BenchmarkRunRow(Base):
    __tablename__ = "benchmark_runs"

    id = Column(String(36), primary_key=True)
    name = Column(String(256), nullable=False)
    config = Column(JSON, nullable=True)
    status = Column(String(32), default="running")
    started_at = Column(DateTime, default=lambda: datetime.now(UTC))
    completed_at = Column(DateTime, nullable=True)

    samples = relationship("BenchmarkSampleRow", back_populates="run")


class BenchmarkSampleRow(Base):
    __tablename__ = "benchmark_samples"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("benchmark_runs.id"), nullable=False)
    sample_id = Column(String(64), nullable=False)
    source_text = Column(Text, nullable=True)
    output_text = Column(Text, nullable=True)
    source_length = Column(Integer, nullable=True)
    output_length = Column(Integer, nullable=True)
    profile = Column(String(32), nullable=True)
    transformation = Column(String(64), nullable=True)
    domain = Column(String(64), nullable=True)
    language = Column(String(8), nullable=True)
    character_edit_ratio = Column(Float, nullable=True)
    token_edit_ratio = Column(Float, nullable=True)
    semantic_similarity = Column(Float, nullable=True)
    claim_preservation = Column(Float, nullable=True)
    detector_score_before = Column(Float, nullable=True)
    detector_score_after = Column(Float, nullable=True)
    detector_confidence_before = Column(Float, nullable=True)
    detector_confidence_after = Column(Float, nullable=True)
    validation_passed = Column(Boolean, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC))

    run = relationship("BenchmarkRunRow", back_populates="samples")
