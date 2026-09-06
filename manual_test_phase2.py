"""
manual_test_phase2.py

Run this manually to exercise Phase 2 end-to-end against the real
Google Cloud Vision Web Detection API. Not an automated pytest file
because it costs API quota and needs a real network + API key.

Usage:
    python manual_test_phase2.py input/your_photo.jpg
"""

import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from app.face_detection import detect_and_select_face
from app.web_search import get_search_provider, SearchProviderError, NoSearchResultsError
from app.candidate_matcher import rank_candidates, get_best_candidate
from app.config import config


def main():
    if len(sys.argv) != 2:
        print("Usage: python manual_test_phase2.py <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]

    print("[1] Detecting face in input image...")
    input_face = detect_and_select_face(image_path)
    print(f"    -> face detected (det_score={input_face.det_score:.3f})")

    print("[2] Running genuine reverse-image search...")
    provider = get_search_provider()
    try:
        results = provider.search_by_image(image_path, max_results=config.MAX_SEARCH_RESULTS)
    except NoSearchResultsError:
        print("    -> Search completed but found no candidates. Nothing to rank.")
        return
    except SearchProviderError as e:
        print(f"    -> Search provider error: {e}")
        return
    print(f"    -> {len(results)} candidate(s) found")

    print("[3] Downloading candidates and scoring face similarity...")
    matches = rank_candidates(input_face, results)

    print("\n--- Candidate ranking ---")
    for i, m in enumerate(matches, start=1):
        if m.scored:
            print(f"Candidate {i} -> {m.similarity_score}%  ({m.search_result.source_url})")
        else:
            print(f"Candidate {i} -> SKIPPED ({m.error})  ({m.search_result.source_url})")

    best = get_best_candidate(matches)
    print(f"\nThreshold: {config.SIMILARITY_THRESHOLD}%")
    if best:
        print(f"BEST MATCH -> {best.similarity_score}% -> {best.search_result.source_url}")
    else:
        print("No candidate crossed the configured similarity threshold.")


if __name__ == "__main__":
    main()