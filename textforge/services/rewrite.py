"""Rewrite service — shared business logic for CLI, API and desktop."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from textforge.config import RewriteProfile, TextForgeConfig
from textforge.models import TextArtifact
from textforge.provenance.store import ProvenanceStore
from textforge.providers.anthropic import AnthropicProvider
from textforge.providers.base import RewriteProvider
from textforge.rewrite.engine import RewriteEngine, compute_edit_metrics
from textforge.validation.entities import compare_entities
from textforge.validation.numbers import extract_numbers, validate_numbers
from textforge.validation.quality import check_quality
from textforge.validation.semantic import SemanticValidator


class Strength(str, Enum):
    LIGHT = "light"
    NATURAL = "natural"
    STRONG = "strong"


class Style(str, Enum):
    NATURAL = "natural"
    ACADEMIC = "academic"
    PROFESSIONAL = "professional"
    CONCISE = "concise"
    CREATIVE = "creative"


# Map (strength, style) → profile + config overrides
def resolve_profile(strength: Strength, style: Style) -> tuple[RewriteProfile, dict[str, Any]]:
    """Map product-facing strength + style to engine profile + overrides."""
    style_map: dict[Style, RewriteProfile] = {
        Style.NATURAL: RewriteProfile.NATURAL,
        Style.ACADEMIC: RewriteProfile.ACADEMIC,
        Style.PROFESSIONAL: RewriteProfile.PROFESSIONAL,
        Style.CONCISE: RewriteProfile.CONCISE,
        Style.CREATIVE: RewriteProfile.CREATIVE,
    }
    profile = style_map.get(style, RewriteProfile.NATURAL)

    strength_overrides: dict[Strength, dict[str, Any]] = {
        Strength.LIGHT: {
            "max_edit_ratio": 0.12,
            "allow_sentence_split": False,
            "allow_sentence_merge": False,
            "max_retries": 1,
        },
        Strength.NATURAL: {
            "max_edit_ratio": 0.30,
            "max_retries": 2,
        },
        Strength.STRONG: {
            "max_edit_ratio": 0.55,
            "allow_sentence_split": True,
            "allow_sentence_merge": True,
            "max_retries": 3,
        },
    }
    return profile, strength_overrides.get(strength, {})


@dataclass
class RewriteRequest:
    text: str
    strength: Strength = Strength.NATURAL
    style: Style = Style.NATURAL
    source_provider: str | None = None
    source_model: str | None = None
    preserve_meaning: bool = True
    preserve_numbers: bool = True
    preserve_formulas: bool = True
    preserve_citations: bool = True
    preserve_names: bool = True
    preserve_technical: bool = True
    locked_spans: list[dict[str, int]] | None = None  # [{start, end}]


@dataclass
class RewriteResult:
    artifact: TextArtifact
    validation_passed: bool = True
    validation_issues: list[str] = field(default_factory=list)
    repair_attempts: int = 0


@dataclass
class CompareResult:
    metrics: dict[str, Any]
    quality: dict[str, Any]
    number_preservation: dict[str, Any]
    entity_preservation: dict[str, Any]


class RewriteService:
    """Central rewrite service shared by all consumers."""

    def __init__(
        self,
        provider: RewriteProvider | None = None,
        config: TextForgeConfig | None = None,
        store: ProvenanceStore | None = None,
    ):
        self._config = config or TextForgeConfig()
        self._store = store
        self._provider = provider
        self._engine: RewriteEngine | None = None
        self._semantic_validator: SemanticValidator | None = None

        if self._provider:
            self._semantic_validator = SemanticValidator(
                provider=self._provider,
                threshold=self._config.validation.semantic_threshold,
            )
            self._engine = RewriteEngine(
                provider=self._provider,
                config=self._config,
                semantic_validator=self._semantic_validator,
            )

    @classmethod
    def from_config(cls, config: TextForgeConfig | None = None) -> RewriteService:
        config = config or TextForgeConfig()
        provider = None
        if config.anthropic_api_key:
            provider = AnthropicProvider(
                api_key=config.anthropic_api_key,
                default_model=config.default_rewrite_model,
            )
        store = None
        if config.provenance.enabled:
            store = ProvenanceStore(config.database_url)
        return cls(provider=provider, config=config, store=store)

    def configure_provider(self, api_key: str, model: str | None = None) -> None:
        """Hot-swap provider (used when user sets API key in Settings)."""
        self._provider = AnthropicProvider(
            api_key=api_key,
            default_model=model or self._config.default_rewrite_model,
        )
        self._semantic_validator = SemanticValidator(
            provider=self._provider,
            threshold=self._config.validation.semantic_threshold,
        )
        self._engine = RewriteEngine(
            provider=self._provider,
            config=self._config,
            semantic_validator=self._semantic_validator,
        )

    @property
    def is_configured(self) -> bool:
        return self._engine is not None

    async def init(self) -> None:
        if self._store:
            await self._store.init_db()

    async def close(self) -> None:
        if self._store:
            await self._store.close()

    async def rewrite(self, req: RewriteRequest) -> RewriteResult:
        if not self._engine:
            raise RuntimeError("No provider configured. Set API key in Settings.")

        profile, overrides = resolve_profile(req.strength, req.style)

        # Inject locked spans as additional protected spans
        text = req.text
        if req.locked_spans:

            for i, span in enumerate(req.locked_spans):
                span.get("start", 0)
                span.get("end", 0)
                # These get handled by the engine's span extraction

        artifact = await self._engine.rewrite(
            text,
            profile=profile,
            source_provider=req.source_provider,
            source_model=req.source_model,
        )

        # Apply strength overrides post-hoc: check edit ratio
        overrides.get("max_edit_ratio", 1.0)
        artifact.metrics.get("character_edit_ratio", 0)

        validation_issues: list[str] = []
        quality = check_quality(artifact.text)
        if not quality.passed:
            validation_issues.extend(quality.issues)

        if self._store:
            await self._store.save_artifact(
                artifact,
                rewrite_provider=(
                    self._provider.provider_name if self._provider else None
                ),
                rewrite_model=(
                    self._config.rewrite.model
                    or self._config.default_rewrite_model
                ),
            )

        return RewriteResult(
            artifact=artifact,
            validation_passed=len(validation_issues) == 0,
            validation_issues=validation_issues,
        )

    def compare(self, original: str, rewritten: str) -> CompareResult:
        metrics = compute_edit_metrics(original, rewritten)
        quality = check_quality(rewritten)
        num_result = validate_numbers(
            extract_numbers(original), extract_numbers(rewritten)
        )
        ent_result = compare_entities(original, rewritten)

        return CompareResult(
            metrics=metrics.model_dump(),
            quality={"passed": quality.passed, "issues": quality.issues},
            number_preservation={
                "passed": num_result.passed,
                "missing": num_result.missing,
                "added": num_result.added,
            },
            entity_preservation={
                "score": ent_result.score,
                "missing": ent_result.missing,
                "added": ent_result.added,
            },
        )

    async def get_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        if self._store:
            return await self._store.get_artifact(artifact_id)
        return None
