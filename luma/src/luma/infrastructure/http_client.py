"""Async HTTP client with retry logic."""

import asyncio
import logging
from typing import Optional, Any, Dict

import httpx

logger = logging.getLogger(__name__)


class HttpClient:
    """Async HTTP client with retry and timeout support."""

    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        base_url: Optional[str] = None,
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.base_url = base_url
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            timeout = httpx.Timeout(self.timeout)
            limits = httpx.Limits(max_keepalive_connections=20, max_connections=100)
            self._client = httpx.AsyncClient(
                timeout=timeout,
                limits=limits,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        retry_on: Optional[list[int]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Make GET request with retry logic.

        Args:
            url: Request URL
            params: Query parameters
            headers: Request headers
            retry_on: HTTP status codes to retry on

        Returns:
            JSON response data or None if failed
        """
        if retry_on is None:
            retry_on = [429, 500, 502, 503, 504]

        full_url = url if self.base_url is None else f"{self.base_url}{url}"

        for attempt in range(self.max_retries):
            try:
                client = await self.get_client()
                response = await client.get(full_url, params=params, headers=headers)

                if response.status_code == 404:
                    return None

                if response.status_code in retry_on:
                    wait_time = self.retry_delay * (2**attempt)
                    logger.warning(
                        f"Got status {response.status_code}, "
                        f"retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                    continue

                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                if e.response.status_code in retry_on and attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2**attempt)
                    logger.warning(
                        f"HTTP error {e.response.status_code}, "
                        f"retrying in {wait_time}s"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                logger.error(f"HTTP error: {e}")
                return None

            except httpx.TimeoutException:
                logger.warning(f"Timeout on attempt {attempt + 1}/{self.max_retries}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    logger.error("Max retries reached due to timeout")
                    return None

            except Exception as e:
                logger.error(f"Request error: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    return None

        return None

    async def get_batch(
        self,
        urls: list[str],
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        concurrency: int = 5,
    ) -> list[Optional[Dict[str, Any]]]:
        """Make multiple GET requests concurrently.

        Args:
            urls: List of URLs to fetch
            params: Query parameters
            headers: Request headers
            concurrency: Max concurrent requests

        Returns:
            List of JSON responses in same order as URLs
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_with_semaphore(url: str) -> Optional[Dict[str, Any]]:
            async with semaphore:
                return await self.get(url, params=params, headers=headers)

        tasks = [fetch_with_semaphore(url) for url in urls]
        return await asyncio.gather(*tasks)


class JikanClient(HttpClient):
    """HTTP client for Jikan API (MAL API)."""

    BASE_URL = "https://api.jikan.moe/v4"

    def __init__(self, timeout: float = 30.0, max_retries: int = 3):
        super().__init__(
            base_url=self.BASE_URL,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=2.0,
        )

    async def get_anime(self, anime_id: int) -> Optional[Dict[str, Any]]:
        """Get anime by MAL ID.

        Args:
            anime_id: MyAnimeList ID

        Returns:
            Anime data dict or None
        """
        return await self.get(f"/anime/{anime_id}")

    async def get_anime_batch(self, anime_ids: list[int]) -> list[Optional[Dict[str, Any]]]:
        """Get multiple anime by IDs.

        Args:
            anime_ids: List of MyAnimeList IDs

        Returns:
            List of anime data dicts
        """
        urls = [f"/anime/{aid}" for aid in anime_ids]
        return await self.get_batch(urls, concurrency=3)
