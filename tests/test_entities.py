"""Tests for entity extraction and comparison."""

from textforge.validation.entities import compare_entities, extract_entities


class TestEntityExtraction:
    def test_abbreviations(self):
        entities = extract_entities("The API uses HTTP and REST protocols.")
        assert "API" in entities
        assert "HTTP" in entities
        assert "REST" in entities

    def test_snake_case(self):
        entities = extract_entities("Call the function_name and get_result.")
        assert "function_name" in entities
        assert "get_result" in entities


class TestEntityComparison:
    def test_preserved(self):
        result = compare_entities(
            "The API uses HTTP for REST.",
            "The API employs HTTP for REST.",
        )
        assert result.score == 1.0 or result.score > 0.9

    def test_missing_entity(self):
        result = compare_entities(
            "The API uses HTTP.",
            "The interface uses a protocol.",
        )
        assert "API" in result.missing or "HTTP" in result.missing
