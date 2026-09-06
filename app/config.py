"""
config.py

Centralized configuration loaded from environment variables (.env file).
No secrets are hardcoded anywhere in this module.
"""

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv is optional at this phase; real env vars still work.
    pass


@dataclass(frozen=True)
class Config:
    # --- Face matching ---
    # Similarity threshold (0-100 scale) above which a candidate is considered a "match".
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "60.0"))

    # Which face to use if multiple are detected in the INPUT image: "largest" or "most_confident"
    FACE_SELECTION_STRATEGY: str = os.getenv("FACE_SELECTION_STRATEGY", "largest")

    # InsightFace model pack name (downloaded automatically on first run)
    INSIGHTFACE_MODEL_NAME: str = os.getenv("INSIGHTFACE_MODEL_NAME", "buffalo_l")

    # "CPU" or "CUDA" — CPU is the safe default for a hackathon laptop demo
    INSIGHTFACE_PROVIDER: str = os.getenv("INSIGHTFACE_PROVIDER", "CPUExecutionProvider")

    # --- Search (used in Phase 2, declared now so config is stable) ---
    SEARCH_API_KEY: str = os.getenv("SEARCH_API_KEY", "")
    SEARCH_PROVIDER: str = os.getenv("SEARCH_PROVIDER", "")
    MAX_SEARCH_RESULTS: int = int(os.getenv("MAX_SEARCH_RESULTS", "10"))

    # --- Temporary image hosting (needed so URL-based search APIs like
    # SerpApi can fetch the input image) ---
    IMAGE_HOST_PROVIDER: str = os.getenv("IMAGE_HOST_PROVIDER", "cloudinary")
    CLOUDINARY_CLOUD_NAME: str = os.getenv("CLOUDINARY_CLOUD_NAME", "")
    CLOUDINARY_API_KEY: str = os.getenv("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET: str = os.getenv("CLOUDINARY_API_SECRET", "")

    # --- Blockchain (used in Phase 5/6, declared now so config is stable) ---
    RPC_URL: str = os.getenv("RPC_URL", "")
    PRIVATE_KEY: str = os.getenv("PRIVATE_KEY", "")
    CONTRACT_ADDRESS: str = os.getenv("CONTRACT_ADDRESS", "")


config = Config()