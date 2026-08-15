"""Chat service — Claude conversation through official Anthropic API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import anthropic

from textforge.services.rewrite import RewriteRequest, RewriteService, Strength, Style


@dataclass
class ChatMessage:
    role: str  # "user" or "assistant"
    content: str
    rewritten_content: str | None = None
    artifact_id: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatConfig:
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float | None = None
    system_prompt: str | None = None
    auto_rewrite: bool = False
    rewrite_strength: Strength = Strength.NATURAL
    rewrite_style: Style = Style.NATURAL
    display_mode: str = "both"  # "rewritten_only", "both", "original_only"


class ChatService:
    """Multi-turn chat via official Anthropic Messages API with optional rewrite."""

    def __init__(
        self,
        rewrite_service: RewriteService,
    ):
        self._rewrite = rewrite_service
        self._client: anthropic.AsyncAnthropic | None = None

    def configure(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    @property
    def is_configured(self) -> bool:
        return self._client is not None

    async def test_connection(self, api_key: str) -> dict[str, Any]:
        """Test API key validity."""
        try:
            client = anthropic.AsyncAnthropic(api_key=api_key)
            response = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return {"ok": True, "model": response.model}
        except anthropic.AuthenticationError:
            return {"ok": False, "error": "Invalid API key"}
        except anthropic.RateLimitError:
            return {"ok": False, "error": "Rate limited — key is valid but busy"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def send_message(
        self,
        messages: list[dict[str, str]],
        config: ChatConfig,
    ) -> ChatMessage:
        """Send a message and get a complete response (non-streaming)."""
        if not self._client:
            raise RuntimeError("Chat not configured. Set API key first.")

        kwargs: dict[str, Any] = {
            "model": config.model,
            "max_tokens": config.max_tokens,
            "messages": messages,
        }
        if config.temperature is not None:
            kwargs["temperature"] = config.temperature
        if config.system_prompt:
            kwargs["system"] = config.system_prompt

        response = await self._client.messages.create(**kwargs)

        text = ""
        for block in response.content:
            if block.type == "text":
                text += block.text

        result = ChatMessage(role="assistant", content=text)

        # Auto-rewrite if enabled
        if config.auto_rewrite and self._rewrite.is_configured:
            try:
                rr = await self._rewrite.rewrite(RewriteRequest(
                    text=text,
                    strength=config.rewrite_strength,
                    style=config.rewrite_style,
                    source_provider="anthropic",
                    source_model=response.model,
                ))
                result.rewritten_content = rr.artifact.text
                result.artifact_id = str(rr.artifact.id)
                result.metrics = rr.artifact.metrics
            except Exception:
                # Never destroy the original on rewrite failure
                result.rewritten_content = None

        return result

    async def stream_message(
        self,
        messages: list[dict[str, str]],
        config: ChatConfig,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream a response, then optionally rewrite the completed answer."""
        if not self._client:
            raise RuntimeError("Chat not configured. Set API key first.")

        kwargs: dict[str, Any] = {
            "model": config.model,
            "max_tokens": config.max_tokens,
            "messages": messages,
        }
        if config.temperature is not None:
            kwargs["temperature"] = config.temperature
        if config.system_prompt:
            kwargs["system"] = config.system_prompt

        full_text = ""
        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                full_text += text
                yield {"type": "text_delta", "text": text}

        yield {"type": "message_complete", "text": full_text}

        # Rewrite the completed answer if enabled
        if config.auto_rewrite and self._rewrite.is_configured:
            yield {"type": "rewrite_start"}
            try:
                rr = await self._rewrite.rewrite(RewriteRequest(
                    text=full_text,
                    strength=config.rewrite_strength,
                    style=config.rewrite_style,
                    source_provider="anthropic",
                    source_model=config.model,
                ))
                yield {
                    "type": "rewrite_complete",
                    "text": rr.artifact.text,
                    "artifact_id": str(rr.artifact.id),
                    "metrics": rr.artifact.metrics,
                }
            except Exception as e:
                yield {"type": "rewrite_error", "error": str(e)}
