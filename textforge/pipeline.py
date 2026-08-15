"""Top-level TextForge API and wrapped provider client."""

from __future__ import annotations

from typing import Any

from textforge.config import RewriteProfile, TextForgeConfig
from textforge.models import ProviderResponse, TextArtifact
from textforge.provenance.store import ProvenanceStore
from textforge.providers.anthropic import AnthropicProvider
from textforge.providers.base import RewriteProvider
from textforge.rewrite.engine import RewriteEngine
from textforge.validation.semantic import SemanticValidator


class TextForge:
    """Main entry point for the TextForge library."""

    def __init__(
        self,
        config: TextForgeConfig,
        rewrite_provider: RewriteProvider | None = None,
        store: ProvenanceStore | None = None,
    ):
        self.config = config
        self._store = store

        if rewrite_provider:
            self._rewrite_provider = rewrite_provider
        elif config.anthropic_api_key:
            self._rewrite_provider = AnthropicProvider(
                api_key=config.anthropic_api_key,
                default_model=config.default_rewrite_model,
            )
        else:
            self._rewrite_provider = None  # type: ignore[assignment]

        semantic_validator = None
        if self._rewrite_provider:
            semantic_validator = SemanticValidator(
                provider=self._rewrite_provider,
                threshold=config.validation.semantic_threshold,
            )

        self._engine: RewriteEngine | None = None
        if self._rewrite_provider:
            self._engine = RewriteEngine(
                provider=self._rewrite_provider,
                config=config,
                semantic_validator=semantic_validator,
            )

    @classmethod
    def from_config(cls, config: TextForgeConfig | None = None) -> TextForge:
        if config is None:
            config = TextForgeConfig()
        store = None
        if config.provenance.enabled:
            store = ProvenanceStore(config.database_url)
        return cls(config=config, store=store)

    async def init(self) -> None:
        """Initialize database."""
        if self._store:
            await self._store.init_db()

    async def close(self) -> None:
        if self._store:
            await self._store.close()

    async def rewrite(
        self,
        text: str,
        *,
        profile: str | RewriteProfile = "academic",
        source_provider: str | None = None,
        source_model: str | None = None,
        preserve: dict[str, bool] | None = None,
    ) -> TextArtifact:
        if self._engine is None:
            raise RuntimeError("No rewrite provider configured. Set ANTHROPIC_API_KEY.")

        if isinstance(profile, str):
            profile = RewriteProfile(profile)

        artifact = await self._engine.rewrite(
            text,
            profile=profile,
            source_provider=source_provider,
            source_model=source_model,
            preserve=preserve,
        )

        if self._store:
            await self._store.save_artifact(
                artifact,
                rewrite_provider=(
                    self._rewrite_provider.provider_name
                    if self._rewrite_provider else None
                ),
                rewrite_model=self.config.rewrite.model or self.config.default_rewrite_model,
            )

        return artifact

    async def get_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        if self._store is None:
            return None
        return await self._store.get_artifact(artifact_id)


class TextForgeAnthropicClient:
    """Wrapped Anthropic provider that optionally applies TextForge rewriting."""

    def __init__(
        self,
        anthropic_client: AnthropicProvider,
        forge: TextForge,
        default_profile: str = "natural",
    ):
        self._client = anthropic_client
        self._forge = forge
        self._default_profile = default_profile

    async def generate(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        rewrite_profile: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ProviderResponse:
        response = await self._client.generate(
            messages,
            model=model or self._client._default_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if rewrite_profile is not None:
            artifact = await self._forge.rewrite(
                response.text,
                profile=rewrite_profile,
                source_provider="anthropic",
                source_model=response.model,
            )
            response = ProviderResponse(
                text=artifact.text,
                model=response.model,
                provider=response.provider,
                metadata={
                    **response.metadata,
                    "textforge_artifact_id": str(artifact.id),
                },
                usage=response.usage,
            )

        return response
