"""
test_hashing.py

Tests the core SHA-256 fingerprinting guarantees:
  - Same bytes -> same hash (determinism)
  - Same exact file loaded twice -> same hash
  - Even a 1-byte change -> a completely different hash

Run with: pytest tests/test_hashing.py -v
"""

import pytest

from app.hashing import compute_sha256, fingerprint_candidate, ContentRecord
from app.candidate_matcher import CandidateMatch
from app.web_search import SearchResult


def test_same_bytes_same_hash():
    data = b"this is some image content pretending to be bytes"
    hash_a = compute_sha256(data)
    hash_b = compute_sha256(data)
    assert hash_a == hash_b


def test_modified_bytes_different_hash():
    original = b"this is some image content pretending to be bytes"
    modified = b"this is some image content pretending to be Bytes"  # 1 char changed
    hash_a = compute_sha256(original)
    hash_b = compute_sha256(modified)
    assert hash_a != hash_b


def test_hash_is_hex_sha256_length():
    data = b"any content"
    h = compute_sha256(data)
    assert len(h) == 64  # SHA-256 hex digest is always 64 hex characters
    int(h, 16)  # should not raise - confirms it's valid hex


def test_hash_rejects_non_bytes():
    with pytest.raises(TypeError):
        compute_sha256("not bytes, a plain string")


def test_fingerprint_candidate_produces_matching_hash():
    fake_jpeg_bytes = b"\xff\xd8\xff" + b"fake jpeg content for testing"
    result = SearchResult(source_url="https://example.com/post/123", title="Example Post")
    match = CandidateMatch(search_result=result, similarity_score=87.5, image_bytes=fake_jpeg_bytes)

    record = fingerprint_candidate(match)

    assert isinstance(record, ContentRecord)
    assert record.content_hash == compute_sha256(fake_jpeg_bytes)
    assert record.content_type == "image/jpeg"
    assert record.similarity_score == 87.5
    assert record.source_url == "https://example.com/post/123"


def test_fingerprint_candidate_rejects_missing_bytes():
    result = SearchResult(source_url="https://example.com/post/123")
    match = CandidateMatch(search_result=result, similarity_score=87.5, image_bytes=None)

    with pytest.raises(ValueError):
        fingerprint_candidate(match)


def test_fingerprint_candidate_rejects_unscored_match():
    result = SearchResult(source_url="https://example.com/post/123")
    match = CandidateMatch(search_result=result, similarity_score=None, image_bytes=b"\xff\xd8\xffsome bytes")

    with pytest.raises(ValueError):
        fingerprint_candidate(match)