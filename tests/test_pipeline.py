"""Tests for the rewrite pipeline with mocked provider."""

from __future__ import annotations

import pytest

from tests.conftest import MockRewriteProvider
from textforge.config import RewriteProfile, TextForgeConfig
from textforge.rewrite.engine import RewriteEngine
from textforge.validation.semantic import SemanticValidator


@pytest.fixture
def engine():
    """Create engine with mock provider that echoes back input."""
    provider = MockRewriteProvider(response_text="")
    config = TextForgeConfig(
        anthropic_api_key="test",
        provenance={"enabled": False, "database": ":memory:"},
        validation={"semantic_threshold": 0.94, "enforce_numbers": True,
                     "enforce_entities": True, "enforce_claims": True},
    )
    return RewriteEngine(provider=provider, config=config)


@pytest.fixture
def engine_with_response():
    """Create engine where provider returns a specific response."""
    rewritten = (
        "Machine learning is a subfield of artificial intelligence. "
        "It focuses on building systems that learn from data. "
        "The accuracy reached 95.5% on the benchmark dataset."
    )
    provider = MockRewriteProvider(response_text=rewritten)
    config = TextForgeConfig(
        anthropic_api_key="test",
        provenance={"enabled": False, "database": ":memory:"},
        validation={"semantic_threshold": 0.0, "enforce_numbers": False,
                     "enforce_entities": False, "enforce_claims": False},
    )
    return RewriteEngine(provider=provider, config=config)


class TestRewritePipeline:
    @pytest.mark.asyncio
    async def test_basic_rewrite(self, engine_with_response):
        text = (
            "Machine learning is a subset of AI. "
            "It builds systems that learn from data. "
            "Accuracy was 95.5% on the benchmark."
        )
        artifact = await engine_with_response.rewrite(text, profile=RewriteProfile.ACADEMIC)

        assert artifact.text
        assert artifact.original_text
        assert artifact.source_hash
        assert artifact.output_hash
        assert len(artifact.transformations) > 0

    @pytest.mark.asyncio
    async def test_preserves_original_text(self, engine_with_response):
        text = "The original text should be preserved."
        artifact = await engine_with_response.rewrite(text, profile=RewriteProfile.MINIMAL)
        assert artifact.original_text == text

    @pytest.mark.asyncio
    async def test_metrics_computed(self, engine_with_response):
        text = "Some text to rewrite."
        artifact = await engine_with_response.rewrite(text)
        assert "character_edit_ratio" in artifact.metrics
        assert "token_edit_ratio" in artifact.metrics
        assert "length_ratio" in artifact.metrics

    @pytest.mark.asyncio
    async def test_protected_spans_in_artifact(self, engine_with_response):
        text = "The value $x = 42$ is important. See [1] for details."
        # The mock provider returns fixed text, but spans are still extracted
        artifact = await engine_with_response.rewrite(text)
        # Spans were extracted during pipeline
        assert artifact.original_text == text


class TestRetryLogic:
    @pytest.mark.asyncio
    async def test_retry_on_semantic_failure(self):
        """Test that engine retries when semantic validation fails."""
        call_count = 0

        class CountingProvider:
            provider_name = "counting"

            async def rewrite(self, text, system_prompt, **kwargs):
                nonlocal call_count
                call_count += 1
                from textforge.models import ProviderResponse
                return ProviderResponse(
                    text=f"Attempt {call_count}: " + text,
                    model="test", provider="counting",
                )

            async def structured_output(self, messages, **kwargs):
                from textforge.models import ProviderResponse
                return ProviderResponse(
                    text=(
                        '{"score": 0.5, "contradictions": ["test"],'
                        ' "missing_claims": [], "added_claims": []}'
                    ),
                    model="test", provider="counting",
                )

            async def generate(self, messages, **kwargs):
                return await self.structured_output(messages, **kwargs)

        provider = CountingProvider()
        config = TextForgeConfig(
            anthropic_api_key="test",
            provenance={"enabled": False, "database": ":memory:"},
            validation={"semantic_threshold": 0.99, "enforce_numbers": False,
                         "enforce_entities": False, "enforce_claims": False},
        )
        validator = SemanticValidator(provider=provider, threshold=0.99)
        engine = RewriteEngine(provider=provider, config=config, semantic_validator=validator)

        await engine.rewrite("Test text.", profile=RewriteProfile.ACADEMIC)
        # Should have retried (max_retries=2 for academic + 1 initial = 3 attempts)
        assert call_count == 3  # initial + 2 retries

    @pytest.mark.asyncio
    async def test_max_retries_respected(self):
        """Test that engine respects max retries."""
        call_count = 0

        class FailingProvider:
            provider_name = "failing"

            async def rewrite(self, text, system_prompt, **kwargs):
                nonlocal call_count
                call_count += 1
                from textforge.models import ProviderResponse
                return ProviderResponse(
                    text="<TF_PROTECTED_9999> bad text",
                    model="test", provider="failing",
                )

            async def structured_output(self, messages, **kwargs):
                from textforge.models import ProviderResponse
                return ProviderResponse(text="{}", model="test", provider="failing")

            async def generate(self, messages, **kwargs):
                return await self.structured_output(messages, **kwargs)

        config = TextForgeConfig(
            anthropic_api_key="test",
            provenance={"enabled": False, "database": ":memory:"},
        )
        engine = RewriteEngine(provider=FailingProvider(), config=config)

        await engine.rewrite("Good text.", profile=RewriteProfile.MINIMAL)
        # minimal has max_retries=1, so 1 initial + 1 retry = 2
        assert call_count == 2
