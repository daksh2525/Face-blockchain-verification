# Face Identification & Blockchain Verification

A hackathon project that pipelines face recognition, genuine reverse-image
web search, and blockchain-based content fingerprinting into one CLI tool.

> **Status: Phases 1–4 complete.** Phases 5–8 (blockchain read/write
> integration, full pipeline, and final docs) are in progress — see
> [Roadmap](#roadmap--whats-next) below.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Problem Statement](#problem-statement)
3. [Architecture](#architecture)
4. [Current Progress](#current-progress)
5. [Prerequisites & Accounts Needed](#prerequisites--accounts-needed)
6. [Installation](#installation)
7. [Environment Variables](#environment-variables)
8. [Folder Structure](#folder-structure)
9. [What's Built So Far (Phase 1–4 Details)](#whats-built-so-far-phase-14-details)
10. [Running What's Built](#running-whats-built)
11. [Roadmap / What's Next](#roadmap--whats-next)
12. [Known Limitations (Current)](#known-limitations-current)
13. [Privacy & Ethical Considerations](#privacy--ethical-considerations)
14. [Troubleshooting](#troubleshooting)

---

## Project Overview

This project takes a face photo as input and:

1. Detects the face and generates a biometric embedding.
2. Performs a **genuine** reverse-image search across the public web to
   find visually similar public content.
3. Downloads candidate images and compares faces to rank them by
   similarity.
4. Takes the best-matching public content and computes a **SHA-256
   fingerprint** of it.
5. Registers that fingerprint on an Ethereum testnet via a smart
   contract.
6. Later, re-verifies the content by recomputing its hash and comparing
   it against what's stored on-chain — proving whether the content has
   been tampered with since registration.

No website is required — everything runs from a CLI, designed to be easy
to demo in a screen recording.

## Problem Statement

Reverse-image search tools can find where a face appears online, but
there's no simple, verifiable way to prove *that specific piece of
content* hasn't been altered since it was checked. This project solves
that by fingerprinting the matched content with SHA-256 and anchoring
that fingerprint immutably on a blockchain — so anyone can later verify
the content's integrity without trusting a central authority.

## Architecture

```
Input Face Image
      │
      ▼
Face Detection & Embedding (InsightFace)
      │
      ▼
Genuine Reverse-Image Search (SerpApi / Google Vision)
      │
      ▼
Candidate Image Download + Face Comparison
      │
      ▼
Best Match Selected (face similarity score)
      │
      ▼
SHA-256 Content Fingerprint
      │
      ▼
Smart Contract: registerContent() on Sepolia testnet
      │
      ▼
On-chain Storage: content hash + submitter + timestamp + source
      │
      ▼
Verification: re-hash content → compare to on-chain record
      │
      ▼
VERIFIED ✓ or TAMPERED ✗
```

## Current Progress

| Phase | Description | Status |
|---|---|---|
| 1 | Face detection + embedding + similarity | ✅ Done |
| 2 | Genuine web/image search + candidate matching | ✅ Done |
| 3 | SHA-256 content fingerprinting | ✅ Done |
| 4 | Solidity smart contract | ✅ Written, ready to deploy |
| 5 | Web3.py blockchain integration (write) | ⏳ Next |
| 6 | Blockchain verification (read + compare) | ⏳ Upcoming |
| 7 | Full pipeline + CLI (`main.py`) | ⏳ Upcoming |
| 8 | Testing + final README + demo prep | ⏳ Upcoming |

## Prerequisites & Accounts Needed

- **Python 3.9–3.11** (3.11 recommended; tested on 3.11.16)
- **A SerpApi account** (free, no credit card) — for reverse-image
  search: [serpapi.com](https://serpapi.com)
- **A Cloudinary account** (free tier works) — used to briefly host the
  input image at a public URL so SerpApi can fetch it (auto-deleted
  right after each search): [cloudinary.com](https://cloudinary.com)
- **MetaMask** browser extension + a **Sepolia testnet** wallet with
  free test ETH (from a faucet) — needed starting Phase 5, for
  deploying/calling the smart contract

## Installation

```bash
git clone <your-repo-url>
cd face-blockchain-verification

python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# then fill in .env with your own keys (see below)
```

First run will auto-download the InsightFace `buffalo_l` model pack
(~350MB, one-time, needs internet).

## Environment Variables

All configuration lives in `.env` (never commit this file — see
`.gitignore`). Template: `.env.example`.

```ini
# --- Face matching ---
SIMILARITY_THRESHOLD=60.0        # 0-100 scale; candidate must score >= this to count as a "match"
FACE_SELECTION_STRATEGY=largest  # "largest" or "most_confident" — which face to use if multiple detected in input
INSIGHTFACE_MODEL_NAME=buffalo_l
INSIGHTFACE_PROVIDER=CPUExecutionProvider

# --- Search (Phase 2) ---
SEARCH_PROVIDER=serpapi          # "serpapi" (default, no card) or "google_vision" (needs GCP billing)
SEARCH_API_KEY=                  # your SerpApi (or Google Cloud Vision) API key
MAX_SEARCH_RESULTS=10

# --- Temporary image hosting (only needed for SerpApi) ---
IMAGE_HOST_PROVIDER=cloudinary   # "cloudinary" (default) or "litterbox" (anonymous, no account)
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=

# --- Blockchain (Phase 5/6) ---
RPC_URL=                         # Sepolia RPC endpoint (e.g. from Infura/Alchemy)
PRIVATE_KEY=                     # wallet private key used to send transactions — NEVER share or commit this
CONTRACT_ADDRESS=                # filled in after deploying ContentVerification.sol
```

**Never commit `.env`. Never hardcode any key directly in code.**

## Folder Structure

```
face-blockchain-verification/
│
├── app/
│   ├── __init__.py
│   ├── config.py             # all env-var-driven settings
│   ├── face_detection.py     # Phase 1: detect + select face
│   ├── face_embedding.py     # Phase 1: normalize + similarity scoring
│   ├── web_search.py         # Phase 2: SerpApi / Google Vision reverse-image search
│   ├── candidate_matcher.py  # Phase 2: download candidates, rank by face similarity
│   ├── image_hosting.py      # Phase 2: temp public hosting for image-URL-based search
│   ├── hashing.py            # Phase 3: SHA-256 content fingerprinting
│   ├── blockchain.py         # Phase 5/6: web3.py integration (coming next)
│   └── pipeline.py           # Phase 7: full pipeline orchestration (coming)
│
├── contracts/
│   └── ContentVerification.sol  # Phase 4: the on-chain registry contract
│
├── tests/
│   ├── __init__.py
│   ├── test_face.py          # Phase 1 tests
│   ├── test_hashing.py       # Phase 3 tests
│   └── test_blockchain.py    # Phase 5/6 tests (coming)
│
├── input/                    # put your input face images here
├── data/                     # scratch space for intermediate data
│
├── manual_test_phase2.py     # standalone script to exercise Phase 2 end-to-end
├── main.py                   # Phase 7: final CLI entrypoint (coming)
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md                 # this file
```

## What's Built So Far (Phase 1–4 Details)

### Phase 1 — Face Detection & Embedding
Uses **InsightFace** (`buffalo_l` model pack) to detect faces and
generate 512-dimensional, L2-normalized embeddings. If multiple faces
are detected, one is auto-selected via a configurable strategy
(`largest` bounding box by default). Similarity between two faces is
computed as cosine similarity, scaled to a 0–100 **face similarity
score** — explicitly *not* framed as an identity-match probability.

Key files: `app/face_detection.py`, `app/face_embedding.py`

### Phase 2 — Genuine Web/Image Search & Candidate Matching
Performs a **real** reverse-image search via **SerpApi**'s Google
Reverse Image engine (no hardcoded or fake results). Since SerpApi
needs a public image URL rather than raw bytes, the input image is
first uploaded to **Cloudinary** (the user's own account), searched,
and then immediately deleted. Every candidate result is downloaded,
run through face detection, and scored against the input face.
Candidates that fail (no face, broken link, non-image content) are
skipped gracefully rather than crashing the pipeline.

An alternate provider, **Google Cloud Vision Web Detection**, is also
implemented behind the same interface and can be swapped in via
`SEARCH_PROVIDER=google_vision`.

Key files: `app/web_search.py`, `app/candidate_matcher.py`,
`app/image_hosting.py`

**Verified working** on a real test image — correctly found and ranked
9 real public candidates (Instagram, Reddit, IMDb, Wikipedia, etc.)
with sensible similarity scores.

### Phase 3 — SHA-256 Content Fingerprinting
Takes the exact downloaded bytes of the best-matching candidate image
and computes a deterministic SHA-256 hash, bundled with metadata
(source URL, content type, similarity score, timestamp) into a
`ContentRecord`. Verified via automated tests that identical bytes
always produce identical hashes, and that even a single changed byte
produces a completely different hash.

Key file: `app/hashing.py`

### Phase 4 — Smart Contract
`contracts/ContentVerification.sol` — a simple Solidity contract with:

- `registerContent(bytes32 contentHash, string sourceReference)` —
  stores a new content hash on-chain; reverts on duplicate hashes.
- `verifyContent(bytes32 contentHash) → bool` — quick existence check.
- `getRecord(bytes32 contentHash) → (exists, submitter, timestamp,
  sourceReference)` — full record lookup.
- Emits a `ContentRegistered` event on every successful registration.

Deployed via Remix IDE to the **Sepolia** testnet using MetaMask.

## Running What's Built

**Phase 1 (manual, from a Python shell):**
```python
from app.face_detection import detect_and_select_face
from app.face_embedding import compare_faces

face1 = detect_and_select_face("input/photo1.jpg")
face2 = detect_and_select_face("input/photo2.jpg")
print(compare_faces(face1, face2))
```

**Phase 2 (end-to-end search + matching):**
```bash
python manual_test_phase2.py input/your_photo.jpg
```

**Phase 3 (automated tests):**
```bash
pytest tests/test_hashing.py -v
```

**Phase 1 tests:**
```bash
pytest tests/test_face.py -v
```

## Roadmap / What's Next

- **Phase 5 — Web3.py Integration**: connect to Sepolia via `RPC_URL`,
  sign and send a `registerContent()` transaction using `PRIVATE_KEY`,
  and return the real transaction hash. Will clearly distinguish the
  **content hash** (SHA-256 fingerprint of the image) from the
  **transaction hash** (identifier of the blockchain transaction that
  stored it) — these are different things and the code/docs will keep
  them clearly separated.
- **Phase 6 — On-chain Verification**: read the stored record back
  from the contract (`getRecord` / `verifyContent`), recompute the
  current content hash, and compare the two to output `VERIFIED` or
  `NOT VERIFIED / CONTENT CHANGED`. This will always read the real
  blockchain — never simulated locally.
- **Phase 7 — Full Pipeline + CLI**: wire every phase together into
  `app/pipeline.py` and a single command:
  ```bash
  python main.py --image input/A.jpg
  ```
  producing the full step-by-step CLI output (detection → search →
  matching → hashing → registration → verification).
- **Phase 8 — Testing + Final Docs + Demo Prep**: blockchain tests
  (`test_blockchain.py`), a final expanded README covering all 24
  points from the original spec (install steps, wallet/testnet setup,
  contract deployment walkthrough, full example output, etc.), and
  polishing the CLI output for a clean screen-recorded demo.

## Known Limitations (Current)

- Reverse-image search results depend entirely on what SerpApi's
  underlying Google index has crawled — a photo with no public
  footprint will legitimately return few or zero results.
- Face similarity score is a **similarity metric, not proof of
  identity** — it should never be read as a certainty claim.
- SerpApi's free tier is capped at 250 searches/month; Cloudinary free
  tier has its own storage/bandwidth caps.
- The input image is briefly hosted on a public Cloudinary URL during
  search (auto-deleted immediately after) — see Privacy section below.
- Phases 5–8 are not yet implemented, so there is no working on-chain
  write/read path yet — `blockchain.py` and `main.py` don't exist yet.

## Privacy & Ethical Considerations

- This system does **not** attempt to identify a person's real-world
  identity from a name database — it only determines whether faces in
  public candidate images are visually/biometrically similar to the
  input face.
- No CAPTCHA, authentication, robots.txt, or access-control bypass is
  performed anywhere in the pipeline — only publicly accessible content
  from the search provider's own API is used.
- During search, the input image is briefly uploaded to a public URL
  (via the user's own Cloudinary account) so the search API can fetch
  it, then deleted immediately after the search completes.
- No personal information beyond what's necessary for matching is
  stored; the blockchain only ever stores a **hash** and a source
  reference — never the image itself.
- Face similarity scores are always labeled as such, never presented
  as a certainty of identity match.

## Troubleshooting

- **FutureWarning from InsightFace** (`rcond` / `estimate` deprecated)
  — harmless, comes from InsightFace's internal use of an older
  scikit-image API, not from this project's code. Safe to ignore.
- **`SEARCH_API_KEY is not set`** — check `.env` is in the project root
  and the key is pasted correctly with no extra quotes/spaces.
- **`Cloudinary credentials are missing`** — all three of
  `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`,
  `CLOUDINARY_API_SECRET` must be set.
- **`Search completed but found no candidates`** — this is normal,
  expected behavior for images with no public footprint, not a bug.
- **Deploying on "Remix VM" by mistake** — Remix's default environment
  is a local, in-browser simulated chain, not a real testnet. For a
  genuine deployment, the Environment dropdown in Remix's "Deploy & Run
  Transactions" tab must be set to **"Injected Provider - MetaMask"**,
  with MetaMask itself switched to the **Sepolia** network.