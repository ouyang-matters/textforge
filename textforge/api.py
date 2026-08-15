"""FastAPI application — serves both legacy API and desktop client."""

from __future__ import annotations

import json
import os
import sys
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from textforge.config import TextForgeConfig
from textforge.services.chat import ChatConfig, ChatService
from textforge.services.rewrite import RewriteRequest as SvcRewriteRequest
from textforge.services.rewrite import (
    RewriteService,
    Strength,
    Style,
)
from textforge.validation.entities import extract_entities
from textforge.validation.numbers import extract_numbers
from textforge.validation.quality import check_quality

# ---------- Request / Response models (backward-compatible) ----------


class PreserveOptions(BaseModel):
    math: bool = True
    numbers: bool = True
    citations: bool = True
    code: bool = True
    urls: bool = True


class RewriteRequest(BaseModel):
    text: str
    profile: str = "academic"
    source_provider: str | None = None
    source_model: str | None = None
    preserve: PreserveOptions = Field(default_factory=PreserveOptions)


class RewriteResponse(BaseModel):
    artifact_id: str
    text: str
    original_text: str = ""
    metrics: dict[str, Any] = {}
    validation: dict[str, Any] = {}


class DesktopRewriteRequest(BaseModel):
    text: str
    strength: str = "natural"
    style: str = "natural"
    preserve_meaning: bool = True
    preserve_numbers: bool = True
    preserve_formulas: bool = True
    preserve_citations: bool = True
    preserve_names: bool = True
    preserve_technical: bool = True
    locked_spans: list[dict[str, int]] | None = None


class AnalyzeRequest(BaseModel):
    text: str


class AnalyzeResponse(BaseModel):
    metrics: dict[str, Any] = {}
    quality: dict[str, Any] = {}
    numbers: list[str] = []
    entities: list[str] = []


class CompareRequest(BaseModel):
    original: str
    rewritten: str


class CompareResponse(BaseModel):
    metrics: dict[str, Any] = {}
    quality: dict[str, Any] = {}
    number_preservation: dict[str, Any] = {}
    entity_preservation: dict[str, Any] = {}


class ChatRequest(BaseModel):
    messages: list[dict[str, str]]
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float | None = None
    system_prompt: str | None = None
    auto_rewrite: bool = False
    rewrite_strength: str = "natural"
    rewrite_style: str = "natural"
    display_mode: str = "both"
    stream: bool = False


class ProviderConfigRequest(BaseModel):
    api_key: str
    model: str | None = None


class BenchmarkRequest(BaseModel):
    config_path: str | None = None
    config: dict[str, Any] | None = None
    texts: list[str] | None = None


class BenchmarkResponse(BaseModel):
    run_id: str
    samples_count: int
    aggregated: dict[str, Any] = {}


class ProxyRequest(BaseModel):
    model: str
    messages: list[dict[str, Any]]
    max_tokens: int = 4096
    temperature: float | None = None
    system: str | None = None
    rewrite_profile: str | None = None


class ProxyResponse(BaseModel):
    id: str = ""
    type: str = "message"
    role: str = "assistant"
    content: list[dict[str, Any]] = []
    model: str = ""
    usage: dict[str, int] = {}


# ---------- App state ----------

_rewrite_svc: RewriteService | None = None
_chat_svc: ChatService | None = None


def _get_rewrite() -> RewriteService:
    if _rewrite_svc is None:
        raise HTTPException(500, "Service not initialized")
    return _rewrite_svc


def _get_chat() -> ChatService:
    if _chat_svc is None:
        raise HTTPException(500, "Chat service not initialized")
    return _chat_svc


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _rewrite_svc, _chat_svc
    config = TextForgeConfig(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
    )
    _rewrite_svc = RewriteService.from_config(config)
    await _rewrite_svc.init()
    _chat_svc = ChatService(rewrite_service=_rewrite_svc)
    if config.anthropic_api_key:
        _chat_svc.configure(config.anthropic_api_key)
    yield
    await _rewrite_svc.close()


