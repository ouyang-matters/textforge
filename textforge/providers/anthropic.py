"""Anthropic provider implementation."""

from __future__ import annotations

import anthropic

from textforge.models import ProviderResponse


class AnthropicProvider:
    """TextProvider and RewriteProvider implementation for Anthropic."""

    provider_name: str = "anthropic"

    def __init__(self, api_key: str, default_model: str = "claude-sonnet-4-20250514"):
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._default_model = default_model

    async def generate(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ProviderResponse:
        kwargs: dict = {
            "model": model or self._default_model,
            "messages": messages,
            "max_tokens": max_tokens or 4096,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature

        response = await self._client.messages.create(**kwargs)

        text = ""
        for block in response.content:
            if block.type == "text":
                text += block.text

        return ProviderResponse(
            text=text,
            model=response.model,
            provider="anthropic",
            metadata={
                "stop_reason": response.stop_reason or "",
                "id": response.id,
            },
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
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
        messages = [{"role": "user", "content": text}]
        kwargs: dict = {
            "model": model or self._default_model,
            "system": system_prompt,
            "messages": messages,
            "max_tokens": max_tokens or 4096,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature

        response = await self._client.messages.create(**kwargs)

        text_out = ""
        for block in response.content:
            if block.type == "text":
                text_out += block.text

        return ProviderResponse(
            text=text_out,
            model=response.model,
            provider="anthropic",
            metadata={
                "stop_reason": response.stop_reason or "",
                "id": response.id,
            },
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        )

    async def structured_output(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ProviderResponse:
        return await self.generate(
            messages, model=model, temperature=temperature, max_tokens=max_tokens
        )
