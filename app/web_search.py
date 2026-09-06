"""
web_search.py

Genuine reverse-image search: given an input image, find real public
candidate images/pages that may contain a visually similar face.

Design: a small abstract interface (SearchProvider) so the concrete
provider can be swapped out later without touching the rest of the
pipeline. Default implementation uses Google Cloud Vision's Web
Detection feature via a simple REST call (API key auth, no OAuth/service
account required).

This module does NOT bypass CAPTCHAs, authentication, robots.txt, or
private/access-controlled content. It only surfaces what the search
provider's public API returns.
"""

import base64
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

import requests

from app.config import config
from app.image_hosting import upload_temp_image, ImageHostingError

logger = logging.getLogger("web_search")

GOOGLE_VISION_ENDPOINT = "https://vision.googleapis.com/v1/images:annotate"


class SearchProviderError(Exception):
    """Raised when the search provider fails (bad key, quota, network, etc.)."""
    pass


class NoSearchResultsError(Exception):
    """Raised when a search completes successfully but returns zero candidates."""
    pass


@dataclass
class SearchResult:
    source_url: str                  # page the image/content was found on
    image_url: Optional[str] = None  # direct URL of the candidate image, if available
    title: Optional[str] = None      # page/result title, if available
    match_type: Optional[str] = None  # e.g. "full_match", "partial_match", "visually_similar"


class SearchProvider(ABC):
    """Abstract interface every search provider must implement."""

    @abstractmethod
    def search_by_image(self, image_path: str, max_results: int = 10) -> List[SearchResult]:
        """
        Given a local image path, returns a list of SearchResult candidates
        found via a genuine web/image search. Raises SearchProviderError on
        failure, NoSearchResultsError if the search succeeds with 0 results.
        """
        raise NotImplementedError


