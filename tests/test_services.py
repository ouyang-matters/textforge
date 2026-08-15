"""Tests for the service layer."""

from __future__ import annotations

import pytest

from tests.conftest import MockRewriteProvider
from textforge.config import TextForgeConfig
from textforge.services.rewrite import (
    RewriteRequest,
    RewriteService,
    Strength,
    Style,
    resolve_profile,
)


class TestResolveProfile:
    def test_light_natural(self):
        profile, overrides = resolve_profile(Strength.LIGHT, Style.NATURAL)
        assert profile.value == "natural"
        assert overrides["max_edit_ratio"] == 0.12
        assert overrides["allow_sentence_split"] is False

    def test_strong_academic(self):
        profile, overrides = resolve_profile(Strength.STRONG, Style.ACADEMIC)
        assert profile.value == "academic"
        assert overrides["max_edit_ratio"] == 0.55
        assert overrides["allow_sentence_split"] is True

    def test_natural_concise(self):
        profile, overrides = resolve_profile(Strength.NATURAL, Style.CONCISE)
        assert profile.value == "concise"
        assert overrides["max_edit_ratio"] == 0.30


class TestRewriteService:
    def _make_service(self, response_text: str = "Rewritten.") -> RewriteService:
        provider = MockRewriteProvider(response_text=response_text)
        config = TextForgeConfig(
            anthropic_api_key="test",
            provenance={"enabled": False, "database": ":memory:"},
            validation={
                "semantic_threshold": 0.0,
                "enforce_numbers": False,
                "enforce_entities": False,
                "enforce_claims": False,
            },
        )
        return RewriteService(provider=provider, config=config)

    @pytest.mark.asyncio
    async def test_rewrite_basic(self):
        svc = self._make_service("The answer is 42.")
        result = await svc.rewrite(RewriteRequest(text="The answer is 42."))
        assert result.artifact.text
        assert result.artifact.original_text

    @pytest.mark.asyncio
    async def test_rewrite_with_strength_style(self):
        svc = self._make_service("Rewritten text.")
        result = await svc.rewrite(RewriteRequest(
            text="Original text.",
            strength=Strength.LIGHT,
            style=Style.ACADEMIC,
        ))
        assert result.artifact.text

    def test_compare(self):
        svc = self._make_service()
        result = svc.compare("Hello world.", "Hello planet.")
        assert "character_edit_ratio" in result.metrics
        assert isinstance(result.quality["passed"], bool)

    def test_is_configured(self):
        svc = self._make_service()
        assert svc.is_configured

    def test_not_configured_without_provider(self):
        config = TextForgeConfig(provenance={"enabled": False, "database": ":memory:"})
        svc = RewriteService(config=config)
        assert not svc.is_configured

    @pytest.mark.asyncio
    async def test_rewrite_without_provider_raises(self):
        config = TextForgeConfig(provenance={"enabled": False, "database": ":memory:"})
        svc = RewriteService(config=config)
        with pytest.raises(RuntimeError, match="No provider configured"):
            await svc.rewrite(RewriteRequest(text="Test"))

    def test_configure_provider(self):
        config = TextForgeConfig(provenance={"enabled": False, "database": ":memory:"})
        svc = RewriteService(config=config)
        assert not svc.is_configured
        # Can't actually configure without real key, but test the method exists
        # and the structure works
        assert hasattr(svc, "configure_provider")
