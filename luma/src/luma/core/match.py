"""Wikidata matching for anime."""

import logging

from luma.infrastructure.http_client import HttpClient
from luma.models.anime import Anime
from luma.models.match import MatchMethod, MatchResult

logger = logging.getLogger(__name__)

# Wikidata properties
PROP_MAL_ID = "P5419"  # MyAnimeList ID property
PROP_INSTANCE_OF = "P31"  # Instance of
PROP_TITLE = "P1476"  # Title
PROP_PUB_DATE = "P577"  # Publication date
PROP_EPISODES = "P1113"  # Number of episodes


class WikidataMatcher:
    """Matcher for finding anime in Wikidata."""

    WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"
    WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"

    def __init__(self, http_client: HttpClient | None = None):
        self.client = http_client or HttpClient()

    async def match(self, anime: Anime) -> MatchResult:
        """Find best Wikidata match for anime.

        Args:
            anime: Anime to match

        Returns:
            MatchResult with best match (or no match)
        """
        # Try exact ID match first
        id_match = await self._match_by_id(anime)
        if id_match and id_match.is_match():
            return id_match

        # Try exact title + year
        title_year_match = await self._match_by_title_and_year(anime)
        if title_year_match and title_year_match.is_match():
            return title_year_match

        # Try fuzzy title match
        fuzzy_match = await self._match_by_fuzzy_title(anime)
        if fuzzy_match and fuzzy_match.is_match():
            return fuzzy_match

        # Try multi-field match
        multi_match = await self._match_multi_field(anime)
        if multi_match and multi_match.is_match():
            return multi_match

        return MatchResult.no_match()

    async def _match_by_id(self, anime: Anime) -> MatchResult | None:
        """Match by exact MAL ID property.

        Args:
            anime: Anime to match

        Returns:
            MatchResult if found, None otherwise
        """
        try:
            # SPARQL query to find entity by MAL ID property
            query = f"""
            SELECT ?item ?itemLabel WHERE {{
                ?item wdt:{PROP_MAL_ID} "{anime.mal_id}" .
                SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
            }}
            LIMIT 1
            """

            results = await self._sparql_query(query)

            if results and results.get("results", {}).get("bindings"):
                binding = results["results"]["bindings"][0]
                item_uri = binding.get("item", {}).get("value", "")
                label = binding.get("itemLabel", {}).get("value", "")

                # Extract Q-ID from URI
                q_id = item_uri.split("/")[-1] if item_uri else None

                if q_id:
                    return MatchResult(
                        wikidata_id=q_id,
                        wikidata_label=label,
                        confidence=0.95,
                        match_method=MatchMethod.EXACT_ID,
                        match_metadata={"matched_property": PROP_MAL_ID},
                    )

        except Exception as e:
            logger.debug(f"ID match failed for {anime.mal_id}: {e}")

        return None

    async def _match_by_title_and_year(self, anime: Anime) -> MatchResult | None:
        """Match by exact title and year.

        Args:
            anime: Anime to match

        Returns:
            MatchResult if found, None otherwise
        """
        if not anime.title or not anime.year:
            return None

        try:
            # SPARQL query for title + year match
            # This is a simplified approach - real implementation would need more robust matching
            query = f"""
            SELECT ?item ?itemLabel WHERE {{
                ?item rdfs:label "{anime.title}"@en .
                ?item wdt:{PROP_PUB_DATE} ?date .
                FILTER(STRSTARTS(STR(?date), "{anime.year}"))
                SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
            }}
            LIMIT 5
            """

            results = await self._sparql_query(query)

            if results and results.get("results", {}).get("bindings"):
                binding = results["results"]["bindings"][0]
                item_uri = binding.get("item", {}).get("value", "")
                label = binding.get("itemLabel", {}).get("value", "")

                q_id = item_uri.split("/")[-1] if item_uri else None

                if q_id:
                    return MatchResult(
                        wikidata_id=q_id,
                        wikidata_label=label,
                        confidence=0.9,
                        match_method=MatchMethod.EXACT_TITLE_YEAR,
                        match_metadata={"matched_title": anime.title, "matched_year": anime.year},
                    )

        except Exception as e:
            logger.debug(f"Title+Year match failed for {anime.mal_id}: {e}")

        return None

    async def _match_by_fuzzy_title(self, anime: Anime) -> MatchResult | None:
        """Match by fuzzy title similarity.

        Note: This is a simplified implementation. A full implementation would:
        1. Search for candidates via Wikidata API
        2. Use RapidFuzz for similarity scoring
        3. Return best match above threshold

        Args:
            anime: Anime to match

        Returns:
            MatchResult if found, None otherwise
        """
        # Simplified: Use exact title search via MediaWiki API
        try:
            params = {
                "action": "wbsearchentities",
                "search": anime.title,
                "language": "en",
                "format": "json",
                "limit": 5,
            }

            results = await self.client.get(
                "",
                params=params,
                headers={"User-Agent": "Luma/1.0"},
            )

            if results and results.get("search"):
                for result in results["search"][:3]:
                    # Basic confidence based on match
                    display_label = result.get("display", {}).get("label", {}).get("value", "")
                    desc = result.get("display", {}).get("description", {}).get("value", "")

                    # Simple heuristic: if description mentions anime
                    confidence = 0.6
                    if desc and "anime" in desc.lower():
                        confidence = 0.75

                    if confidence >= 0.5:
                        return MatchResult(
                            wikidata_id=result.get("id"),
                            wikidata_label=display_label,
                            confidence=confidence,
                            match_method=MatchMethod.FUZZY_TITLE,
                            match_metadata={"searched_title": anime.title},
                        )

        except Exception as e:
            logger.debug(f"Fuzzy title match failed for {anime.mal_id}: {e}")

        return None

    async def _match_multi_field(self, anime: Anime) -> MatchResult | None:
        """Match using multiple fields.

        Args:
            anime: Anime to match

        Returns:
            MatchResult if found, None otherwise
        """
        # Simplified implementation
        # Real implementation would combine title + episodes + year
        if not anime.title:
            return None

        try:
            # Search for title
            params = {
                "action": "wbsearchentities",
                "search": anime.title,
                "language": "en",
                "format": "json",
                "limit": 10,
            }

            results = await self.client.get(
                "",
                params=params,
                headers={"User-Agent": "Luma/1.0"},
            )

            if results and results.get("search"):
                best_match = None
                best_confidence = 0.0

                for result in results["search"]:
                    desc = result.get("display", {}).get("description", {}).get("value", "")

                    # Boost confidence if description is relevant
                    confidence = 0.5
                    if desc and "anime" in desc.lower():
                        confidence += 0.2
                    if anime.year and desc and str(anime.year) in desc:
                        confidence += 0.1
                    if anime.episodes and anime.episodes > 1:
                        confidence += 0.05

                    # Limit max confidence for multi-field match
                    confidence = min(confidence, 0.85)

                    if confidence > best_confidence and confidence >= 0.5:
                        best_match = result
                        best_confidence = confidence

                if best_match:
                    display_label = best_match.get("display", {}).get("label", {}).get("value", "")
                    return MatchResult(
                        wikidata_id=best_match.get("id"),
                        wikidata_label=display_label,
                        confidence=best_confidence,
                        match_method=MatchMethod.MULTI_FIELD,
                        match_metadata={
                            "fields_used": ["title", "year", "episodes"],
                            "year": anime.year,
                            "episodes": anime.episodes,
                        },
                    )

        except Exception as e:
            logger.debug(f"Multi-field match failed for {anime.mal_id}: {e}")

        return None

    async def _sparql_query(self, query: str) -> dict | None:
        """Execute SPARQL query.

        Args:
            query: SPARQL query string

        Returns:
            Query results or None
        """
        try:
            import urllib.parse

            params = {
                "query": query,
                "format": "json",
            }

            encoded = urllib.parse.urlencode(params)
            url = f"{self.WIKIDATA_SPARQL_URL}?{encoded}"

            result = await self.client.get(
                url,
                headers={"User-Agent": "Luma/1.0", "Accept": "application/sparql-results+json"},
            )

            return result

        except Exception as e:
            logger.error(f"SPARQL query failed: {e}")
            return None

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.close()
