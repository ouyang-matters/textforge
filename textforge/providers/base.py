"""Provider protocol and base types."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from textforge.models import ProviderResponse


@runtime_checkable
class TextProvider(Protocol):
    async def generate(
        self,
        messages: list[dict],
        *,
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ProviderResponse: ...


@runtime_checkable
class RewriteProvider(Protocol):
    """Provider abstraction specifically for rewriting text.

    Decoupled from the source provider so rewriting can use a different
    provider/model than the one that originally generated the text.
    """

    provider_name: str

    async def rewrite(
        self,
        text: str,
        system_prompt: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ProviderResponse: ...

    async def structured_output(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ProviderResponse: ...