app = FastAPI(title="TextForge", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Health ----------

@app.get("/health")
async def health():
    svc = _get_rewrite()
    return {
        "status": "ok",
        "provider_configured": svc.is_configured,
        "chat_configured": _chat_svc.is_configured if _chat_svc else False,
    }


# ---------- Legacy /v1 endpoints (backward-compatible) ----------

@app.post("/v1/rewrite", response_model=RewriteResponse)
async def rewrite_v1(req: RewriteRequest):
    svc = _get_rewrite()
    try:
        result = await svc.rewrite(SvcRewriteRequest(
            text=req.text,
            source_provider=req.source_provider,
            source_model=req.source_model,
        ))
    except RuntimeError as e:
        raise HTTPException(500, str(e)) from e

    return RewriteResponse(
        artifact_id=str(result.artifact.id),
        text=result.artifact.text,
        original_text=result.artifact.original_text,
        metrics=result.artifact.metrics,
        validation={
            "passed": result.validation_passed,
            "issues": result.validation_issues,
        },
    )


@app.post("/v1/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    numbers = extract_numbers(req.text)
    entities = sorted(extract_entities(req.text))
    quality = check_quality(req.text)

    return AnalyzeResponse(
        metrics={"length": len(req.text), "word_count": len(req.text.split())},
        quality={"passed": quality.passed, "issues": quality.issues},
        numbers=numbers,
        entities=entities,
    )


@app.post("/v1/compare", response_model=CompareResponse)
async def compare(req: CompareRequest):
    svc = _get_rewrite()
    result = svc.compare(req.original, req.rewritten)
    return CompareResponse(
        metrics=result.metrics,
        quality=result.quality,
        number_preservation=result.number_preservation,
        entity_preservation=result.entity_preservation,
    )


@app.get("/v1/artifacts/{artifact_id}")
async def get_artifact(artifact_id: str):
    svc = _get_rewrite()
    data = await svc.get_artifact(artifact_id)
    if data is None:
        raise HTTPException(404, "Artifact not found")
    return data


@app.post("/v1/benchmark", response_model=BenchmarkResponse)
async def benchmark(req: BenchmarkRequest):
    raise HTTPException(501, "Benchmark via API coming soon")


@app.get("/v1/benchmark/{run_id}")
async def get_benchmark(run_id: str):
    raise HTTPException(501, "Benchmark via API coming soon")


@app.post("/v1/proxy/messages", response_model=ProxyResponse)
async def proxy_messages(req: ProxyRequest):
    svc = _get_rewrite()
    if not svc.is_configured:
        raise HTTPException(500, "No provider configured")

    from textforge.providers.anthropic import AnthropicProvider

    if not isinstance(svc._provider, AnthropicProvider):
        raise HTTPException(500, "Proxy mode requires Anthropic provider")

    response = await svc._provider.generate(
        req.messages,
        model=req.model,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
    )
    text = response.text

    if req.rewrite_profile and not _looks_like_structured(text):
        result = await svc.rewrite(SvcRewriteRequest(text=text))
        text = result.artifact.text

    return ProxyResponse(
        id=str(response.metadata.get("id", "")),
        content=[{"type": "text", "text": text}],
        model=response.model,
        usage=response.usage,
    )


# ---------- Desktop endpoints ----------

@app.post("/api/rewrite")
async def desktop_rewrite(req: DesktopRewriteRequest):
    svc = _get_rewrite()
    try:
        strength = Strength(req.strength)
        style = Style(req.style)
    except ValueError:
        strength = Strength.NATURAL
        style = Style.NATURAL

    try:
        result = await svc.rewrite(SvcRewriteRequest(
            text=req.text,
            strength=strength,
            style=style,
            preserve_meaning=req.preserve_meaning,
            preserve_numbers=req.preserve_numbers,
            preserve_formulas=req.preserve_formulas,
            preserve_citations=req.preserve_citations,
            preserve_names=req.preserve_names,
            preserve_technical=req.preserve_technical,
            locked_spans=req.locked_spans,
        ))
    except RuntimeError as e:
        raise HTTPException(500, str(e)) from e

    return {
        "artifact_id": str(result.artifact.id),
        "text": result.artifact.text,
        "original_text": result.artifact.original_text,
        "metrics": result.artifact.metrics,
        "validation": {
            "passed": result.validation_passed,
            "issues": result.validation_issues,
        },
    }


@app.post("/api/compare")
async def desktop_compare(req: CompareRequest):
    svc = _get_rewrite()
    result = svc.compare(req.original, req.rewritten)
    return {
        "metrics": result.metrics,
        "quality": result.quality,
        "number_preservation": result.number_preservation,
        "entity_preservation": result.entity_preservation,
    }


@app.post("/api/chat")
async def desktop_chat(req: ChatRequest):
    chat = _get_chat()

    config = ChatConfig(
        model=req.model,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
        system_prompt=req.system_prompt,
        auto_rewrite=req.auto_rewrite,
        rewrite_strength=Strength(req.rewrite_strength),
        rewrite_style=Style(req.rewrite_style),
        display_mode=req.display_mode,
    )

    if req.stream:
        async def event_stream():
            async for event in chat.stream_message(req.messages, config):
                yield f"data: {json.dumps(event)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
        )

    msg = await chat.send_message(req.messages, config)
    return {
        "role": msg.role,
        "content": msg.content,
        "rewritten_content": msg.rewritten_content,
        "artifact_id": msg.artifact_id,
        "metrics": msg.metrics,
    }


@app.post("/api/provider/configure")
async def configure_provider(req: ProviderConfigRequest):
    svc = _get_rewrite()
    chat = _get_chat()

    svc.configure_provider(req.api_key, req.model)
    chat.configure(req.api_key)

    return {"ok": True, "configured": True}


@app.post("/api/provider/test")
async def test_provider(req: ProviderConfigRequest):
    chat = _get_chat()
    result = await chat.test_connection(req.api_key)
    return result


@app.get("/api/settings")
async def get_settings():
    svc = _get_rewrite()
    return {
        "provider_configured": svc.is_configured,
        "chat_configured": _chat_svc.is_configured if _chat_svc else False,
        "default_model": svc._config.default_rewrite_model,
        "validation": {
            "semantic_threshold": svc._config.validation.semantic_threshold,
            "enforce_numbers": svc._config.validation.enforce_numbers,
            "enforce_entities": svc._config.validation.enforce_entities,
        },
    }


# ---------- Static frontend serving ----------

def _find_static_dir() -> str | None:
    """Locate the built frontend static files."""
    candidates = [
        # Packaged: next to the executable
        os.path.join(os.path.dirname(sys.executable), "frontend"),
        os.path.join(os.path.dirname(sys.executable), "..", "frontend"),
        # PyInstaller _MEIPASS
        os.path.join(getattr(sys, "_MEIPASS", ""), "frontend"),
        # Development: apps/desktop/dist
        os.path.join(os.path.dirname(__file__), "..", "apps", "desktop", "dist"),
    ]
    for c in candidates:
        idx = os.path.join(c, "index.html")
        if os.path.isfile(idx):
            return os.path.abspath(c)
    return None


_static_dir = _find_static_dir()
if _static_dir:
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(_static_dir, "index.html"))

    # Mount assets AFTER all API routes so it doesn't shadow them
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(_static_dir, "assets")),
        name="static-assets",
    )

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA fallback — serve index.html for unmatched routes."""
        file_path = os.path.join(_static_dir, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(_static_dir, "index.html"))


# ---------- Helpers ----------

def _looks_like_structured(text: str) -> bool:
    stripped = text.strip()
    if stripped.startswith(("{", "[")) and stripped.endswith(("}", "]")):
        return True
    if stripped.startswith("```") and stripped.endswith("```"):
        return True
    return False
