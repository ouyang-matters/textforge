"""Watermark detector protocol and base types."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from textforge.models import WatermarkResult


@runtime_checkable
class WatermarkDetector(Protocol):
    name: str

    def detect(self, text: str) -> WatermarkResult: ...
