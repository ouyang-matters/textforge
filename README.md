# TextForge

Text post-processing middleware with rewrite, validation, provenance logging, and a desktop application.

## Desktop Application

Install the `.deb` package from `release/`, or run from source:

```bash
cd apps/desktop
npm install
npm run tauri dev
```

The desktop app includes:
- **Rewrite** — two-pane editor with strength (Light/Natural/Strong) and style (Natural/Academic/Professional/Concise/Creative) controls, preservation toggles, diff view, and metrics
- **Claude** — multi-turn chat via the official Anthropic API with optional auto-rewrite of responses
- **Compare** — side-by-side text comparison with edit metrics, number/entity preservation scores
- **Settings** — API key configuration with connection testing, privacy controls

API keys are stored in the app's config directory, not in the database. History is opt-in. Raw text logging is disabled by default.

## Architecture

```
Desktop UI (Tauri + React)
    |
    v
Local API (FastAPI on localhost:18157)
    |
    v
Service Layer (textforge/services/)
    |
    +--> RewriteService ------> RewriteEngine --> Provider (Anthropic)
    |                     |---> Validation (semantic, numbers, entities, quality)
    |                     |---> Protected Spans (LaTeX, code, URLs, citations, numbers)
    |                     |---> Provenance Store (SQLite)
    |
    +--> ChatService ---------> Anthropic Messages API
                           |---> Optional auto-rewrite via RewriteService
```

## Installation (Python Backend)

```bash
uv pip install -e ".[dev]"
```

## Environment Variables

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## CLI

```bash
textforge rewrite input.txt --profile academic
cat input.txt | textforge rewrite --profile natural
textforge analyze input.txt
textforge compare original.txt rewritten.txt
textforge serve --host 127.0.0.1 --port 8080
textforge benchmark experiments/example.yaml
```

## API

```bash
# Legacy endpoints
curl -X POST http://localhost:8080/v1/rewrite -H "Content-Type: application/json" \
  -d '{"text": "Input text.", "profile": "academic"}'

# Desktop endpoints
curl -X POST http://localhost:8080/api/rewrite -H "Content-Type: application/json" \
  -d '{"text": "Input text.", "strength": "natural", "style": "academic"}'

curl -X POST http://localhost:8080/api/compare -H "Content-Type: application/json" \
  -d '{"original": "Original.", "rewritten": "Rewritten."}'

curl http://localhost:8080/health
```

## Python API

```python
from textforge.services.rewrite import RewriteService, RewriteRequest, Strength, Style

svc = RewriteService.from_config()
await svc.init()
result = await svc.rewrite(RewriteRequest(
    text="Your text here.",
    strength=Strength.NATURAL,
    style=Style.ACADEMIC,
))
print(result.artifact.text)
```

## Configuration

See `textforge/config.py`. Key settings:
- `validation.semantic_threshold`: minimum semantic similarity (default 0.94)
- `validation.enforce_numbers`: verify number preservation (default true)
- `provenance.enabled`: store artifacts in SQLite (default true)

## Tests

```bash
pytest tests/ -v          # 103 tests, no API key required
ruff check textforge/     # lint
```

## Build

```bash
# Frontend
cd apps/desktop && npm install && npm run build

# Tauri desktop app
npm run tauri build

# Artifacts in apps/desktop/src-tauri/target/release/bundle/
```

## Privacy

- API keys stored in app config directory (not SQLite)
- Raw text logging disabled by default
- History is opt-in
- Text sent only to the configured Anthropic API endpoint

## Supported Platforms

- Linux x86_64 (primary, .deb and .rpm packages)
- macOS and Windows possible with appropriate Tauri toolchain
