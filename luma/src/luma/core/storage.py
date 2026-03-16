"""Storage operations for anime data."""

import json
import logging
from typing import Optional

from luma.infrastructure.database import Database
from luma.models.anime import Anime
from luma.models.quality import QualityResult
from luma.models.match import MatchResult

logger = logging.getLogger(__name__)


class Storage:
    """Storage layer for anime data."""

    def __init__(self, db: Database):
        self.db = db

    async def save_anime(self, anime: Anime, status: str = "pending") -> int:
        """Save anime to database.

        Args:
            anime: Anime to save
            status: Processing status

        Returns:
            Database ID of saved anime
        """
        return await self.db.upsert_anime(
            mal_id=anime.mal_id,
            title=anime.title,
            title_japanese=anime.title_japanese,
            title_english=anime.title_english,
            episodes=anime.episodes,
            score=anime.score,
            year=anime.year,
            type_=anime.type.value if anime.type else None,
            source=anime.source.value if anime.source else None,
            studios=anime.studios if anime.studios else None,
            genres=anime.genres if anime.genres else None,
            synopsis=anime.synopsis,
            processing_status=status,
        )

    async def save_quality_check(
        self,
        anime_id: int,
        result: QualityResult,
    ) -> int:
        """Save quality check result.

        Args:
            anime_id: Database ID of anime
            result: Quality check result

        Returns:
            Database ID of saved quality check
        """
        violation_details = None
        if result.violations:
            violation_details = json.dumps(
                [
                    {
                        "rule": v.rule.value,
                        "field": v.field,
                        "message": v.message,
                        "severity": v.severity,
                    }
                    for v in result.violations
                ]
            )

        return await self.db.insert_quality_check(
            anime_id=anime_id,
            passed=result.passed,
            overall_reason=result.overall_reason,
            violation_details=violation_details,
        )

    async def save_match(
        self,
        anime_id: int,
        result: MatchResult,
    ) -> int:
        """Save Wikidata match result.

        Args:
            anime_id: Database ID of anime
            result: Match result

        Returns:
            Database ID of saved match
        """
        return await self.db.upsert_match(
            anime_id=anime_id,
            wikidata_id=result.wikidata_id,
            wikidata_label=result.wikidata_label,
            confidence=result.confidence,
            match_method=result.match_method.value,
            match_metadata=result.match_metadata if result.match_metadata else None,
        )

    async def mark_anime_completed(self, mal_id: int) -> None:
        """Mark anime as completed.

        Args:
            mal_id: MyAnimeList ID
        """
        await self.db.update_anime_status(mal_id, "completed")

    async def mark_anime_failed(self, mal_id: int) -> None:
        """Mark anime as failed.

        Args:
            mal_id: MyAnimeList ID
        """
        await self.db.update_anime_status(mal_id, "failed")

    async def get_anime_db_id(self, mal_id: int) -> Optional[int]:
        """Get database ID for MAL ID.

        Args:
            mal_id: MyAnimeList ID

        Returns:
            Database ID or None
        """
        anime = await self.db.get_anime_by_mal_id(mal_id)
        return anime["id"] if anime else None

    async def get_processed_ids(self) -> set[int]:
        """Get set of processed MAL IDs.

        Returns:
            Set of processed MAL IDs
        """
        return await self.db.get_processed_anime_ids()

    async def export_data(
        self,
        filter_type: str = "all",
        limit: Optional[int] = None,
    ) -> list[dict]:
        """Export anime data.

        Args:
            filter_type: "all", "matched", or "unmatched"
            limit: Maximum records to return

        Returns:
            List of anime data dicts
        """
        return await self.db.get_anime_for_export(filter_type, limit)

    async def get_stats(self) -> dict:
        """Get database statistics.

        Returns:
            Dictionary of statistics
        """
        return await self.db.get_stats()

    async def log_error(
        self,
        anime_id: Optional[int],
        stage: str,
        error_type: str,
        error_message: str,
        stack_trace: Optional[str] = None,
    ) -> int:
        """Log processing error.

        Args:
            anime_id: MAL ID
            stage: Processing stage
            error_type: Type of error
            error_message: Error message
            stack_trace: Stack trace

        Returns:
            Database ID of logged error
        """
        return await self.db.insert_error(
            anime_id=anime_id,
            stage=stage,
            error_type=error_type,
            error_message=error_message,
            stack_trace=stack_trace,
        )
