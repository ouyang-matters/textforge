"""Rewrite engine: the core rewrite pipeline."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

import structlog

from textforge.config import ProfileConfig, RewriteProfile, TextForgeConfig
from textforge.models import (
    EditMetrics,
    RewriteContext,
    TextArtifact,
    TransformationRecord,
)
from textforge.provenance.hashing import sha256_hash
from textforge.providers.base import RewriteProvider
from textforge.rewrite.planner import analyze_structure_deterministic
from textforge.rewrite.prompts import (
    PROFILE_INSTRUCTIONS,
    RETRY_PROMPT,
    REWRITE_SYSTEM_PROMPT,
)
from textforge.rewrite.protected_spans import extract_protected_spans, restore_protected_spans
from textforge.validation.numbers import extract_numbers, validate_numbers
from textforge.validation.quality import check_quality
from textforge.validation.semantic import SemanticValidator

logger = structlog.get_logger()


def _normalize_text(text: str) -> str:
    """Normalize unicode and whitespace."""
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _count_sentences(text: str) -> int:
    return len([s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()])


def _count_paragraphs(text: str) -> int:
    return len([p for p in re.split(r"\n\s*\n", text) if p.strip()])


def _simple_tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer."""
    return re.findall(r"\b\w+\b|[^\w\s]", text)


def _levenshtein_ratio(s1: str, s2: str) -> float:
    """Normalized Levenshtein distance."""
    try:
        from Levenshtein import distance

        if not s1 and not s2:
            return 0.0
        d = distance(s1, s2)
        return d / max(len(s1), len(s2))
    except ImportError:
        # Fallback: simple character-level comparison
        if not s1 and not s2:
            return 0.0
        max_len = max(len(s1), len(s2))
        matches = sum(c1 == c2 for c1, c2 in zip(s1, s2))
        return 1.0 - (matches / max_len)


def _token_edit_ratio(s1: str, s2: str) -> float:
    """Token-level edit ratio using simple tokenizer."""
    t1 = _simple_tokenize(s1)
    t2 = _simple_tokenize(s2)
    if not t1 and not t2:
        return 0.0
    # Use set-based comparison for simplicity
    set1, set2 = set(t1), set(t2)
    if not set1 and not set2:
        return 0.0
    intersection = set1 & set2
    union = set1 | set2
    return 1.0 - (len(intersection) / len(union)) if union else 0.0


def compute_edit_metrics(source: str, candidate: str) -> EditMetrics:
    """Compute edit metrics between source and candidate."""
    return EditMetrics(
        character_edit_ratio=_levenshtein_ratio(source, candidate),
        token_edit_ratio=_token_edit_ratio(source, candidate),
        sentence_count_delta=_count_sentences(candidate) - _count_sentences(source),
        paragraph_count_delta=_count_paragraphs(candidate) - _count_paragraphs(source),
        length_ratio=len(candidate) / len(source) if source else 0.0,
    )


