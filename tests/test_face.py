"""
test_face.py

Basic tests for Phase 1: face detection, embedding, and similarity.

Run with: pytest tests/test_face.py -v

These tests require:
  - The `insightface` model pack to be downloaded (happens automatically
    on first run, requires internet access once).
  - Two real face images in tests/fixtures/ :
      same_person_a.jpg, same_person_b.jpg  (same person, two different photos)
      different_person.jpg                   (a different person)

If you don't have fixture images yet, you can skip these and just run
main.py manually against your own input images for Phase 1 (Phase 1 has
no CLI yet — that comes in Phase 7 integration, but you can test the
functions directly from a Python shell, see README "Phase 1 manual test").
"""

import os
import pytest

from app.face_detection import (
    detect_and_select_face,
    detect_faces,
    load_image,
    NoFaceDetectedError,
    InvalidImageError,
)
from app.face_embedding import compare_faces, get_embedding

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _fixture(name):
    return os.path.join(FIXTURES, name)


@pytest.mark.skipif(
    not os.path.exists(_fixture("same_person_a.jpg")),
    reason="fixture images not present",
)
def test_same_person_high_similarity():
    face_a = detect_and_select_face(_fixture("same_person_a.jpg"))
    face_b = detect_and_select_face(_fixture("same_person_b.jpg"))
    score = compare_faces(face_a, face_b)
    assert score > 50.0  # same person across two photos should score reasonably high


@pytest.mark.skipif(
    not os.path.exists(_fixture("same_person_a.jpg")),
    reason="fixture images not present",
)
def test_different_person_lower_similarity():
    face_a = detect_and_select_face(_fixture("same_person_a.jpg"))
    face_c = detect_and_select_face(_fixture("different_person.jpg"))
    score = compare_faces(face_a, face_c)
    assert score < 90.0  # sanity bound; different people shouldn't score near-identical


def test_invalid_image_raises():
    with pytest.raises(InvalidImageError):
        load_image("this_file_does_not_exist.jpg")


def test_embedding_is_normalized():
    import numpy as np
    if not os.path.exists(_fixture("same_person_a.jpg")):
        pytest.skip("fixture image not present")
    face = detect_and_select_face(_fixture("same_person_a.jpg"))
    emb = get_embedding(face)
    assert abs(np.linalg.norm(emb) - 1.0) < 1e-4