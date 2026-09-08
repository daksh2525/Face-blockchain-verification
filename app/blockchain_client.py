"""
Phase 5 + 6: Web3.py Blockchain Integration + Verification
-----------------------------------------------------------
Connects to the deployed ContentVerification contract on Sepolia testnet
and lets you:
  1. Register a SHA-256 content hash on-chain (registerContent)
  2. Check if a hash is already registered (verifyContent)
  3. Get the full on-chain record for a hash (getRecord)
  4. Verify a file's current integrity against the blockchain (verify_file)

Reads CONTRACT_ADDRESS, RPC_URL, and PRIVATE_KEY from a .env file
in the project root.
"""

import json
import os
import sys
import hashlib
from datetime import datetime, timezone

from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
RPC_URL = os.getenv("RPC_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")

ABI_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "contracts",
    "contract_abi.json"
)

REGISTRY_LOG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "registrations.json"
)


def load_abi():
    with open(ABI_PATH, "r") as f:
        return json.load(f)


def get_web3():
    if not RPC_URL:
        sys.exit("ERROR: RPC_URL missing in .env (Infura/Alchemy Sepolia URL)")
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        sys.exit("ERROR: Could not connect to Sepolia via RPC_URL. Check the URL.")
    return w3


def get_contract(w3):
    if not CONTRACT_ADDRESS:
        sys.exit("ERROR: CONTRACT_ADDRESS missing in .env")
    return w3.eth.contract(
        address=Web3.to_checksum_address(CONTRACT_ADDRESS),
        abi=load_abi(),
    )


