"""
face_embedding.py

Handles embedding normalization and similarity scoring.

Note: InsightFace's buffalo_l pack already includes a recognition model,
so `face.normed_embedding` (L2-normalized 512-d vector) is produced during
detection in face_detection.py. This module is responsible for:
  1. Guaranteeing embeddings are normalized (defensive, in case a future
     detector/model doesn't pre-normalize).
  2. Computing similarity scores between embeddings.
  3. Converting raw cosine similarity into the 0-100 "face similarity score"
     used throughout the rest of the pipeline.
"""

import logging
from typing import Optional

import numpy as np

from app.face_detection import DetectedFace

logger = logging.getLogger("face_embedding")


class EmbeddingUnavailableError(Exception):
    """Raised when a DetectedFace has no embedding computed."""
    pass


def normalize_embedding(embedding: np.ndarray) -> np.ndarray:
    """
    L2-normalizes an embedding vector so cosine similarity reduces to a
    simple dot product. Defensive: no-ops if already normalized.
    """
    norm = np.linalg.norm(embedding)
    if norm == 0:
        raise EmbeddingUnavailableError("Embedding is a zero vector; cannot normalize.")
    return embedding / norm


def get_embedding(face: DetectedFace) -> np.ndarray:
    """
    Returns a guaranteed-normalized embedding for a DetectedFace.
    Raises EmbeddingUnavailableError if no embedding was computed for this face.
    """
    if face.embedding is None:
        raise EmbeddingUnavailableError(
            "This face has no embedding. This can happen if the recognition "
            "model failed to run on the detected face region."
        )
    return normalize_embedding(face.embedding)


def cosine_similarity(embedding_a: np.ndarray, embedding_b: np.ndarray) -> float:
    """
    Computes cosine similarity between two normalized embeddings.
    Returns a value in [-1, 1] (in practice, for InsightFace embeddings of
    real faces, values are typically in [0, 1]).
    """
    a = normalize_embedding(embedding_a)
    b = normalize_embedding(embedding_b)
    return float(np.dot(a, b))


def similarity_score(embedding_a: np.ndarray, embedding_b: np.ndarray) -> float:
    """
    Converts cosine similarity into a 0-100 "face similarity score".

    IMPORTANT: this is a similarity metric, NOT a probability that two
    faces belong to the same person. It should always be labeled as
    "face similarity score" in any output, never as an identity match
    probability or certainty.
    """
    cos_sim = cosine_similarity(embedding_a, embedding_b)
    # Clamp to [0, 1] before scaling to avoid small negative similarities
    # (which do occur for very dissimilar faces) producing negative percentages.
    clamped = max(0.0, min(1.0, cos_sim))
    return round(clamped * 100, 2)


def compare_faces(face_a: DetectedFace, face_b: DetectedFace) -> float:
    """
    Convenience wrapper: given two DetectedFace objects (each already
    carrying an embedding), returns their face similarity score (0-100).
    """
    emb_a = get_embedding(face_a)
    emb_b = get_embedding(face_b)
    score = similarity_score(emb_a, emb_b)
    logger.info(f"Computed face similarity score: {score}%")
    return score