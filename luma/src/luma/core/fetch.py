"""Data fetching from Jikan API."""

import asyncio
import logging
from typing import Optional, AsyncIterator

from luma.infrastructure.http_client import JikanClient
from luma.infrastructure.rate_limiter import RateLimiter
from luma.models.anime import Anime

logger = logging.getLogger(__name__)


class AnimeFetcher:
    """Fetch anime data from Jikan API."""

    JIKAN_API_RATE = 3.0  # requests per second

    def __init__(
        self,
        rate_limiter: Optional[RateLimiter] = None,
        client: Optional[JikanClient] = None,
    ):
        self.rate_limiter = rate_limiter or RateLimiter(rate=self.JIKAN_API_RATE)
        self.client = client or JikanClient()

    async def fetch_anime(self, anime_id: int) -> Optional[Anime]:
        """Fetch a single anime by MAL ID.

        Args:
            anime_id: MyAnimeList ID

        Returns:
            Anime object or None if not found
        """
        async with self.rate_limiter:
            try:
                data = await self.client.get_anime(anime_id)

                if data is None or "data" not in data:
                    logger.debug(f"No data found for anime ID {anime_id}")
                    return None

                return self._parse_anime(data["data"])

            except Exception as e:
                logger.error(f"Error fetching anime {anime_id}: {e}")
                return None

    async def fetch_anime_batch(
        self,
        anime_ids: list[int],
        batch_size: int = 10,
    ) -> list[Optional[Anime]]:
        """Fetch multiple anime in batches.

        Args:
            anime_ids: List of MAL IDs
            batch_size: Batch size for processing

        Returns:
            List of Anime objects (None for failed fetches)
        """
        results: list[Optional[Anime]] = []

        for i in range(0, len(anime_ids), batch_size):
            batch = anime_ids[i:i + batch_size]

            # Fetch batch concurrently with rate limiting
            tasks = [self.fetch_anime(aid) for aid in batch]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)

            logger.debug(
                f"Fetched batch {i // batch_size + 1}: "
                f"{sum(1 for r in batch_results if r is not None)}/{len(batch)} successful"
            )

        return results

    async def fetch_anime_range(
        self,
        start_id: int,
        end_id: int,
        batch_size: int = 10,
    ) -> AsyncIterator[Anime]:
        """Fetch anime in a range as async iterator.

        Args:
            start_id: Starting MAL ID (inclusive)
            end_id: Ending MAL ID (inclusive)
            batch_size: Batch size for processing

        Yields:
            Anime objects
        """
        anime_ids = list(range(start_id, end_id + 1))

        for anime in await self.fetch_anime_batch(anime_ids, batch_size):
            if anime is not None:
                yield anime

    def _parse_anime(self, data: dict) -> Optional[Anime]:
        """Parse API response into Anime model.

        Args:
            data: Raw API data

        Returns:
            Anime object or None if parsing fails
        """
        try:
            from luma.models.anime import AnimeType, AnimeSource

            # Extract titles
            titles = data.get("titles", [])
            title_japanese = None
            title_english = None

            for t in titles:
                if t.get("type") == "Japanese":
                    title_japanese = t.get("title")
                elif t.get("type") == "English":
                    title_english = t.get("title")

            # Extract studios
            studios_data = data.get("studios", [])
            studios = [s.get("name", "") for s in studios_data if s.get("name")]

            # Extract genres
            genres_data = data.get("genres", [])
            genres = [g.get("name", "") for g in genres_data if g.get("name")]

            # Parse type
            type_str = data.get("type")
            try:
                anime_type = AnimeType(type_str) if type_str else AnimeType.UNKNOWN
            except ValueError:
                anime_type = AnimeType.UNKNOWN

            # Parse source
            source_str = data.get("source")
            try:
                anime_source = AnimeSource(source_str) if source_str else AnimeSource.UNKNOWN
            except ValueError:
                anime_source = AnimeSource.UNKNOWN

            # Extract year from aired dates
            year = None
            aired = data.get("aired", {})
            if aired and aired.get("from"):
                from_year = aired["from"][:4] if isinstance(aired["from"], str) else None
                if from_year and from_year.isdigit():
                    year = int(from_year)

            return Anime(
                mal_id=data.get("mal_id"),
                title=data.get("title") or "Unknown",
                title_japanese=title_japanese,
                title_english=title_english,
                titles=titles,
                episodes=data.get("episodes"),
                score=data.get("score"),
                year=year,
                type=anime_type,
                source=anime_source,
                studios=studios,
                genres=genres,
                synopsis=data.get("synopsis"),
                aired=aired,
                duration=data.get("duration"),
                rating=data.get("rating"),
                url=data.get("url"),
                images=data.get("images"),
            )

        except Exception as e:
            logger.error(f"Error parsing anime data: {e}")
            return None

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.close()
