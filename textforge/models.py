"""Core domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ProtectedSpanKind(str, Enum):
    DISPLAY_LATEX = "display_latex"
    INLINE_LATEX = "inline_latex"
    CODE_BLOCK = "code_block"
    INLINE_CODE = "inline_code"
    URL = "url"
    DOI = "doi"
    CITATION = "citation"
    INTEGER = "integer"
    DECIMAL = "decimal"
    SCIENTIFIC = "scientific"
    PERCENTAGE = "percentage"
    EQUATION_LABEL = "equation_label"
    MATH_IDENTIFIER = "math_identifier"
    QUOTED_TEXT = "quoted_text"


class ProtectedSpan(BaseModel):
    placeholder: str
    original: str
    start: int
    end: int
    kind: ProtectedSpanKind


class TransformationRecord(BaseModel):
    name: str
    input_hash: str
    output_hash: str
    provider: str | None = None
    model: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    parameters: dict[str, str | int | float | bool | None] = {}


class TextArtifact(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    text: str
    original_text: str
    source_provider: str | None = None
    source_model: str | None = None
    source_hash: str
    output_hash: str | None = None
    protected_spans: list[ProtectedSpan] = []
    transformations: list[TransformationRecord] = []
    metrics: dict[str, float | int | str | bool | None] = {}


class EditMetrics(BaseModel):
    character_edit_ratio: float
    token_edit_ratio: float
    sentence_count_delta: int
    paragraph_count_delta: int
    length_ratio: float


class SemanticValidationResult(BaseModel):
    score: float
    passed: bool
    contradictions: list[str] = []
    missing_claims: list[str] = []
    added_claims: list[str] = []


class ClaimComparisonResult(BaseModel):
    source_claims: list[str]
    candidate_claims: list[str]
    preserved: list[str] = []
    missing: list[str] = []
    added: list[str] = []
    modified: list[str] = []
    score: float = 1.0


class EntityComparisonResult(BaseModel):
    source_entities: list[str]
    candidate_entities: list[str]
    missing: list[str] = []
    added: list[str] = []
    score: float = 1.0


class NumberPreservationResult(BaseModel):
    source_numbers: list[str]
    candidate_numbers: list[str]
    missing: list[str] = []
    added: list[str] = []
    passed: bool = True


class QualityCheckResult(BaseModel):
    passed: bool
    issues: list[str] = []


class WatermarkResult(BaseModel):
    detector: str
    score: float | None = None
    confidence: float | None = None
    detected: bool | None = None
    metadata: dict[str, str | float | int | bool | None] = {}


class ProviderResponse(BaseModel):
    text: str
    model: str
    provider: str
    metadata: dict[str, str | float | int | bool | None] = {}
    usage: dict[str, int] = {}


class RewriteContext(BaseModel):
    profile_name: str = "academic"
    max_edit_ratio: float = 0.5
    allow_sentence_split: bool = True
    allow_sentence_merge: bool = True
    allow_paragraph_reordering: bool = False
    preserve_paragraph_count: bool = True
    preserve_register: bool = True
    preserve_technical_terms: bool = True
    protected_spans: list[ProtectedSpan] = []
    paragraph_analyses: list[ParagraphAnalysis] = []


class ParagraphType(str, Enum):
    DEFINITION = "definition"
    ARGUMENT = "argument"
    EXAMPLE = "example"
    TRANSITION = "transition"
    ENUMERATION = "enumeration"
    TECHNICAL_EXPLANATION = "technical_explanation"
    QUOTATION = "quotation"
    CODE_RELATED = "code_related"
    OTHER = "other"


class ParagraphAnalysis(BaseModel):
    index: int
    text: str
    paragraph_type: ParagraphType
    sentence_count: int
    has_protected_content: bool = False


class StructuralAnalysisResult(BaseModel):
    paragraphs: list[ParagraphAnalysis]
    total_paragraphs: int
    total_sentences: int


class TransformationResult(BaseModel):
    text: str
    transformation_name: str
    input_hash: str
    output_hash: str
    parameters: dict[str, str | int | float | bool | None] = {}
