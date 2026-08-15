"""SynthID-Text reference adapter.

Optional dependency: install with `pip install "textforge[synthid]"`.
Falls back gracefully when synthid-text is not installed.
"""

from __future__ import annotations

from textforge.models import WatermarkResult


class SynthIDReferenceAdapter:
    """Adapter around SynthID-Text reference implementation."""

    name: str = "synthid_reference"

    def __init__(self) -> None:
        self._available = False
        try:
            import synthid_text  # noqa: F401

            self._available = True
        except ImportError:
            pass

    @property
    def available(self) -> bool:
        return self._available

    def detect(self, text: str) -> WatermarkResult:
        if not self._available:
            return WatermarkResult(
                detector=self.name,
                score=None,
                confidence=None,
                detected=None,
                metadata={"error": "synthid-text not installed"},
            )

        try:
            # Reference implementation interface may vary;
            # this adapter isolates the rest of the project from API changes.
            import synthid_text

            # The actual API depends on the synthid-text version.
            # This is a best-effort adapter.
            detector = synthid_text.SynthIDDetector()
            result = detector.detect(text)
            return WatermarkResult(
                detector=self.name,
                score=getattr(result, "score", None),
                confidence=getattr(result, "confidence", None),
                detected=getattr(result, "detected", None),
                metadata={"raw": str(result)},
            )
        except Exception as e:
            return WatermarkResult(
                detector=self.name,
                score=None,
                confidence=None,
                detected=None,
                metadata={"error": str(e)},
            )
