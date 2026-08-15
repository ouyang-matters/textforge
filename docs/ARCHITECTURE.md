# TextForge Architecture

## System Overview

TextForge is a text post-processing middleware that sits between an LLM provider and the end user. It rewrites, validates, logs provenance, and benchmarks watermark robustness for generated text.

```
                                   +------------------+
                                   |  Anthropic API   |
                                   +--------+---------+
                                            |
                               ProviderResponse (raw text)
                                            |
                                            v
+-------+     +-----------+     +------------------------+     +----------+
| stdin |---->|           |     |     Rewrite Pipeline    |     |          |
| file  |---->|  Ingest   |---->|  normalize              |---->|  Output  |---->  stdout
| API   |---->|           |     |  extract protected spans|     |  Artifact|---->  API JSON
+-------+     +-----------+     |  structural analysis    |     +-----+----+---->  DB
                                |  candidate generation   |           |
                                |  restore spans          |           v
                                |  validation + retry     |     +-----------+
                                |  provenance record      |     | Provenance|
                                +------------------------+     |  Store    |
                                                                +-----------+
```

## Module Dependency Graph

```
textforge/
  __init__.py          <-- re-exports TextForge, TextArtifact
  config.py            <-- standalone, no internal deps
  models.py            <-- standalone, Pydantic models only

  providers/
    base.py            <-- Protocol definitions (no deps)
    anthropic.py       <-- depends on: models, anthropic SDK

  rewrite/
    prompts.py         <-- standalone string templates
    protected_spans.py <-- depends on: models
    planner.py         <-- depends on: models, providers/base, prompts
    transforms.py      <-- depends on: models, providers/base, provenance/hashing
    engine.py          <-- depends on: config, models, providers/base, planner,
                           prompts, protected_spans, validation/*, provenance/hashing

  validation/
    semantic.py        <-- depends on: models, providers/base, rewrite/prompts
    claims.py          <-- depends on: models, providers/base, rewrite/prompts
    entities.py        <-- depends on: models (deterministic, no LLM)
    numbers.py         <-- depends on: models (deterministic, no LLM)
    quality.py         <-- depends on: models (deterministic, no LLM)

  provenance/
    hashing.py         <-- standalone (hashlib only)
    models.py          <-- depends on: SQLAlchemy
    store.py           <-- depends on: models, provenance/models

  watermark/
    base.py            <-- Protocol definition (no deps)
    synthid_adapter.py <-- depends on: models, optional synthid-text
    metrics.py         <-- standalone (statistics only)
    benchmark.py       <-- depends on: config, models, provenance/store,
                           rewrite/engine, watermark/base, watermark/metrics

  pipeline.py          <-- top-level API, depends on most modules
  api.py               <-- FastAPI app, depends on: pipeline, config, validation/*
  cli.py               <-- Click CLI, depends on: pipeline, config, validation/*
```

## Core Data Flow

### Rewrite Pipeline

```
1. INGEST
   Raw text string (from file, stdin, API, or provider)

2. NORMALIZE
   Unicode NFC, line ending normalization, trailing whitespace cleanup

3. EXTRACT PROTECTED SPANS
   Regex-based extraction of content that must survive rewriting verbatim:
   - Display/inline LaTeX ($...$, $$...$$, \[...\], \(...\))
   - Code blocks (```...```) and inline code (`...`)
   - URLs, DOIs
   - Citations ([12], [Smith, 2024], (Author et al., 2024))
   - Numbers (integers, decimals, scientific notation, percentages)
   - Equation labels (\ref{}, \eqref{})
   - Quoted text ("...")
   - Math identifiers (x_i, A_{ij})

   Each span is replaced with a stable placeholder: <TF_PROTECTED_0001>

4. STRUCTURAL ANALYSIS
   Classify each paragraph as: definition, argument, example, transition,
   enumeration, technical_explanation, quotation, code_related, or other.
   Deterministic heuristic classifier with optional LLM fallback.

5. CANDIDATE GENERATION
   Send protected text + system prompt to rewrite provider.
   Profile-specific instructions control edit ratio, sentence operations,
   paragraph structure, register, and terminology preservation.

6. RESTORE PROTECTED SPANS
   Replace all <TF_PROTECTED_XXXX> placeholders with original content.

7. VALIDATION
   - Quality checks: placeholder leakage, LaTeX balance, code block balance,
     duplicate sentences, truncation detection
   - Number preservation: multiset equality of extracted numbers
   - Semantic validation (if provider configured): LLM-based comparison
   - Entity preservation: deterministic comparison of proper nouns, abbreviations

8. RETRY (on validation failure)
   Re-send with validation feedback. Capped by profile max_retries.

9. PROVENANCE RECORD
   SHA-256 hashes of source and output, transformation log, validation results.
   Persisted to SQLite via async SQLAlchemy.

10. FINAL ARTIFACT
    TextArtifact with text, original_text, hashes, spans, transformations, metrics.
```

