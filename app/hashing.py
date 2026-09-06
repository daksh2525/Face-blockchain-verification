"""
hashing.py

Content fingerprinting: given the exact bytes of the best-matching
candidate image, compute a deterministic SHA-256 hash and bundle it
with relevant metadata into a ContentRecord.

This hash is the "content hash" that will later be written to the
blockchain (Phase 5/6). It is NOT the same thing as a blockchain
transaction hash — see blockchain.py for that distinction.

SHA-256 properties this module relies on:
  - Deterministic: identical bytes always produce identical output.
  - Avalanche effect: even a single-byte change in the input produces
    a completely different, unpredictable hash.
  - One-way: the hash cannot be reversed to recover the original bytes.
"""

import hashlib
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

from app.candidate_matcher import CandidateMatch

logger = logging.getLogger("hashing")


def compute_sha256(data: bytes) -> str:
    """
    Computes the SHA-256 hash of raw bytes, returned as a lowercase hex string.

    Same bytes + SHA-256 algorithm -> always the same hash.
    A single changed byte in `data` produces a completely different hash.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("compute_sha256 expects raw bytes")
    return hashlib.sha256(data).hexdigest()


@dataclass
class ContentRecord:
    """
    A local record describing the fingerprinted content, kept separately
    from the hash itself. This is what gets logged/displayed alongside
    the hash, and a subset of it (source_url) is what we choose to also
    store on-chain in Phase 5.
    """
    content_hash: str          # SHA-256 hex digest of the image bytes
    source_url: str            # page where the matching content was found
    image_url: Optional[str]   # direct image URL, if available
    content_type: str          # e.g. "image/jpeg" (best-effort guess)
    similarity_score: float    # face similarity score that led to this match
    search_result_title: Optional[str]
    match_type: Optional[str]  # e.g. "google_reverse_image"
    timestamp_utc: str         # ISO-8601 UTC timestamp of when this record was created

    def to_dict(self) -> dict:
        return asdict(self)


def _guess_content_type(image_bytes: bytes) -> str:
    """
    Best-effort content type guess from magic bytes, since we don't
    always get a reliable Content-Type header from arbitrary URLs.
    """
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


def fingerprint_candidate(match: CandidateMatch) -> ContentRecord:
    """
    Builds a ContentRecord (including the SHA-256 content hash) from a
    scored CandidateMatch. Hashes the exact downloaded image bytes —
    the same bytes that were used for face comparison — so the
    fingerprint corresponds precisely to the content that was verified.
    """
    if match.image_bytes is None:
        raise ValueError(
            "This candidate has no downloaded image bytes to fingerprint "
            "(it may have failed to download)."
        )
    if match.similarity_score is None:
        raise ValueError("This candidate was not successfully scored; refusing to fingerprint it.")

    content_hash = compute_sha256(match.image_bytes)
    content_type = _guess_content_type(match.image_bytes)

    record = ContentRecord(
        content_hash=content_hash,
        source_url=match.search_result.source_url,
        image_url=match.search_result.image_url,
        content_type=content_type,
        similarity_score=match.similarity_score,
        search_result_title=match.search_result.title,
        match_type=match.search_result.match_type,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
    )

    logger.info(f"Content hash generated: {content_hash}")
    return record