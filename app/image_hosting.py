"""
image_hosting.py

Some search providers (e.g. SerpApi) need a publicly reachable image URL
rather than raw bytes. This module uploads the input image to a temporary
public location so it can be searched, then cleans it up immediately after.

Two backends are supported:

  - "cloudinary" (default): uses the user's own Cloudinary account.
    Preferred because it's an authenticated account (not an anonymous
    public host) and we can delete the image immediately after the
    search completes, rather than waiting for a fixed expiry window.

  - "litterbox": catbox.moe's anonymous temporary-file service. No
    account needed, but the image sits on an anonymous public URL for
    a fixed minimum period (shortest supported: 1 hour).

Whichever backend is used, callers get a TempImageHandle with a `.url`
and a `.cleanup()` method — always call cleanup() once the search is
done, ideally in a `finally` block.
"""

import logging
from dataclasses import dataclass
from typing import Callable, Optional

import requests

from app.config import config

logger = logging.getLogger("image_hosting")

LITTERBOX_API_URL = "https://litterbox.catbox.moe/resources/internals/api.php"


class ImageHostingError(Exception):
    """Raised when the temporary image upload (or cleanup) fails."""
    pass


@dataclass
class TempImageHandle:
    url: str
    cleanup: Callable[[], None]


# --- Cloudinary backend -----------------------------------------------------

def _upload_via_cloudinary(image_path: str) -> TempImageHandle:
    try:
        import cloudinary
        import cloudinary.uploader
    except ImportError:
        raise ImageHostingError(
            "The 'cloudinary' package is not installed. Run: pip install cloudinary"
        )

    if not (config.CLOUDINARY_CLOUD_NAME and config.CLOUDINARY_API_KEY and config.CLOUDINARY_API_SECRET):
        raise ImageHostingError(
            "Cloudinary credentials are missing. Set CLOUDINARY_CLOUD_NAME, "
            "CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET in your .env file."
        )

    cloudinary.config(
        cloud_name=config.CLOUDINARY_CLOUD_NAME,
        api_key=config.CLOUDINARY_API_KEY,
        api_secret=config.CLOUDINARY_API_SECRET,
        secure=True,
    )

    try:
        result = cloudinary.uploader.upload(
            image_path,
            folder="face-blockchain-verification/tmp",
            overwrite=True,
            unique_filename=True,
        )
    except Exception as e:  # cloudinary raises its own exception types
        raise ImageHostingError(f"Cloudinary upload failed: {e}")

    url = result.get("secure_url")
    public_id = result.get("public_id")
    if not url or not public_id:
        raise ImageHostingError("Cloudinary upload succeeded but response was missing expected fields.")

    def _cleanup():
        try:
            cloudinary.uploader.destroy(public_id)
            logger.info("Temporary Cloudinary image deleted.")
        except Exception as e:
            # Don't let cleanup failure crash the pipeline; just warn.
            logger.warning(f"Could not delete temporary Cloudinary image ({public_id}): {e}")

    logger.info("Temporary image uploaded to Cloudinary.")
    return TempImageHandle(url=url, cleanup=_cleanup)


# --- Litterbox (catbox.moe) backend -----------------------------------------

def _upload_via_litterbox(image_path: str, expiry: str = "1h") -> TempImageHandle:
    if expiry not in ("1h", "12h", "24h", "72h"):
        raise ValueError("expiry must be one of '1h', '12h', '24h', '72h'")

    try:
        with open(image_path, "rb") as f:
            files = {"fileToUpload": f}
            data = {"reqtype": "fileupload", "time": expiry}
            resp = requests.post(LITTERBOX_API_URL, data=data, files=files, timeout=20)
    except OSError as e:
        raise ImageHostingError(f"Could not read image file: {e}")
    except requests.RequestException as e:
        raise ImageHostingError(f"Upload request failed: {e}")

    if resp.status_code != 200:
        raise ImageHostingError(f"Litterbox returned status {resp.status_code}")

    url = resp.text.strip()
    if not url.startswith("http"):
        raise ImageHostingError(f"Unexpected response from Litterbox: {url[:200]}")

    def _cleanup():
        # Litterbox has no delete API; it just relies on the fixed expiry.
        logger.info(f"Temporary Litterbox image will auto-expire in {expiry} (no manual delete available).")

    logger.info(f"Temporary image uploaded to Litterbox (expires in {expiry}).")
    return TempImageHandle(url=url, cleanup=_cleanup)


# --- Public entry point ------------------------------------------------------

def upload_temp_image(image_path: str, provider: Optional[str] = None) -> TempImageHandle:
    """
    Uploads a local image to a temporary public host and returns a
    TempImageHandle. Always call handle.cleanup() once done with the URL.
    """
    provider = (provider or config.IMAGE_HOST_PROVIDER or "cloudinary").lower()

    if provider == "cloudinary":
        return _upload_via_cloudinary(image_path)
    if provider == "litterbox":
        return _upload_via_litterbox(image_path)

    raise ImageHostingError(f"Unknown IMAGE_HOST_PROVIDER '{provider}'.")