### Watermark Benchmark (post-hoc only)

```
Original watermarked text
  --> Detector.detect() --> score_before
  --> RewriteEngine.rewrite() --> rewritten text
  --> Detector.detect() --> score_after
  --> Aggregate metrics across dimensions

Dimensions: text length, language, domain, rewrite profile
Output: per-sample CSV/JSON + aggregated statistics with confidence intervals
```

Watermark scores are **never** fed back into the rewrite planner, candidate
selection, retry logic, or profile adjustment. Evaluation is strictly post-hoc.

## Rewrite Profiles

| Profile      | max_edit | split | merge | reorder | para_count | register | tech_terms | retries |
|-------------|----------|-------|-------|---------|------------|----------|------------|---------|
| minimal     | 0.15     | no    | no    | no      | yes        | yes      | yes        | 1       |
| natural     | 0.35     | yes   | yes   | no      | yes        | yes      | yes        | 2       |
| academic    | 0.30     | yes   | no    | no      | yes        | yes      | yes        | 2       |
| professional| 0.35     | yes   | yes   | no      | yes        | yes      | yes        | 2       |
| concise     | 0.50     | no    | yes   | no      | no         | yes      | yes        | 2       |
| creative    | 0.60     | yes   | yes   | yes     | no         | no       | no         | 3       |

## Provider Abstraction

Two separate protocols:

- **TextProvider**: generic LLM generation (`generate(messages, model, ...)`)
- **RewriteProvider**: rewrite-specific (`rewrite(text, system_prompt, ...)` + `structured_output(...)`)

This separation ensures the rewrite engine can use a different provider/model
than the one that originally generated the text.

## Persistence Schema

```sql
artifacts           -- source/output text, hashes, provider info, metrics
transformations     -- per-transformation log (name, hashes, provider, params)
validation_results  -- per-validator results (score, passed, details)
watermark_results   -- detector scores (linked to artifact or benchmark run)
benchmark_runs      -- experiment metadata and status
benchmark_samples   -- per-sample metrics for benchmark dimensions
```

Schema is auto-created on first use (no migration tool required for MVP).

## API Endpoints

| Method | Path                        | Purpose                              |
|--------|-----------------------------|--------------------------------------|
| POST   | `/v1/rewrite`               | Rewrite text with profile            |
| POST   | `/v1/analyze`               | Extract numbers, entities, quality   |
| POST   | `/v1/compare`               | Compare original vs rewritten        |
| POST   | `/v1/benchmark`             | Run watermark benchmark              |
| GET    | `/v1/artifacts/{id}`        | Retrieve stored artifact             |
| GET    | `/v1/benchmark/{run_id}`    | Retrieve benchmark results           |
| POST   | `/v1/proxy/messages`        | Anthropic-compatible proxy           |
| GET    | `/health`                   | Health check                         |

## Security Considerations

- API keys read from environment only, never logged
- Raw text logging disabled by default (`TEXTFORGE_LOG_RAW_TEXT=false`)
- Authorization headers never logged by structlog configuration
- SQLite database stored locally; no remote persistence by default
