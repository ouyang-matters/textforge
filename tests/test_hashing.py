"""Tests for provenance hashing."""

from textforge.provenance.hashing import sha256_hash


class TestHashing:
    def test_deterministic(self):
        text = "Hello, world!"
        h1 = sha256_hash(text)
        h2 = sha256_hash(text)
        assert h1 == h2

    def test_different_inputs(self):
        h1 = sha256_hash("hello")
        h2 = sha256_hash("world")
        assert h1 != h2

    def test_hex_format(self):
        h = sha256_hash("test")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_empty_string(self):
        h = sha256_hash("")
        assert len(h) == 64
