"""Provenance hashing with SHA-256."""

from __future__ import annotations

import hashlib


def sha256_hash(text: str) -> str:
    """Compute SHA-256 hash of text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