def sha256_of_file(filepath: str) -> str:
    """Returns hex-encoded SHA-256 hash (64 chars, no 0x prefix) of a file's bytes."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def to_bytes32(hex_hash: str) -> bytes:
    """Converts a 64-char hex hash string into the bytes32 format the contract expects."""
    hex_hash = hex_hash.lower().replace("0x", "")
    if len(hex_hash) != 64:
        sys.exit(f"ERROR: hash must be 64 hex chars (SHA-256). Got {len(hex_hash)}.")
    return bytes.fromhex(hex_hash)


# --- Local registration log (bookkeeping only, not used for VERIFIED decision) ---

def _load_registry_log() -> dict:
    if not os.path.exists(REGISTRY_LOG_PATH):
        return {}
    with open(REGISTRY_LOG_PATH, "r") as f:
        return json.load(f)


def _save_registry_log(log: dict):
    os.makedirs(os.path.dirname(REGISTRY_LOG_PATH), exist_ok=True)
    with open(REGISTRY_LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)


def log_registration(file_path: str, content_hash_hex: str, tx_hash: str, source_reference: str):
    """
    Local bookkeeping only - records which hash was originally registered
    for a given file path, purely so the CLI can show a friendly
    'Blockchain hash' comparison later. This is NOT used to decide
    VERIFIED/NOT VERIFIED - that decision always comes from a real
    on-chain getRecord() call.
    """
    log = _load_registry_log()
    log[os.path.abspath(file_path)] = {
        "content_hash": content_hash_hex,
        "transaction_hash": tx_hash,
        "source_reference": source_reference,
        "registered_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    _save_registry_log(log)


# --- Core blockchain operations ---

def register_content(content_hash_hex: str, source_reference: str, file_path: str = None):
    """Signs and sends a registerContent transaction. Returns the tx hash."""
    if not PRIVATE_KEY:
        sys.exit("ERROR: PRIVATE_KEY missing in .env")

    w3 = get_web3()
    contract = get_contract(w3)
    account = w3.eth.account.from_key(PRIVATE_KEY)

    print(f"Wallet address: {account.address}")
    balance = w3.eth.get_balance(account.address)
    print(f"Balance: {w3.from_wei(balance, 'ether')} ETH")

    hash_bytes32 = to_bytes32(content_hash_hex)

    tx = contract.functions.registerContent(
        hash_bytes32, source_reference
    ).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gas": 200000,
        "gasPrice": w3.eth.gas_price,
        "chainId": 11155111,  # Sepolia
    })

    signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"Transaction sent: {tx_hash.hex()}")
    print("Waiting for confirmation...")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"Confirmed in block {receipt.blockNumber} (status={receipt.status})")

    if file_path:
        log_registration(file_path, content_hash_hex, tx_hash.hex(), source_reference)

    return tx_hash.hex()


def verify_content(content_hash_hex: str) -> bool:
    """Read-only call: checks if a hash is already registered on-chain."""
    w3 = get_web3()
    contract = get_contract(w3)
    hash_bytes32 = to_bytes32(content_hash_hex)
    is_verified = contract.functions.verifyContent(hash_bytes32).call()
    return is_verified


def get_record(content_hash_hex: str):
    """Read-only call: fetches the full on-chain record for a content hash."""
    w3 = get_web3()
    contract = get_contract(w3)
    hash_bytes32 = to_bytes32(content_hash_hex)
    exists, submitter, timestamp, source_reference = contract.functions.getRecord(hash_bytes32).call()
    return {
        "exists": exists,
        "submitter": submitter,
        "timestamp": timestamp,
        "source_reference": source_reference,
    }


def verify_file_integrity(file_path: str):
    """
    Full verification flow:
      1. Recompute the CURRENT SHA-256 hash of the file on disk.
      2. Read the REAL on-chain record for that current hash (getRecord).
      3. If found -> content is unchanged since registration -> VERIFIED.
         If not found -> the file's current bytes don't match anything
         registered on-chain -> NOT VERIFIED / CONTENT CHANGED.
    Also shows the originally-registered hash from the local log (if any)
    purely for a clearer side-by-side comparison in the CLI output.
    """
    current_hash = sha256_of_file(file_path)
    print(f"Current Hash:\n{current_hash}\n")

    log = _load_registry_log()
    original_entry = log.get(os.path.abspath(file_path))
    if original_entry:
        print(f"Originally registered hash (from local log):\n{original_entry['content_hash']}\n")

    print("Reading blockchain record for the current hash...")
    record = get_record(current_hash)

    if record["exists"]:
        print(f"\nBlockchain Hash:\n{current_hash}")
        print(f"\nSubmitter:       {record['submitter']}")
        print(f"Registered at:   {record['timestamp']} (unix)")
        print(f"Source:          {record['source_reference']}")
        print("\n========================================")
        print("VERIFICATION RESULT: VERIFIED ✓")
        print("========================================")
        return True
    else:
        if original_entry:
            print(f"\nBlockchain Hash (originally registered):\n{original_entry['content_hash']}")
        print("\nNo on-chain record found for the current content hash.")
        print("\n========================================")
        print("VERIFICATION RESULT: NOT VERIFIED / CONTENT CHANGED ✗")
        print("========================================")
        return False


if __name__ == "__main__":
    # Simple CLI:
    #   python blockchain_client.py register <path_to_file> "source note"
    #   python blockchain_client.py verify <sha256_hash_hex>
    #   python blockchain_client.py verify_file <path_to_file>
    if len(sys.argv) < 2:
        print("Usage:")
        print('  python blockchain_client.py register <file_path> "source reference"')
        print("  python blockchain_client.py verify <sha256_hash_hex>")
        print("  python blockchain_client.py verify_file <file_path>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "register":
        if len(sys.argv) < 4:
            sys.exit('Usage: python blockchain_client.py register <file_path> "source reference"')
        file_path = sys.argv[2]
        source_ref = sys.argv[3]
        file_hash = sha256_of_file(file_path)
        print(f"SHA-256 hash: {file_hash}")
        register_content(file_hash, source_ref, file_path=file_path)

    elif command == "verify":
        if len(sys.argv) < 3:
            sys.exit("Usage: python blockchain_client.py verify <sha256_hash_hex>")
        result = verify_content(sys.argv[2])
        print(f"isVerified: {result}")

    elif command == "verify_file":
        if len(sys.argv) < 3:
            sys.exit("Usage: python blockchain_client.py verify_file <file_path>")
        verify_file_integrity(sys.argv[2])

    else:
        sys.exit(f"Unknown command: {command}")