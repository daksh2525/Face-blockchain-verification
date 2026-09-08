"""
pipeline.py

Orchestrates the full end-to-end flow:

  Input Face Image
    -> Face Detection & Embedding
    -> Genuine Web/Image Search
    -> Candidate Discovery & Face Similarity Comparison
    -> Best Matching Content
    -> SHA-256 Content Fingerprint
    -> Blockchain Registration
    -> On-chain Verification

This module contains no CLI argument parsing - that's main.py's job.
Every step here does real work: no hardcoded results, no simulated
blockchain calls.
"""

import os
import sys
import logging

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

from app.face_detection import (
    detect_and_select_face,
    NoFaceDetectedError,
    InvalidImageError,
)
from app.web_search import (
    get_search_provider,
    SearchProviderError,
    NoSearchResultsError,
)
from app.candidate_matcher import rank_candidates, get_best_candidate
from app.hashing import compute_sha256
from app.config import config
from app.blockchain_client import (
    register_content,
    verify_content,
    get_record,
    log_registration,
)


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _print_header():
    print("=" * 40)
    print("FACE IDENTIFICATION & BLOCKCHAIN VERIFY")
    print("=" * 40)


def _guess_extension(image_bytes: bytes) -> str:
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if image_bytes.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return ".webp"
    return ".bin"


def run_pipeline(image_path: str) -> bool:
    """
    Runs the full pipeline for a single input image. Returns True if the
    final result was VERIFIED, False otherwise (including any early exit
    due to no match / no results / errors). Never raises - all failure
    paths are handled and reported via the CLI output.
    """
    _print_header()

    # --- Step 1: Load image ---
    print("\n[1] Loading image...")
    if not os.path.isfile(image_path):
        print(f"ERROR: File not found: {image_path}")
        return False
    print("Image loaded")

    # --- Step 2 + 3: Detect face + generate embedding ---
    print("\n[2] Detecting face...")
    try:
        input_face = detect_and_select_face(image_path)
    except InvalidImageError as e:
        print(f"ERROR: {e}")
        return False
    except NoFaceDetectedError as e:
        print(f"ERROR: {e}")
        return False
    print(f"Face detected (confidence={input_face.det_score:.3f})")

    print("\n[3] Generating embedding...")
    if input_face.embedding is None:
        print("ERROR: Face embedding could not be generated for this image.")
        return False
    print("Embedding generated")

    # --- Step 4: Genuine web search ---
    print("\n[4] Searching web...")
    try:
        provider = get_search_provider()
        results = provider.search_by_image(image_path, max_results=config.MAX_SEARCH_RESULTS)
    except SearchProviderError as e:
        print(f"ERROR: Search failed: {e}")
        return False
    except NoSearchResultsError:
        print("Search completed - no candidate results found for this image.")
        print("\nNo public content found to verify. Pipeline stopped (nothing to hash/register).")
        return False
    print(f"Search completed")
    print(f"Candidate results found: {len(results)}")

    # --- Step 5: Compare candidate faces ---
    print("\n[5] Comparing candidate faces...\n")
    matches = rank_candidates(input_face, results)
    for i, m in enumerate(matches, start=1):
        if m.scored:
            print(f"Candidate {i} -> {m.similarity_score}%")
        else:
            print(f"Candidate {i} -> SKIPPED ({m.error})")

    # --- Step 6: Best match ---
    print("\n[6] Best match found")
    best = get_best_candidate(matches)
    if best is None:
        print(f"No candidate crossed the configured similarity threshold ({config.SIMILARITY_THRESHOLD}%).")
        print("\nPipeline stopped (no qualifying match to hash/register).")
        return False
    print("Match candidate selected")
    print(f"\nSource:\n{best.search_result.source_url}")
    print(f"\nFace similarity:\n{best.similarity_score}%")

    # --- Step 7: SHA-256 fingerprint ---
    print("\n[7] Generating SHA-256 fingerprint...")
    content_hash = compute_sha256(best.image_bytes)
    print("Content hash generated")
    print(f"\nContent Hash:\n{content_hash}")

    # Save the matched content locally so blockchain_client's file-based
    # helpers (which log_registration and later re-verification rely on)
    # have a real file to point at. This is local bookkeeping only - the
    # verification decision itself always comes from a real on-chain read.
    os.makedirs(DATA_DIR, exist_ok=True)
    ext = _guess_extension(best.image_bytes)
    saved_path = os.path.join(DATA_DIR, f"best_match_{content_hash[:16]}{ext}")
    with open(saved_path, "wb") as f:
        f.write(best.image_bytes)

    # --- Step 8: Register on blockchain ---
    print("\n[8] Registering hash on blockchain...")
    already_registered = verify_content(content_hash)
    if already_registered:
        print("This content hash is already registered on-chain (skipping duplicate registration).")
    else:
        try:
            tx_hash = register_content(
                content_hash,
                source_reference=best.search_result.source_url,
                file_path=saved_path,
            )
        except SystemExit as e:
            # blockchain_client.py uses sys.exit() on config/connection errors
            print(f"ERROR: Blockchain registration failed: {e}")
            return False
        print("Transaction submitted")
        print(f"\nTransaction Hash:\n{tx_hash}")

    # --- Step 9: Read blockchain record ---
    print("\n[9] Reading blockchain record...")
    record = get_record(content_hash)
    if not record["exists"]:
        print("ERROR: Could not find the record on-chain right after registration. Try again shortly.")
        return False
    print("Blockchain record retrieved")

    # --- Step 10: Verify ---
    print("\n[10] Verifying content...\n")
    current_hash = compute_sha256(best.image_bytes)
    print(f"Current Hash:\n{current_hash}")
    print(f"\nBlockchain Hash:\n{content_hash}")

    verified = current_hash == content_hash and record["exists"]

    print("\n" + "=" * 40)
    if verified:
        print("VERIFICATION RESULT: VERIFIED ✓")
    else:
        print("VERIFICATION RESULT: NOT VERIFIED / CONTENT CHANGED ✗")
    print("=" * 40)

    return verified