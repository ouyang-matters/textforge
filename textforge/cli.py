"""CLI for TextForge."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import click

from textforge.config import TextForgeConfig


def _run_async(coro):
    return asyncio.run(coro)


@click.group()
def main():
    """TextForge: text post-processing middleware."""
    pass


@main.command()
@click.argument("input_file", required=False, type=click.Path(exists=True))
@click.option("--profile", "-p", default="academic", help="Rewrite profile")
@click.option("--source-provider", default=None, help="Source provider name")
@click.option("--source-model", default=None, help="Source model name")
def rewrite(
    input_file: str | None, profile: str,
    source_provider: str | None, source_model: str | None,
):
    """Rewrite text from file or stdin."""
    if input_file:
        text = Path(input_file).read_text()
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        click.echo("Error: provide input file or pipe text via stdin", err=True)
        sys.exit(1)

    async def _do():
        from textforge.pipeline import TextForge

        config = TextForgeConfig()
        forge = TextForge.from_config(config)
        await forge.init()
        try:
            artifact = await forge.rewrite(
                text,
                profile=profile,
                source_provider=source_provider,
                source_model=source_model,
            )
            # Output rewritten text to stdout
            click.echo(artifact.text)
            # Diagnostics to stderr
            click.echo(
                json.dumps(artifact.metrics, indent=2, default=str),
                err=True,
            )
        finally:
            await forge.close()

    _run_async(_do())


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
def analyze(input_file: str):
    """Analyze text for numbers, entities, and quality."""
    text = Path(input_file).read_text()

    from textforge.validation.entities import extract_entities
    from textforge.validation.numbers import extract_numbers
    from textforge.validation.quality import check_quality

    numbers = extract_numbers(text)
    entities = sorted(extract_entities(text))
    quality = check_quality(text)

    result = {
        "numbers": numbers,
        "entities": entities,
        "quality": {"passed": quality.passed, "issues": quality.issues},
    }
    click.echo(json.dumps(result, indent=2))


@main.command()
@click.argument("original_file", type=click.Path(exists=True))
@click.argument("rewritten_file", type=click.Path(exists=True))
def compare(original_file: str, rewritten_file: str):
    """Compare original and rewritten texts."""
    original = Path(original_file).read_text()
    rewritten = Path(rewritten_file).read_text()

    from textforge.rewrite.engine import compute_edit_metrics
    from textforge.validation.entities import compare_entities
    from textforge.validation.numbers import extract_numbers, validate_numbers
    from textforge.validation.quality import check_quality

    metrics = compute_edit_metrics(original, rewritten)
    quality = check_quality(rewritten)
    num_result = validate_numbers(extract_numbers(original), extract_numbers(rewritten))
    ent_result = compare_entities(original, rewritten)

    result = {
        "metrics": metrics.model_dump(),
        "quality": {"passed": quality.passed, "issues": quality.issues},
        "number_preservation": {
            "passed": num_result.passed,
            "missing": num_result.missing,
            "added": num_result.added,
        },
        "entity_preservation": {
            "score": ent_result.score,
            "missing": ent_result.missing,
            "added": ent_result.added,
        },
    }
    click.echo(json.dumps(result, indent=2, default=str))


@main.command()
@click.option("--host", default="127.0.0.1", help="Host to bind")
@click.option("--port", default=8080, help="Port to bind")
def serve(host: str, port: int):
    """Start the TextForge API server."""
    import uvicorn

    from textforge.api import app

    uvicorn.run(app, host=host, port=port)


@main.command(name="benchmark")
@click.argument("config_file", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Output file (JSON)")
@click.option("--csv-output", default=None, help="Output CSV file")
def benchmark_cmd(config_file: str, output: str | None, csv_output: str | None):
    """Run watermark benchmark from YAML config."""

    async def _do():
        from textforge.pipeline import TextForge
        from textforge.watermark.benchmark import BenchmarkConfig, BenchmarkRunner

        config = TextForgeConfig()
        forge = TextForge.from_config(config)
        await forge.init()

        try:
            bench_config = BenchmarkConfig.from_yaml(config_file)
            runner = BenchmarkRunner(
                engine=forge._engine,  # type: ignore[arg-type]
                store=forge._store,
            )
            result = await runner.run(bench_config)

            if output:
                Path(output).write_text(result.to_json())
                click.echo(f"JSON output written to {output}", err=True)
            if csv_output:
                Path(csv_output).write_text(result.to_csv())
                click.echo(f"CSV output written to {csv_output}", err=True)

            click.echo(json.dumps(result.aggregated, indent=2, default=str))
        finally:
            await forge.close()

    _run_async(_do())


@main.command(name="artifact")
@click.argument("artifact_id")
def artifact_cmd(artifact_id: str):
    """Retrieve an artifact by ID."""

    async def _do():
        from textforge.pipeline import TextForge

        config = TextForgeConfig()
        forge = TextForge.from_config(config)
        await forge.init()
        try:
            data = await forge.get_artifact(artifact_id)
            if data is None:
                click.echo("Artifact not found", err=True)
                sys.exit(1)
            click.echo(json.dumps(data, indent=2, default=str))
        finally:
            await forge.close()

    _run_async(_do())


if __name__ == "__main__":
    main()