class GoogleVisionWebDetectionProvider(SearchProvider):
    """
    Uses Google Cloud Vision API's WEB_DETECTION feature to perform a real
    reverse-image search across the public web.

    Docs: https://cloud.google.com/vision/docs/detecting-web
    Requires: SEARCH_API_KEY env var (a Google Cloud API key with the
    Cloud Vision API enabled on its project).
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.SEARCH_API_KEY
        if not self.api_key:
            raise SearchProviderError(
                "SEARCH_API_KEY is not set. Set it in your .env file to a "
                "Google Cloud API key with the Cloud Vision API enabled."
            )

    def _encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def search_by_image(self, image_path: str, max_results: int = 10) -> List[SearchResult]:
        try:
            image_b64 = self._encode_image(image_path)
        except OSError as e:
            raise SearchProviderError(f"Could not read image for search: {e}")

        payload = {
            "requests": [
                {
                    "image": {"content": image_b64},
                    "features": [{"type": "WEB_DETECTION", "maxResults": max_results}],
                }
            ]
        }

        try:
            resp = requests.post(
                GOOGLE_VISION_ENDPOINT,
                params={"key": self.api_key},
                json=payload,
                timeout=20,
            )
        except requests.RequestException as e:
            raise SearchProviderError(f"Search request failed (network error): {e}")

        if resp.status_code != 200:
            # Never leak the API key value into logs/errors
            raise SearchProviderError(
                f"Search API returned status {resp.status_code}: {resp.text[:300]}"
            )

        data = resp.json()
        try:
            web_detection = data["responses"][0].get("webDetection", {})
        except (KeyError, IndexError) as e:
            raise SearchProviderError(f"Unexpected search API response shape: {e}")

        if "error" in data["responses"][0]:
            raise SearchProviderError(f"Search API error: {data['responses'][0]['error']}")

        results: List[SearchResult] = []

        # Pages that contain a matching image (best signal: real page + real image)
        for page in web_detection.get("pagesWithMatchingImages", []):
            page_url = page.get("url")
            if not page_url:
                continue
            # A page can list full/partial matching image URLs found on it
            image_urls = [img.get("url") for img in page.get("fullMatchingImages", [])] or \
                         [img.get("url") for img in page.get("partialMatchingImages", [])]
            results.append(SearchResult(
                source_url=page_url,
                image_url=image_urls[0] if image_urls else None,
                title=page.get("pageTitle"),
                match_type="page_with_matching_image",
            ))

        # Visually similar images (weaker signal, but still genuine candidates)
        for img in web_detection.get("visuallySimilarImages", []):
            img_url = img.get("url")
            if not img_url:
                continue
            results.append(SearchResult(
                source_url=img_url,
                image_url=img_url,
                title=None,
                match_type="visually_similar",
            ))

        results = results[:max_results]

        if not results:
            raise NoSearchResultsError(
                "Search completed successfully but returned no candidate results."
            )

        logger.info(f"Search returned {len(results)} candidate result(s).")
        return results


class SerpApiReverseImageProvider(SearchProvider):
    """
    Uses SerpApi's Google Reverse Image engine to perform a real
    reverse-image search across the public web.

    Docs: https://serpapi.com/google-reverse-image
    Requires: SEARCH_API_KEY env var (a SerpApi API key).

    Note: SerpApi requires a public image URL rather than raw bytes, so
    this provider first uploads the input image to a short-lived
    temporary host (see image_hosting.py) before searching.
    """

    SERPAPI_ENDPOINT = "https://serpapi.com/search"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.SEARCH_API_KEY
        if not self.api_key:
            raise SearchProviderError(
                "SEARCH_API_KEY is not set. Set it in your .env file to a "
                "SerpApi API key."
            )

    def search_by_image(self, image_path: str, max_results: int = 10) -> List[SearchResult]:
        image_handle = None
        try:
            image_handle = upload_temp_image(image_path)
        except ImageHostingError as e:
            raise SearchProviderError(f"Could not prepare image for search: {e}")

        try:
            params = {
                "engine": "google_reverse_image",
                "image_url": image_handle.url,
                "api_key": self.api_key,
            }

            try:
                resp = requests.get(self.SERPAPI_ENDPOINT, params=params, timeout=20)
            except requests.RequestException as e:
                raise SearchProviderError(f"Search request failed (network error): {e}")

            if resp.status_code != 200:
                raise SearchProviderError(
                    f"Search API returned status {resp.status_code}: {resp.text[:300]}"
                )

            data = resp.json()

            if "error" in data:
                raise SearchProviderError(f"Search API error: {data['error']}")

            results: List[SearchResult] = []
            for item in data.get("image_results", []):
                source_url = item.get("link")
                if not source_url:
                    continue
                image_url = item.get("original") or item.get("thumbnail")
                results.append(SearchResult(
                    source_url=source_url,
                    image_url=image_url,
                    title=item.get("title"),
                    match_type="google_reverse_image",
                ))

            results = results[:max_results]

            if not results:
                raise NoSearchResultsError(
                    "Search completed successfully but returned no candidate results."
                )

            logger.info(f"Search returned {len(results)} candidate result(s).")
            return results
        finally:
            # Always clean up the temporary public copy of the input image,
            # even if the search failed partway through.
            if image_handle is not None:
                image_handle.cleanup()


def get_search_provider() -> SearchProvider:
    """
    Factory: returns the configured search provider.
    'serpapi' (default) uses SerpApi's Google Reverse Image engine.
    'google_vision' uses Google Cloud Vision's Web Detection feature.
    This is the seam where a new provider can be added later.
    """
    provider_name = (config.SEARCH_PROVIDER or "serpapi").lower()

    if provider_name in ("serpapi", "serp_api"):
        return SerpApiReverseImageProvider()
    if provider_name in ("google_vision", "google"):
        return GoogleVisionWebDetectionProvider()

    raise SearchProviderError(f"Unknown SEARCH_PROVIDER '{provider_name}'.")