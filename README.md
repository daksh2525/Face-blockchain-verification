# Face Identification & Blockchain Verification

A hackathon project that combines **face recognition, genuine reverse-image search, SHA-256 content fingerprinting, and Ethereum blockchain verification** into a single CLI pipeline.

> **Status: All 8 phases complete.**  
> The complete pipeline runs end-to-end against real APIs and the Ethereum Sepolia testnet — with no hardcoded results and no simulated blockchain calls.

## Repository & Demo

- **GitHub Repository:** https://github.com/daksh2525/Face-blockchain-verification.git
- **Demo Video:** https://drive.google.com/file/d/1XqZlB9om5_Lfck9gS79cMxNQkKO_rFO_/view?usp=drive_link

## Table of Contents\*\*

1. [Project Overview](#project-overview)

2. [Problem Statement](#problem-statement)

3. [Architecture](#architecture)

4. [How Face Embeddings Work](#how-face-embeddings-work)

5. [How Candidate Images Are Compared](#how-candidate-images-are-compared)

6. [How Similarity Is Calculated](#how-similarity-is-calculated)

7. [Why SHA-256 Is Used](#why-sha-256-is-used)

8. [Content Hash vs Transaction Hash](#content-hash-vs-transaction-hash)

9. [Why Blockchain Is Used](#why-blockchain-is-used)

10. [Blockchain Architecture](#blockchain-architecture)

11. [Smart Contract](#smart-contract)

12. [Prerequisites & Accounts Needed](#prerequisites--accounts-needed)

13. [Installation](#installation)

14. [Environment Variables](#environment-variables)

15. [Wallet & Testnet Setup](#wallet--testnet-setup)

16. [Contract Deployment](#contract-deployment)

17. [Folder Structure](#folder-structure)

18. [How to Run](#how-to-run)

19. [Example Output](#example-output)

20. [Verification Process](#verification-process)

21. [Testing](#testing)

22. [Demo Recording Tips](#demo-recording-tips)

23. [Known Limitations](#known-limitations)

24. [Privacy & Ethical Considerations](#privacy--ethical-considerations)

25. [Troubleshooting](#troubleshooting)

---

**## Project Overview**

This project takes a face photo as input and:

1. Detects the face and generates a biometric embedding.

2. Performs a \***\*genuine\*\*** reverse-image search across the public web to

   find visually similar public content.

3. Downloads candidate images and compares faces to rank them by

   similarity.

4. Takes the best-matching public content and computes a \*\*SHA-256

   fingerprint\*\* of it.

5. Registers that fingerprint on the Ethereum Sepolia testnet via a

   smart contract.

6. Re-verifies the content by recomputing its hash and comparing it

   against what's stored on-chain — proving whether the content has

   been tampered with since registration.

No website is required — everything runs from a CLI, designed to be

easy to demo in a screen recording.

**## Problem Statement**

Reverse-image search tools can find where a face appears online, but

there's no simple, verifiable way to prove \*that specific piece of

content\* hasn't been altered since it was checked. This project solves

that by fingerprinting the matched content with SHA-256 and anchoring

that fingerprint immutably on a blockchain — so anyone can later verify

the content's integrity without trusting a central authority.

**## Architecture**

```

Input Face Image

      │

      ▼

Face Detection & Embedding (InsightFace)

      │

      ▼

Genuine Reverse-Image Search (SerpApi)

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

VERIFIED ✓ or NOT VERIFIED ✗

```

**## How Face Embeddings Work**

\***\*InsightFace\*\*** (`buffalo_l` model pack) detects faces in an image and

runs a recognition model over each detected face to produce a

512-dimensional numeric vector — the "embedding." Faces of the same

person, even in different photos/lighting/angles, produce embeddings

that are close together in this 512-dimensional space; different

people's faces produce embeddings that are far apart. The embedding is

L2-normalized so that comparing two faces reduces to a simple cosine

similarity calculation.

Embeddings \***\*do not encode identity/name\*\*** — they're purely a

geometric fingerprint of facial structure, used only for similarity

comparison.

**## How Candidate Images Are Compared**

For every candidate URL returned by the search API:

1. The image is downloaded (with size/type/timeout safety checks).

2. Face detection runs on the downloaded image.

3. If one or more faces are found, each is embedded and compared

   against the input face's embedding.

4. The highest-scoring face in that candidate is kept as the

   candidate's score.

5. Candidates that fail at any step (broken link, no face, decode

   failure) are marked as skipped with a reason, rather than crashing

   the pipeline.

**## How Similarity Is Calculated**

Cosine similarity between two normalized embeddings is a single dot

product, producing a value between -1 and 1 (in practice, for real

faces, roughly 0 to 1). This is scaled to a \*\*0–100 face similarity

score\*\*:

```

score = max(0, min(1, cosine_similarity)) * 100

```

This score is explicitly a \*\*similarity metric, not a probability of

identity\*\*. It is labeled as "face similarity score" everywhere in the

codebase and output — never presented as certainty that two images

show the same person.

**## Why SHA-256 Is Used**

SHA-256 is a cryptographic hash function with three properties this

project relies on:

- \***\*Deterministic\*\***: identical input bytes always produce the identical

  256-bit output hash.

- \***\*Avalanche effect\*\***: changing even a single byte of the input

  produces a completely different, unpredictable hash.

- \***\*One-way\*\***: the hash cannot be reversed to recover the original

  content.

This makes SHA-256 ideal as a compact "fingerprint" for tamper

detection: storing the hash on-chain lets anyone later recompute the

hash of a piece of content and compare it, without ever needing to

store the (potentially large) content itself on the blockchain.

**## Content Hash vs Transaction Hash**

These are two distinct hashes and this project keeps them clearly

separated everywhere in code and output:

| | Content Hash | Transaction Hash |

|---|---|---|

| \***\*What it identifies\*\*** | The actual off-chain content (the matched image) | The blockchain transaction that registered the content hash |

| \***\*How it's produced\*\*** | SHA-256 of the image bytes | Generated by the blockchain when the transaction is submitted |

| \***\*Where it's stored\*\*** | Inside the smart contract's storage (as the mapping key) | On the blockchain's transaction log |

| \***\*Example\*\*** | `a55543d885de72d8ee01e3cf...` | `0xb4671cc8cd181d1197...` |

Confusing the two would mean, for example, checking whether a

**transaction** exists instead of whether the **content** is registered —

this project always uses the content hash for `verifyContent` /

`getRecord` lookups, and only displays the transaction hash as a

receipt for the registration transaction itself.

**## Why Blockchain Is Used**

A central database could also store "hash X was seen on date Y," but

that requires trusting whoever controls the database — records could

be silently altered or deleted. Writing the content hash to a public

blockchain (Ethereum Sepolia testnet here) means:

- The record, once confirmed, cannot be altered or deleted by anyone,

  including the original submitter.

- Anyone can independently verify the record by querying the chain

  directly — no API key or permission needed to **read** it.

- The registration is timestamped and tied to the submitting wallet

  address automatically by the chain itself.

**## Blockchain Architecture**

- \***\*Network\*\***: Ethereum Sepolia testnet (a public, free-to-use test

  network — no real funds involved).

- \***\*Client library\*\***: `web3.py`, connecting via an RPC endpoint

  (Infura/Alchemy).

- \***\*Signing\*\***: transactions are signed locally using a wallet private

  key before being broadcast — the private key never leaves the local

  machine/process.

- \***\*Contract\*\***: a single Solidity contract (`ContentVerification.sol`)

  deployed once; all registrations are transactions against this one

  contract address.

**## Smart Contract**

`contracts/ContentVerification.sol`:

- `registerContent(bytes32 contentHash, string sourceReference)` —

  stores a new content hash on-chain. Reverts if this exact hash is

  already registered (prevents duplicate registrations).

- `verifyContent(bytes32 contentHash) → bool` — fast existence check,

  free to call (read-only).

- `getRecord(bytes32 contentHash) → (exists, submitter, timestamp,

  sourceReference)` — full record lookup, free to call.

- `ContentRegistered` event — emitted on every successful registration,

  for easy off-chain indexing/logging.

Deployed via Remix IDE to Sepolia using MetaMask.

**## Prerequisites & Accounts Needed**

- \***\*Python 3.9–3.11\*\*** (tested on 3.11.16)

- \***\*SerpApi account\*\*** (free, no credit card, 250 searches/month):

  [serpapi.com](https://serpapi.com)

- \***\*Cloudinary account\*\*** (free tier): [cloudinary.com](https://cloudinary.com)

  — used to briefly host the input image at a public URL so SerpApi can

  fetch it (auto-deleted right after each search)

- \***\*MetaMask\*\*** browser extension with a \***\*Sepolia testnet\*\*** wallet

  holding free test ETH (from a faucet)

- \***\*An RPC endpoint\*\*** for Sepolia — free from

  [Infura](https://infura.io) or [Alchemy](https://alchemy.com)

**## Installation**

```bash

git clone https://github.com/daksh2525/Face-blockchain-verification.git

cd face-blockchain-verification

python -m venv .venv

source .venv/bin/activate       # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env

# then fill in .env (see Environment Variables below)

```

First run auto-downloads the InsightFace `buffalo_l` model pack

(\~350MB, one-time, needs internet).

**## Environment Variables**

```ini

# --- Face matching ---

SIMILARITY_THRESHOLD=60.0        # 0-100 scale; candidate must score >= this to count as a "match"

FACE_SELECTION_STRATEGY=largest  # "largest" or "most_confident"

INSIGHTFACE_MODEL_NAME=buffalo_l

INSIGHTFACE_PROVIDER=CPUExecutionProvider

# --- Search ---

SEARCH_PROVIDER=serpapi

SEARCH_API_KEY=                  # your SerpApi key

MAX_SEARCH_RESULTS=10

# --- Temporary image hosting (for SerpApi's URL-based search) ---

IMAGE_HOST_PROVIDER=cloudinary

CLOUDINARY_CLOUD_NAME=

CLOUDINARY_API_KEY=

CLOUDINARY_API_SECRET=

# --- Blockchain ---

RPC_URL=                         # Sepolia RPC endpoint (Infura/Alchemy)

PRIVATE_KEY=                     # wallet private key — NEVER share or commit this

CONTRACT_ADDRESS=                # from deploying ContentVerification.sol

```

\***\*Never commit `.env`. Never hardcode any key directly in code.\*\***

`.gitignore` already excludes `.env`.

**## Wallet & Testnet Setup**

1. Install [MetaMask](https://metamask.io) and create a wallet.

2. Enable test networks (Settings → Advanced → "Show test networks")

   and switch to \***\*Sepolia\*\***.

3. Get free Sepolia ETH from a faucet, e.g.:

   - `https://cloud.google.com/application/web3/faucet/ethereum/sepolia`

   - `https://faucet.quicknode.com/ethereum/sepolia`

   - `https://www.alchemy.com/faucets/ethereum-sepolia`

4. Confirm the balance shows up in MetaMask before proceeding.

5. Export the wallet's private key (MetaMask → Account details → Show

   private key) and put it in `.env` as `PRIVATE_KEY` — \*\*testnet

   wallet only, never a wallet holding real funds\*\*.

**## Contract Deployment**

1. Open [Remix IDE](https://remix.ethereum.org).

2. Create `contracts/ContentVerification.sol` and paste in the

   contract source.

3. Solidity Compiler tab → select version 0.8.19+ → Compile.

4. Deploy & Run Transactions tab → Environment: \*\*"Injected Provider -

   MetaMask"\*\* (not "Remix VM" — that's a local simulation, not a real

   chain) → confirm MetaMask is on Sepolia with a funded account.

5. Click \***\*Deploy\*\***, confirm the transaction in MetaMask.

6. Copy the deployed contract address into `.env` as

   `CONTRACT_ADDRESS`.

**## Folder Structure**

```

face-blockchain-verification/

│

├── app/

│   ├── __init__.py

│   ├── config.py               # env-var-driven settings

│   ├── face_detection.py       # Phase 1: detect + select face

│   ├── face_embedding.py       # Phase 1: normalize + similarity scoring

│   ├── web_search.py           # Phase 2: SerpApi reverse-image search

│   ├── candidate_matcher.py    # Phase 2: download candidates, rank by similarity

│   ├── image_hosting.py        # Phase 2: temp public hosting (Cloudinary)

│   ├── hashing.py              # Phase 3: SHA-256 content fingerprinting

│   ├── blockchain_client.py    # Phase 5/6: web3.py integration + verification

│   └── pipeline.py             # Phase 7: full pipeline orchestration

│

├── contracts/

│   ├── ContentVerification.sol # Phase 4: the on-chain registry contract

│   └── contract_abi.json       # ABI used by blockchain_client.py

│

├── tests/

│   ├── __init__.py

│   ├── test_face.py            # Phase 1 tests

│   ├── test_hashing.py         # Phase 3 tests

│   └── test_blockchain.py      # Phase 8 tests (mocked)

│

├── input/                      # put your input face images here

├── data/                       # downloaded best-match images + local registration log

│

├── main.py                     # Phase 7: CLI entrypoint

├── requirements.txt

├── .env.example

├── .gitignore

└── README.md

```

**## How to Run**

\***\*Full pipeline (one command):\*\***

```bash

python main.py --image input/your_photo.jpg

```

\***\*Individual phase testing:\*\***

```bash

# Phase 1 tests

pytest tests/test_face.py -v

# Phase 2 only (search + matching)

python manual_test_phase2.py input/your_photo.jpg

# Phase 3 tests

pytest tests/test_hashing.py -v

# Phase 5/6 manually (register + verify a specific file)

python app/blockchain_client.py register input/your_photo.jpg "a source note"

python app/blockchain_client.py verify_file input/your_photo.jpg

# Phase 8 blockchain tests (mocked, no real network needed)

pytest tests/test_blockchain.py -v

```

**## Example Output**

Real output from a full pipeline run:

```

\========================================

FACE IDENTIFICATION & BLOCKCHAIN VERIFY

\========================================

[1] Loading image...

Image loaded

[2] Detecting face...

Face detected (confidence=0.831)

[3] Generating embedding...

Embedding generated

[4] Searching web...

Search completed

Candidate results found: 8

[5] Comparing candidate faces...

Candidate 1 -> 89.06%

Candidate 2 -> 85.57%

Candidate 3 -> 77.51%

Candidate 4 -> 75.49%

Candidate 5 -> 68.63%

Candidate 6 -> 66.35%

Candidate 7 -> 53.2%

Candidate 8 -> 45.43%

[6] Best match found

Match candidate selected

Source:

https://www.reddit.com/r/onepiecetheories/comments/.../

Face similarity:

89.06%

[7] Generating SHA-256 fingerprint...

Content hash generated

Content Hash:

a55543d885de72d8ee01e3cf359dd6e886445af36a58b62542281e5a6d8f5179

[8] Registering hash on blockchain...

Transaction submitted

Transaction Hash:

0xb4671cc8cd181d119740ad7df0e97706c17bdf36849a247986f0dd9913052480

[9] Reading blockchain record...

Blockchain record retrieved

[10] Verifying content...

Current Hash:

a55543d885de72d8ee01e3cf359dd6e886445af36a58b62542281e5a6d8f5179

Blockchain Hash:

a55543d885de72d8ee01e3cf359dd6e886445af36a58b62542281e5a6d8f5179

\========================================

VERIFICATION RESULT: VERIFIED ✓

\========================================

```

**## Verification Process**

```

Current/Downloaded Content

      │ SHA-256

      ▼

Current Content Hash

      │

      ▼

Read stored hash from blockchain (getRecord)

      │

      ▼

Compare hashes

      │

      ▼

VERIFIED (hashes match, record exists on-chain)

   or

NOT VERIFIED / CONTENT CHANGED (no matching on-chain record)

```

This is a \***\*real on-chain read every time\*\*** — never a locally cached

or simulated result. Registering content twice with the same hash is

automatically prevented (and skipped, not re-charged) by checking

`verifyContent()` before attempting registration.

**## Testing**

```bash

pytest tests/ -v

```

Covers:

- SHA-256 determinism (same bytes → same hash; modified bytes →

  different hash)

- Face embedding generation and normalization

- Face similarity score calculation

- Blockchain registration/retrieval/verification logic (mocked, so

  these run without spending real gas or needing network access)

**## Demo Recording Tips**

- Run `python main.py --image input/your_photo.jpg` on a photo with a

  known public presence for a guaranteed non-empty search result.

- Have the Sepolia Etherscan page

  (`https://sepolia.etherscan.io/tx/<transaction_hash>`) ready in a

  second tab to show the transaction confirming live, for extra

  credibility.

- Consider running once beforehand so the InsightFace model is already

  cached locally (avoids a \~1-2 min download live on camera).

- The `FutureWarning` lines from InsightFace's internal dependencies

  are harmless; add `warnings.filterwarnings("ignore",

  category=FutureWarning)`near the top of`app/pipeline.py` to hide

  them from the recording if desired.

**## Known Limitations**

- Reverse-image search results depend entirely on what SerpApi's

  underlying Google index has crawled — a photo with no public

  footprint will legitimately return few or zero results.

- Face similarity score is a \*\*similarity metric, not proof of

  identity\*\* — never treat it as a certainty claim.

- SerpApi's free tier is capped at 250 searches/month; Cloudinary free

  tier has its own storage/bandwidth caps.

- The input image is briefly hosted on a public Cloudinary URL during

  search (auto-deleted immediately after).

- Sepolia is a testnet — this project intentionally does not use

  Ethereum mainnet, so registrations have no real-world monetary cost

  or permanence guarantee beyond the testnet's own lifetime.

**## Privacy & Ethical Considerations**

- This system does \***\*not\*\*** attempt to identify a person's real-world

  identity from a name database — it only determines whether faces in

  public candidate images are visually/biometrically similar to the

  input face.

- No CAPTCHA, authentication, robots.txt, or access-control bypass is

  performed anywhere in the pipeline — only publicly accessible content

  from the search provider's own API is used.

- During search, the input image is briefly uploaded to a public URL

  (via the user's own Cloudinary account) so the search API can fetch

  it, then deleted immediately after the search completes.

- The blockchain only ever stores a \***\*hash\*\*** and a source reference —

  never the image itself.

- Face similarity scores are always labeled as such, never presented

  as a certainty of identity match.

**## Troubleshooting**

- \***\*FutureWarning from InsightFace\*\*** — harmless, from InsightFace's

  internal use of an older scikit-image API. Safe to ignore or

  suppress (see Demo Recording Tips).

- \***\*`SEARCH_API_KEY is not set`\*\*** — check `.env` is in the project root

  and the key has no extra quotes/spaces.

- \***\*`Cloudinary credentials are missing`\*\*** — all three of

  `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`,

  `CLOUDINARY_API_SECRET` must be set.

- \***\*`Python-dotenv could not parse statement starting at line 1`\*\*** —

  usually a formatting issue on the first line of `.env` (stray

  character/space); harmless if the rest of the values still load

  correctly, but worth double-checking.

- \***\*Deploying on "Remix VM" by mistake\*\*** — this is a local, in-browser

  simulated chain, not a real testnet. Use \*\*"Injected Provider -

  MetaMask"\*\* with MetaMask switched to Sepolia for a genuine

  deployment.

- \***\*`ERROR: Content hash already registered`\*\*** — expected behavior if

  you run the pipeline twice on content that hasn't changed; the

  pipeline detects this and skips re-registering automatically.