class RewriteEngine:
    """Core rewrite engine implementing the full pipeline."""

    def __init__(
        self,
        provider: RewriteProvider,
        config: TextForgeConfig,
        semantic_validator: SemanticValidator | None = None,
    ):
        self._provider = provider
        self._config = config
        self._semantic_validator = semantic_validator

    async def rewrite(
        self,
        text: str,
        *,
        profile: RewriteProfile | None = None,
        source_provider: str | None = None,
        source_model: str | None = None,
        preserve: dict[str, bool] | None = None,
    ) -> TextArtifact:
        """Execute the full rewrite pipeline."""
        profile = profile or self._config.rewrite.profile
        profile_config = self._config.get_profile_config(profile)
        model = self._config.rewrite.model or self._config.default_rewrite_model

        # 1. Normalize
        normalized = _normalize_text(text)
        source_hash = sha256_hash(normalized)

        # 2. Extract protected spans
        protected_text, spans = extract_protected_spans(normalized)

        # 3. Structural analysis
        structure = analyze_structure_deterministic(protected_text)

        # 4. Build rewrite context (stored on artifact for downstream use)
        _context = RewriteContext(
            profile_name=profile.value,
            max_edit_ratio=profile_config.max_edit_ratio,
            allow_sentence_split=profile_config.allow_sentence_split,
            allow_sentence_merge=profile_config.allow_sentence_merge,
            allow_paragraph_reordering=profile_config.allow_paragraph_reordering,
            preserve_paragraph_count=profile_config.preserve_paragraph_count,
            preserve_register=profile_config.preserve_register,
            preserve_technical_terms=profile_config.preserve_technical_terms,
            protected_spans=spans,
            paragraph_analyses=structure.paragraphs,
        )

        # 5. Source numbers for validation
        source_numbers = extract_numbers(normalized)

        # 6. Generate candidate with retries
        candidate_text = protected_text
        transformations: list[TransformationRecord] = []
        validation_results: list[dict[str, Any]] = []
        last_issues: list[str] = []

        for attempt in range(profile_config.max_retries + 1):
            # Generate candidate
            if attempt == 0:
                candidate_text = await self._generate_candidate(
                    protected_text, profile, profile_config, model
                )
            else:
                candidate_text = await self._retry_candidate(
                    protected_text, candidate_text, last_issues, model
                )

            # Record transformation
            transformations.append(TransformationRecord(
                name=f"rewrite_{profile.value}" + (f"_retry_{attempt}" if attempt > 0 else ""),
                input_hash=sha256_hash(protected_text),
                output_hash=sha256_hash(candidate_text),
                provider=self._provider.provider_name,
                model=model,
                parameters={
                    "profile": profile.value,
                    "attempt": attempt,
                },
            ))

            # 7. Restore protected spans
            restored = restore_protected_spans(candidate_text, spans)

            # 8. Validate
            issues = []

            # Quality check
            quality = check_quality(restored)
            if not quality.passed:
                issues.extend(quality.issues)
                validation_results.append({
                    "validator": "quality",
                    "passed": False,
                    "details": {"issues": quality.issues},
                })

            # Number preservation
            if self._config.validation.enforce_numbers:
                num_result = validate_numbers(source_numbers, extract_numbers(restored))
                if not num_result.passed:
                    issues.append(
                        f"Number mismatch: missing={num_result.missing}, added={num_result.added}"
                    )
                    validation_results.append({
                        "validator": "numbers",
                        "passed": False,
                        "details": {
                            "missing": num_result.missing,
                            "added": num_result.added,
                        },
                    })

            # Semantic validation
            semantic_score = 1.0
            if self._semantic_validator:
                sem_result = await self._semantic_validator.compare(normalized, restored)
                semantic_score = sem_result.score
                if not sem_result.passed:
                    issues.append(f"Semantic similarity {sem_result.score:.2f} below threshold")
                    if sem_result.contradictions:
                        issues.append(f"Contradictions: {sem_result.contradictions}")
                    if sem_result.missing_claims:
                        issues.append(f"Missing claims: {sem_result.missing_claims}")
                validation_results.append({
                    "validator": "semantic",
                    "score": sem_result.score,
                    "passed": sem_result.passed,
                    "details": {
                        "contradictions": sem_result.contradictions,
                        "missing_claims": sem_result.missing_claims,
                        "added_claims": sem_result.added_claims,
                    },
                })

            # If no issues, break
            if not issues:
                logger.info("rewrite_succeeded", attempt=attempt, profile=profile.value)
                break

            last_issues = issues
            logger.info(
                "rewrite_validation_failed",
                attempt=attempt,
                issues=issues,
            )

            if attempt >= profile_config.max_retries:
                logger.warning("rewrite_max_retries", profile=profile.value)

        # 9. Compute metrics
        metrics = compute_edit_metrics(normalized, restored)
        metrics_dict: dict[str, float | int | str | bool | None] = {
            "character_edit_ratio": metrics.character_edit_ratio,
            "token_edit_ratio": metrics.token_edit_ratio,
            "sentence_count_delta": metrics.sentence_count_delta,
            "paragraph_count_delta": metrics.paragraph_count_delta,
            "length_ratio": metrics.length_ratio,
            "semantic_similarity": semantic_score,
        }

        # 10. Build artifact
        output_hash = sha256_hash(restored)
        artifact = TextArtifact(
            text=restored,
            original_text=normalized,
            source_provider=source_provider,
            source_model=source_model,
            source_hash=source_hash,
            output_hash=output_hash,
            protected_spans=spans,
            transformations=transformations,
            metrics=metrics_dict,
        )

        return artifact

    async def _generate_candidate(
        self,
        text: str,
        profile: RewriteProfile,
        profile_config: ProfileConfig,
        model: str,
    ) -> str:
        profile_instructions = PROFILE_INSTRUCTIONS.get(profile.value, "")
        system_prompt = REWRITE_SYSTEM_PROMPT.format(
            profile=profile.value,
            max_edit_ratio=profile_config.max_edit_ratio,
            allow_sentence_split=profile_config.allow_sentence_split,
            allow_sentence_merge=profile_config.allow_sentence_merge,
            allow_paragraph_reordering=profile_config.allow_paragraph_reordering,
            preserve_paragraph_count=profile_config.preserve_paragraph_count,
            preserve_register=profile_config.preserve_register,
            preserve_technical_terms=profile_config.preserve_technical_terms,
            profile_instructions=profile_instructions,
        )

        response = await self._provider.rewrite(
            text, system_prompt, model=model, temperature=0.4
        )
        return response.text.strip()

    async def _retry_candidate(
        self,
        original: str,
        previous: str,
        issues: list[str],
        model: str,
    ) -> str:
        prompt = RETRY_PROMPT.format(
            issues="\n".join(f"- {i}" for i in issues),
            original=original,
            previous=previous,
        )
        response = await self._provider.rewrite(
            prompt,
            "Fix the issues and return only the corrected rewritten text.",
            model=model,
            temperature=0.3,
        )
        return response.text.strip()
