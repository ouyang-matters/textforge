#!/bin/bash
# Build script that runs INSIDE the pywine Docker container.
# It installs dependencies and runs PyInstaller to create a Windows exe.

set -e

cd /src

echo "=== Installing Python dependencies ==="
wine pip install --no-warn-script-location \
    fastapi==0.115.12 \
    uvicorn==0.34.3 \
    pydantic==2.11.7 \
    pydantic-settings==2.9.1 \
    httpx==0.28.1 \
    anthropic==0.52.0 \
    sqlalchemy==2.0.41 \
    aiosqlite==0.21.0 \
    pyyaml==6.0.2 \
    python-dotenv==1.1.0 \
    structlog==25.4.0 \
    python-Levenshtein==0.27.1 \
    click==8.2.1 \
    h11==0.16.0 \
    anyio==4.9.0 \
    sniffio==1.3.1 \
    httpcore==1.0.9 \
    certifi \
    idna \
    python-multipart \
    pyinstaller==6.13.0 \
    2>&1 | tail -5

echo "=== Copying spec to writable location ==="
cp /src/packaging/windows/pyinstaller.spec /output/textforge.spec

echo "=== Running PyInstaller ==="
cd /output
wine pyinstaller \
    --noconfirm \
    --clean \
    --distpath /output/dist \
    --workpath /output/build \
    /output/textforge.spec \
    2>&1

echo "=== Build complete ==="
ls -la /output/dist/TextForge/
