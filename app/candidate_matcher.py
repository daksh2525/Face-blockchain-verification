"""
candidate_matcher.py

Takes SearchResult candidates from web_search.py, downloads each candidate
image, runs face detection + embedding on it, and compares it against the
input face's embedding. Produces a ranked list of CandidateMatch objects.

Handles the realistic failure modes of working with arbitrary public URLs:
unreachable hosts, non-image content, images with no detectable face, etc.
Any single candidate failing does NOT abort the whole pipeline.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import cv2
import requests

from app.config import config
from app.face_detection import DetectedFace, detect_faces, NoFaceDetectedError
from app.face_embedding import compare_faces, EmbeddingUnavailableError
from app.web_search import SearchResult

logger = logging.getLogger("candidate_matcher")

REQUEST_TIMEOUT_SECONDS = 15
MAX_IMAGE_BYTES = 20 * 1024 * 1024  # 20MB safety cap


@dataclass
class CandidateMatch:
    search_result: SearchResult
    similarity_score: Optional[float] = None   # None if this candidate couldn't be scored
    image_bytes: Optional[bytes] = None        # raw bytes, kept for Phase 3 hashing
    error: Optional[str] = None                # human-readable reason if scoring failed

    @property
    def scored(self) -> bool:
        return self.similarity_score is not None

    @property
    def crossed_threshold(self) -> bool:
        return self.scored and self.similarity_score >= config.SIMILARITY_THRESHOLD


def download_image_bytes(url: str) -> bytes:
    """
    Downloads an image from a public URL. Raises ValueError on any failure
    (network error, non-2xx status, non-image content, too large).
    """
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS, stream=True)
    except requests.RequestException as e:
        raise ValueError(f"Could not reach URL: {e}")

    if resp.status_code != 200:
        raise ValueError(f"URL returned status {resp.status_code}")

    content_type = resp.headers.get("Content-Type", "")
    if content_type and not content_type.startswith("image/"):
        raise ValueError(f"URL did not return an image (Content-Type: {content_type})")

    data = resp.content
    if len(data) == 0:
        raise ValueError("URL returned empty content")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError(f"Image too large ({len(data)} bytes), skipping")

    return data


def bytes_to_image(image_bytes: bytes) -> np.ndarray:
    """Decodes raw image bytes into a BGR numpy array (OpenCV format)."""
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode downloaded bytes as an image")
    return img


def score_candidate(input_face: DetectedFace, result: SearchResult) -> CandidateMatch:
    """
    Downloads a single candidate image and scores it against the input face.
    Never raises — failures are captured in CandidateMatch.error so one bad
    candidate doesn't stop processing the rest.
    """
    url_to_try = result.image_url or result.source_url

    try:
        image_bytes = download_image_bytes(url_to_try)
    except ValueError as e:
        logger.warning(f"Skipping candidate ({url_to_try}): {e}")
        return CandidateMatch(search_result=result, error=str(e))

    try:
        img = bytes_to_image(image_bytes)
    except ValueError as e:
        logger.warning(f"Skipping candidate ({url_to_try}): {e}")
        return CandidateMatch(search_result=result, image_bytes=image_bytes, error=str(e))

    try:
        candidate_faces = detect_faces(img)
    except NoFaceDetectedError:
        logger.warning(f"No face detected in candidate image: {url_to_try}")
        return CandidateMatch(
            search_result=result,
            image_bytes=image_bytes,
            error="No face detected in candidate image",
        )

    # If multiple faces appear in the candidate, compare against the best-scoring one
    best_score = None
    for cand_face in candidate_faces:
        try:
            score = compare_faces(input_face, cand_face)
        except EmbeddingUnavailableError:
            continue
        if best_score is None or score > best_score:
            best_score = score

    if best_score is None:
        return CandidateMatch(
            search_result=result,
            image_bytes=image_bytes,
            error="Candidate face(s) had no usable embedding",
        )

    return CandidateMatch(search_result=result, similarity_score=best_score, image_bytes=image_bytes)


def rank_candidates(input_face: DetectedFace, results: List[SearchResult]) -> List[CandidateMatch]:
    """
    Scores every candidate and returns them sorted best-first.
    Unscored (failed) candidates are sorted to the end.
    """
    matches = [score_candidate(input_face, r) for r in results]
    matches.sort(key=lambda m: (m.similarity_score is None, -(m.similarity_score or 0)))

    scored_count = sum(1 for m in matches if m.scored)
    logger.info(f"Scored {scored_count}/{len(matches)} candidate(s) successfully.")
    return matches


def get_best_candidate(matches: List[CandidateMatch]) -> Optional[CandidateMatch]:
    """
    Returns the highest-scoring candidate that crosses SIMILARITY_THRESHOLD,
    or None if no candidate qualifies (this is a normal, expected outcome,
    not an error).
    """
    qualifying = [m for m in matches if m.crossed_threshold]
    if not qualifying:
        return None
    return max(qualifying, key=lambda m: m.similarity_score)