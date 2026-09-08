"""
manual_test_phase5.py

Run this manually to exercise Phase 5 end-to-end: register a content
hash on the real Sepolia testnet, then read it back. Uses a fixed test
string's SHA-256 hash so it's repeatable and doesn't require Phase 1-3.

Usage:
    python manual_test_phase5.py
"""

import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from app.hashing import compute_sha256
from app.blockchain import (
    register_content_hash,
    read_record,
    is_registered,
    DuplicateContentError,
    BlockchainConfigError,
    BlockchainConnectionError,
    TransactionFailedError,
)


def main():
    # A fixed, repeatable "content" for testing purposes.
    test_content = b"hackathon test content - phase 5 verification"
    content_hash = compute_sha256(test_content)
    source_reference = "manual_test_phase5 - test content"

    print(f"Content hash to register: 0x{content_hash}")

    print("\n[1] Checking if this hash is already registered...")
    try:
        already = is_registered(content_hash)
    except (BlockchainConfigError, BlockchainConnectionError) as e:
        print(f"    -> Config/connection error: {e}")
        return

    if already:
        print("    -> Already registered. Skipping registration, reading existing record instead.")
    else:
        print("    -> Not yet registered. Proceeding to register.")
        print("\n[2] Sending registerContent() transaction to Sepolia...")
        try:
            result = register_content_hash(content_hash, source_reference)
        except DuplicateContentError as e:
            print(f"    -> {e}")
        except TransactionFailedError as e:
            print(f"    -> Transaction failed: {e}")
            return
        else:
            print(f"    -> SUCCESS")
            print(f"    Content Hash:     0x{result.content_hash_hex}")
            print(f"    Transaction Hash: {result.transaction_hash}")
            print(f"    Block Number:     {result.block_number}")
            print(f"    Submitter:        {result.submitter_address}")
            print(f"\n    View on explorer: https://sepolia.etherscan.io/tx/{result.transaction_hash}")

    print("\n[3] Reading the record back from the blockchain...")
    record = read_record(content_hash)
    if record.exists:
        print(f"    Exists:            {record.exists}")
        print(f"    Submitter:         {record.submitter}")
        print(f"    Timestamp (unix):  {record.timestamp}")
        print(f"    Source Reference:  {record.source_reference}")
    else:
        print("    -> No record found (unexpected at this point).")


if __name__ == "__main__":
    main()