"""Shared test fixtures."""

from __future__ import annotations

import pytest

from textforge.config import TextForgeConfig
from textforge.models import ProviderResponse


class MockRewriteProvider:
    """Mock provider for testing without API keys."""

    provider_name = "mock"

    def __init__(self, response_text: str = ""):
        self._response_text = response_text

    async def generate(
        self,
        messages: list[dict],
        *,
        model: str = "mock-model",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ProviderResponse:
        return ProviderResponse(
            text=self._response_text,
            model="mock-model",
            provider="mock",
        )

    async def rewrite(
        self,
        text: str,
        system_prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ProviderResponse:
        return ProviderResponse(
            text=self._response_text or text,
            model="mock-model",
            provider="mock",
        )

    async def structured_output(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ProviderResponse:
        return ProviderResponse(
            text=self._response_text,
            model="mock-model",
            provider="mock",
        )


@pytest.fixture
def mock_provider():
    return MockRewriteProvider()


@pytest.fixture
def config():
    return TextForgeConfig(
        anthropic_api_key="test-key",
        database_url="sqlite+aiosqlite:///",
        provenance={"enabled": False, "database": ":memory:"},
    )
