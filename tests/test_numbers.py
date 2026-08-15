"""Tests for number extraction and preservation."""

from __future__ import annotations

from textforge.validation.numbers import extract_numbers, validate_numbers


class TestNumberExtraction:
    def test_integers(self):
        nums = extract_numbers("There are 42 items and 7 categories.")
        assert "42" in nums
        assert "7" in nums

    def test_decimals(self):
        nums = extract_numbers("The value is 3.14 and margin 0.05.")
        assert "3.14" in nums
        assert "0.05" in nums

    def test_scientific(self):
        nums = extract_numbers("Values 1.5e10 and 3.2E-4 were measured.")
        assert "1.5e10" in nums
        assert "3.2E-4" in nums

    def test_percentages(self):
        nums = extract_numbers("Improved by 15.3% over 92% baseline.")
        assert "15.3%" in nums
        assert "92%" in nums

    def test_negative(self):
        nums = extract_numbers("Temperature was -15 and error -3.5.")
        assert "-15" in nums
        assert "-3.5" in nums

    def test_fractions(self):
        nums = extract_numbers("The ratio is 1/2 and 3/4.")
        assert "1/2" in nums
        assert "3/4" in nums


class TestNumberPreservation:
    def test_equal_sets(self):
        source = ["42", "3.14", "1.5e10"]
        candidate = ["42", "3.14", "1.5e10"]
        result = validate_numbers(source, candidate)
        assert result.passed
        assert result.missing == []
        assert result.added == []

    def test_missing_number(self):
        source = ["42", "3.14"]
        candidate = ["42"]
        result = validate_numbers(source, candidate)
        assert not result.passed
        assert "3.14" in result.missing

    def test_added_number(self):
        source = ["42"]
        candidate = ["42", "99"]
        result = validate_numbers(source, candidate)
        assert not result.passed
        assert "99" in result.added

    def test_duplicate_counts(self):
        source = ["42", "42"]
        candidate = ["42"]
        result = validate_numbers(source, candidate)
        assert not result.passed
        assert "42" in result.missing
