"""
face_detection.py

Wraps InsightFace's face analysis app to detect faces in an image
and select the "appropriate" face when multiple are present.

This module does NOT identify who a person is. It only locates
face regions and hands landmarks/crops off for embedding generation.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import cv2
import insightface
from insightface.app import FaceAnalysis

from app.config import config

logger = logging.getLogger("face_detection")


class NoFaceDetectedError(Exception):
    """Raised when no face can be found in an image."""
    pass


class InvalidImageError(Exception):
    """Raised when an image file cannot be loaded/decoded."""
    pass


@dataclass
class DetectedFace:
    bbox: np.ndarray          # [x1, y1, x2, y2]
    landmarks: np.ndarray     # 5-point landmarks
    det_score: float          # detector confidence
    embedding: Optional[np.ndarray] = None  # filled in by face_embedding.py

    @property
    def area(self) -> float:
        x1, y1, x2, y2 = self.bbox
        return max(0.0, (x2 - x1)) * max(0.0, (y2 - y1))


_face_app: Optional[FaceAnalysis] = None


def get_face_app() -> FaceAnalysis:
    """
    Lazily initializes and caches the InsightFace analysis app.
    Loading the model is slow, so we only do it once per process.
    """
    global _face_app
    if _face_app is None:
        logger.info(f"Loading InsightFace model pack '{config.INSIGHTFACE_MODEL_NAME}'...")
        _face_app = FaceAnalysis(
            name=config.INSIGHTFACE_MODEL_NAME,
            providers=[config.INSIGHTFACE_PROVIDER],
        )
        # ctx_id=-1 forces CPU; det_size controls detector input resolution
        _face_app.prepare(ctx_id=-1 if "CPU" in config.INSIGHTFACE_PROVIDER else 0, det_size=(640, 640))
        logger.info("InsightFace model loaded.")
    return _face_app


def load_image(image_path: str) -> np.ndarray:
    """
    Loads an image from disk as a BGR numpy array (OpenCV format).
    Raises InvalidImageError if the file can't be read/decoded.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise InvalidImageError(
            f"Could not load image at '{image_path}'. "
            "It may be missing, corrupted, or an unsupported format."
        )
    return img


def detect_faces(img: np.ndarray) -> List[DetectedFace]:
    """
    Runs face detection on a BGR numpy image and returns all detected faces.
    Raises NoFaceDetectedError if none are found.
    """
    app = get_face_app()
    faces = app.get(img)

    if not faces:
        raise NoFaceDetectedError(
            "No face detected in the image. Try a clearer, front-facing photo."
        )

    detected = [
        DetectedFace(
            bbox=f.bbox,
            landmarks=f.kps,
            det_score=float(f.det_score),
            embedding=getattr(f, "normed_embedding", None),
        )
        for f in faces
    ]
    logger.info(f"Detected {len(detected)} face(s).")
    return detected


def select_face(faces: List[DetectedFace], strategy: str = None) -> DetectedFace:
    """
    Selects the "appropriate" face when multiple are detected.

    strategy:
      - "largest": pick the face with the largest bounding-box area (default;
        assumes the main subject is closest to the camera / most prominent).
      - "most_confident": pick the face with the highest detector confidence score.
    """
    strategy = strategy or config.FACE_SELECTION_STRATEGY

    if len(faces) > 1:
        logger.warning(
            f"Multiple faces ({len(faces)}) detected in input image. "
            f"Selecting using strategy='{strategy}'."
        )

    if strategy == "most_confident":
        return max(faces, key=lambda f: f.det_score)
    # default: largest
    return max(faces, key=lambda f: f.area)


def detect_and_select_face(image_path: str, strategy: str = None) -> DetectedFace:
    """
    Convenience wrapper: load image -> detect faces -> select the right one.
    """
    img = load_image(image_path)
    faces = detect_faces(img)
    return select_face(faces, strategy=strategy)