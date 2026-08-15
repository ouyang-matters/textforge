"""Tests for API request validation and endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from textforge.api import AnalyzeRequest, CompareRequest, RewriteRequest, app


class TestRequestValidation:
    def test_rewrite_request_defaults(self):
        req = RewriteRequest(text="Hello")
        assert req.profile == "academic"
        assert req.preserve.math is True
        assert req.preserve.numbers is True

    def test_rewrite_request_custom(self):
        req = RewriteRequest(
            text="Hello",
            profile="minimal",
            source_provider="anthropic",
            source_model="claude-3",
            preserve={"math": False, "numbers": True, "citations": True,
                       "code": True, "urls": True},
        )
        assert req.profile == "minimal"
        assert req.preserve.math is False

    def test_analyze_request(self):
        req = AnalyzeRequest(text="Some text")
        assert req.text == "Some text"

    def test_compare_request(self):
        req = CompareRequest(original="A", rewritten="B")
        assert req.original == "A"
        assert req.rewritten == "B"


class TestHealthEndpoint:
    def test_health(self):
        # Use TestClient without lifespan to test health endpoint
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "ok"
