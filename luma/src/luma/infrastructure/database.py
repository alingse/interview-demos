"""Async SQLite database connection and operations."""

import aiosqlite
import json
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Any, List
from datetime import datetime

from pydantic import BaseModel


class Database:
    """Async SQLite database wrapper."""

    def __init__(self, db_path: str | Path = "data/anime.db"):
        self.db_path = Path(db_path)
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self) -> aiosqlite.Connection:
        """Create database connection and initialize schema."""
        if self._connection is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = await aiosqlite.connect(self.db_path)
            await self._init_schema()
        return self._connection

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    @asynccontextmanager
    async def connection(self):
        """Context manager for database connection."""
        conn = await self.connect()
        try:
            yield conn
        finally:
            pass  # Don't close, keep for reuse

    async def _init_schema(self) -> None:
        """Initialize database schema."""
        if self._connection is None:
            return

        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS anime (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mal_id INTEGER UNIQUE NOT NULL,
                title TEXT NOT NULL,
                title_japanese TEXT,
                title_english TEXT,
                episodes INTEGER,
                score REAL,
                year INTEGER,
                type TEXT,
                source TEXT,
                studios TEXT,
                genres TEXT,
                synopsis TEXT,
                processing_status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS quality_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anime_id INTEGER NOT NULL,
                passed BOOLEAN NOT NULL,
                overall_reason TEXT,
                violation_details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (anime_id) REFERENCES anime(id)
            )
        """)

        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anime_id INTEGER NOT NULL UNIQUE,
                wikidata_id TEXT,
                wikidata_label TEXT,
                confidence REAL NOT NULL,
                match_method TEXT NOT NULL,
                match_metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (anime_id) REFERENCES anime(id)
            )
        """)

        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS processing_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anime_id INTEGER,
                stage TEXT NOT NULL,
                error_type TEXT NOT NULL,
                error_message TEXT NOT NULL,
                stack_trace TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for better query performance
        await self._connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_anime_mal_id ON anime(mal_id)
        """)

        await self._connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_anime_status ON anime(processing_status)
        """)

        await self._connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_quality_anime_id ON quality_checks(anime_id)
        """)

        await self._connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_matches_anime_id ON matches(anime_id)
        """)

        await self._connection.commit()

    async def upsert_anime(
        self,
        mal_id: int,
        title: str,
        title_japanese: Optional[str] = None,
        title_english: Optional[str] = None,
        episodes: Optional[int] = None,
        score: Optional[float] = None,
        year: Optional[int] = None,
        type_: Optional[str] = None,
        source: Optional[str] = None,
        studios: Optional[List[str]] = None,
        genres: Optional[List[str]] = None,
        synopsis: Optional[str] = None,
        processing_status: str = "pending",
    ) -> int:
        """Insert or update anime record.

        Returns:
            The anime database ID
        """
        async with self.connection() as conn:
            studios_json = json.dumps(studios) if studios else None
            genres_json = json.dumps(genres) if genres else None

            cursor = await conn.execute("""
                INSERT INTO anime (
                    mal_id, title, title_japanese, title_english,
                    episodes, score, year, type, source,
                    studios, genres, synopsis, processing_status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT (mal_id) DO UPDATE SET
                    title = excluded.title,
                    title_japanese = excluded.title_japanese,
                    title_english = excluded.title_english,
                    episodes = excluded.episodes,
                    score = excluded.score,
                    year = excluded.year,
                    type = excluded.type,
                    source = excluded.source,
                    studios = excluded.studios,
                    genres = excluded.genres,
                    synopsis = excluded.synopsis,
                    processing_status = excluded.processing_status,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
            """, (
                mal_id, title, title_japanese, title_english,
                episodes, score, year, type_, source,
                studios_json, genres_json, synopsis, processing_status
            ))

            row = await cursor.fetchone()
            await conn.commit()
            return row[0] if row else cursor.lastrowid

    async def get_anime_by_mal_id(self, mal_id: int) -> Optional[dict]:
        """Get anime by MAL ID."""
        async with self.connection() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM anime WHERE mal_id = ?",
                (mal_id,)
            )
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

    async def update_anime_status(self, mal_id: int, status: str) -> None:
        """Update anime processing status."""
        async with self.connection() as conn:
            await conn.execute("""
                UPDATE anime SET processing_status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE mal_id = ?
            """, (status, mal_id))
            await conn.commit()

    async def insert_quality_check(
        self,
        anime_id: int,
        passed: bool,
        overall_reason: Optional[str] = None,
        violation_details: Optional[str] = None,
    ) -> int:
        """Insert quality check result."""
        async with self.connection() as conn:
            cursor = await conn.execute("""
                INSERT INTO quality_checks (anime_id, passed, overall_reason, violation_details)
                VALUES (?, ?, ?, ?)
            """, (anime_id, passed, overall_reason, violation_details))
            await conn.commit()
            return cursor.lastrowid

    async def upsert_match(
        self,
        anime_id: int,
        wikidata_id: Optional[str],
        wikidata_label: Optional[str],
        confidence: float,
        match_method: str,
        match_metadata: Optional[dict] = None,
    ) -> int:
        """Insert or update match result."""
        async with self.connection() as conn:
            metadata_json = json.dumps(match_metadata) if match_metadata else None

            cursor = await conn.execute("""
                INSERT INTO matches (
                    anime_id, wikidata_id, wikidata_label, confidence, match_method, match_metadata
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (anime_id) DO UPDATE SET
                    wikidata_id = excluded.wikidata_id,
                    wikidata_label = excluded.wikidata_label,
                    confidence = excluded.confidence,
                    match_method = excluded.match_method,
                    match_metadata = excluded.match_metadata
                RETURNING id
            """, (anime_id, wikidata_id, wikidata_label, confidence, match_method, metadata_json))

            row = await cursor.fetchone()
            await conn.commit()
            return row[0] if row else cursor.lastrowid

    async def insert_error(
        self,
        anime_id: Optional[int],
        stage: str,
        error_type: str,
        error_message: str,
        stack_trace: Optional[str] = None,
    ) -> int:
        """Insert processing error."""
        async with self.connection() as conn:
            cursor = await conn.execute("""
                INSERT INTO processing_errors (anime_id, stage, error_type, error_message, stack_trace)
                VALUES (?, ?, ?, ?, ?)
            """, (anime_id, stage, error_type, error_message, stack_trace))
            await conn.commit()
            return cursor.lastrowid

    async def get_processed_anime_ids(self) -> set[int]:
        """Get set of processed anime MAL IDs."""
        async with self.connection() as conn:
            cursor = await conn.execute("""
                SELECT mal_id FROM anime WHERE processing_status = 'completed'
            """)
            rows = await cursor.fetchall()
            return {row[0] for row in rows}

    async def get_anime_for_export(
        self,
        filter_type: str = "all",
        limit: Optional[int] = None,
    ) -> List[dict]:
        """Get anime for export.

        Args:
            filter_type: "all", "matched", or "unmatched"
            limit: Maximum number of records to return
        """
        async with self.connection() as conn:
            conn.row_factory = aiosqlite.Row

            query = """
                SELECT
                    a.*,
                    qc.passed as quality_passed,
                    m.wikidata_id, m.wikidata_label, m.confidence as match_confidence
                FROM anime a
                LEFT JOIN quality_checks qc ON a.id = qc.anime_id
                LEFT JOIN matches m ON a.id = m.anime_id
                WHERE a.processing_status = 'completed'
            """

            params: List = []

            if filter_type == "matched":
                query += " AND m.wikidata_id IS NOT NULL"
            elif filter_type == "unmatched":
                query += " AND m.wikidata_id IS NULL"

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_stats(self) -> dict:
        """Get database statistics."""
        async with self.connection() as conn:
            stats = {}

            cursor = await conn.execute("SELECT COUNT(*) FROM anime")
            stats["total_anime"] = (await cursor.fetchone())[0]

            cursor = await conn.execute("SELECT COUNT(*) FROM anime WHERE processing_status = 'completed'")
            stats["completed_anime"] = (await cursor.fetchone())[0]

            cursor = await conn.execute("""
                SELECT COUNT(*) FROM quality_checks WHERE passed = 1
            """)
            stats["quality_passed"] = (await cursor.fetchone())[0]

            cursor = await conn.execute("""
                SELECT COUNT(*) FROM quality_checks WHERE passed = 0
            """)
            stats["quality_failed"] = (await cursor.fetchone())[0]

            cursor = await conn.execute("""
                SELECT COUNT(*) FROM matches WHERE wikidata_id IS NOT NULL
            """)
            stats["matched"] = (await cursor.fetchone())[0]

            cursor = await conn.execute("""
                SELECT COUNT(*) FROM matches WHERE wikidata_id IS NULL
            """)
            stats["unmatched"] = (await cursor.fetchone())[0]

            return stats
