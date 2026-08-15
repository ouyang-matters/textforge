# TextForge

Text post-processing middleware with rewrite, validation, provenance logging, and watermark robustness benchmarking.

## Installation

```bash
# With uv
uv pip install -e ".[dev]"

# With pip
pip install -e ".[dev]"

# With SynthID support (optional)
pip install -e ".[synthid]"
```

## Environment Variables

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export TEXTFORGE_DATABASE_URL=sqlite+aiosqlite:///./textforge.db
export TEXTFORGE_LOG_LEVEL=INFO
export TEXTFORGE_LOG_RAW_TEXT=false
```

Copy `.env.example` and fill in values.

## CLI Examples

```bash
# Rewrite from file
textforge rewrite input.txt --profile academic

# Rewrite from stdin
cat input.txt | textforge rewrite --profile natural

# Analyze text
textforge analyze input.txt

# Compare original and rewritten
textforge compare original.txt rewritten.txt

# Retrieve stored artifact
textforge artifact ARTIFACT_ID
```

## API Server

```bash
textforge serve --host 127.0.0.1 --port 8080
```

### API Examples

```bash
# Rewrite
curl -X POST http://localhost:8080/v1/rewrite \
  -H "Content-Type: application/json" \
  -d '{"text": "Input text here.", "profile": "academic"}'

# Analyze
curl -X POST http://localhost:8080/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "Text to analyze."}'

# Compare
curl -X POST http://localhost:8080/v1/compare \
  -H "Content-Type: application/json" \
  -d '{"original": "Original text.", "rewritten": "Rewritten text."}'

# Health check
curl http://localhost:8080/health
```

### Proxy Mode

Forward Anthropic API requests through TextForge with optional rewriting:

```bash
curl -X POST http://localhost:8080/v1/proxy/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 1024,
    "rewrite_profile": "natural"
  }'
```

## Python API

```python
from textforge import TextForge

forge = TextForge.from_config()
await forge.init()

result = await forge.rewrite(
    text,
    profile="academic",
    source_provider="anthropic",
    source_model="claude-sonnet-4-20250514",
)
print(result.text)

# Wrapped provider
from textforge.pipeline import TextForgeAnthropicClient
from textforge.providers.anthropic import AnthropicProvider

provider = AnthropicProvider(api_key="sk-ant-...")
client = TextForgeAnthropicClient(anthropic_client=provider, forge=forge)

response = await client.generate(
    messages=[{"role": "user", "content": "Hello"}],
    model="claude-sonnet-4-20250514",
    rewrite_profile="natural",
)
```

## Configuration

Configuration via environment variables (prefix `TEXTFORGE_`) or YAML file. See `textforge/config.py` for all options.

Key settings:
- `rewrite.profile`: minimal, natural, academic, professional, concise, creative
- `validation.semantic_threshold`: minimum semantic similarity (default 0.94)
- `validation.enforce_numbers`: verify number preservation (default true)
- `provenance.enabled`: store artifacts in SQLite (default true)
- `watermark.enabled`: enable watermark detection (default false)

## Running Tests

```bash
# All tests (no API key required)
pytest tests/ -v

# With coverage
pytest tests/ --cov=textforge

# Integration tests (requires ANTHROPIC_API_KEY)
pytest tests/ -v -m integration
```

## Benchmark

```bash
textforge benchmark experiments/example.yaml
textforge benchmark experiments/example.yaml -o results.json --csv-output results.csv
```