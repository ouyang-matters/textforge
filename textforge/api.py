"""FastAPI application."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from textforge.config import TextForgeConfig
from textforge.pipeline import TextForge
from textforge.rewrite.engine import compute_edit_metrics
from textforge.validation.entities import compare_entities
from textforge.validation.numbers import extract_numbers, validate_numbers
from textforge.validation.quality import check_quality

# --- Request/Response Models ---


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
    metrics: dict[str, Any] = {}
    validation: dict[str, Any] = {}


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


class BenchmarkRequest(BaseModel):
    config_path: str | None = None
    config: dict[str, Any] | None = None
    texts: list[str] | None = None


class BenchmarkResponse(BaseModel):
    run_id: str
    samples_count: int
    aggregated: dict[str, Any] = {}


class ProxyRequest(BaseModel):
    """Subset of Anthropic Messages API request."""

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


# --- App ---

_forge: TextForge | None = None


def _get_forge() -> TextForge:
    if _forge is None:
        raise HTTPException(500, "TextForge not initialized")
    return _forge


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _forge
    config = TextForgeConfig(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
    )
    _forge = TextForge.from_config(config)
    await _forge.init()
    yield
    await _forge.close()


app = FastAPI(title="TextForge", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/v1/rewrite", response_model=RewriteResponse)
async def rewrite(req: RewriteRequest):
    forge = _get_forge()
    try:
        artifact = await forge.rewrite(
            req.text,
            profile=req.profile,
            source_provider=req.source_provider,
            source_model=req.source_model,
            preserve=req.preserve.model_dump(),
        )
    except RuntimeError as e:
        raise HTTPException(500, str(e)) from e

    return RewriteResponse(
        artifact_id=str(artifact.id),
        text=artifact.text,
        metrics=artifact.metrics,
        validation={"passed": True},
    )


@app.post("/v1/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    from textforge.validation.entities import extract_entities

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
    metrics = compute_edit_metrics(req.original, req.rewritten)
    quality = check_quality(req.rewritten)
    num_result = validate_numbers(
        extract_numbers(req.original), extract_numbers(req.rewritten)
    )
    ent_result = compare_entities(req.original, req.rewritten)

    return CompareResponse(
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


@app.post("/v1/benchmark", response_model=BenchmarkResponse)
async def benchmark(req: BenchmarkRequest):
    forge = _get_forge()

    from textforge.watermark.benchmark import BenchmarkConfig, BenchmarkRunner

    if req.config_path:
        bench_config = BenchmarkConfig.from_yaml(req.config_path)
    elif req.config:
        bench_config = BenchmarkConfig(req.config)
    else:
        raise HTTPException(400, "Provide config_path or config")

    runner = BenchmarkRunner(
        engine=forge._engine,  # type: ignore[arg-type]
        store=forge._store,
    )
    result = await runner.run(bench_config, texts=req.texts)

    return BenchmarkResponse(
        run_id=result.run_id,
        samples_count=len(result.samples),
        aggregated=result.aggregated,
    )


@app.get("/v1/artifacts/{artifact_id}")
async def get_artifact(artifact_id: str):
    forge = _get_forge()
    data = await forge.get_artifact(artifact_id)
    if data is None:
        raise HTTPException(404, "Artifact not found")
    return data


@app.get("/v1/benchmark/{run_id}")
async def get_benchmark(run_id: str):
    forge = _get_forge()
    if forge._store is None:
        raise HTTPException(500, "Provenance store not configured")
    data = await forge._store.get_benchmark_run(run_id)
    if data is None:
        raise HTTPException(404, "Benchmark run not found")
    return data


@app.post("/v1/proxy/messages", response_model=ProxyResponse)
async def proxy_messages(req: ProxyRequest):
    """Anthropic-compatible proxy that optionally rewrites responses."""
    forge = _get_forge()

    if forge._rewrite_provider is None:
        raise HTTPException(500, "No provider configured")

    # Forward upstream
    from textforge.providers.anthropic import AnthropicProvider

    if not isinstance(forge._rewrite_provider, AnthropicProvider):
        raise HTTPException(500, "Proxy mode requires Anthropic provider")

    messages = req.messages
    kwargs: dict[str, Any] = {
        "model": req.model,
        "max_tokens": req.max_tokens,
    }
    if req.temperature is not None:
        kwargs["temperature"] = req.temperature

    response = await forge._rewrite_provider.generate(messages, **kwargs)

    # Optionally rewrite text content
    text = response.text

    if req.rewrite_profile:
        # Only rewrite plain text, skip tool calls / JSON / code blocks
        if not _looks_like_structured(text):
            artifact = await forge.rewrite(
                text,
                profile=req.rewrite_profile,
                source_provider="anthropic",
                source_model=response.model,
            )
            text = artifact.text

    return ProxyResponse(
        id=str(response.metadata.get("id", "")),
        content=[{"type": "text", "text": text}],
        model=response.model,
        usage=response.usage,
    )


def _looks_like_structured(text: str) -> bool:
    """Heuristic: skip rewriting if content looks like JSON, tool calls, or code."""
    stripped = text.strip()
    if stripped.startswith(("{", "[")) and stripped.endswith(("}", "]")):
        return True
    if stripped.startswith("```") and stripped.endswith("```"):
        return True
    return False
