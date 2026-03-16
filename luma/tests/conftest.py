"""Test fixtures and configuration."""

import asyncio
import pytest
import tempfile
from pathlib import Path

from luma.infrastructure.database import Database
from luma.infrastructure.rate_limiter import RateLimiter
from luma.core.quality import QualityChecker
from luma.models.anime import Anime


@pytest.fixture
def temp_db_path():
    """Create temporary database path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        yield f.name
    # Cleanup is handled by tempfile


@pytest.fixture
async def db(temp_db_path):
    """Create test database."""
    database = Database(temp_db_path)
    await database.connect()
    yield database
    await database.close()


@pytest.fixture
def rate_limiter():
    """Create rate limiter."""
    return RateLimiter(rate=10.0, burst=5)


@pytest.fixture
def quality_checker():
    """Create quality checker."""
    return QualityChecker()


@pytest.fixture
def sample_anime():
    """Create sample anime for testing."""
    return Anime(
        mal_id=1,
        title="Cowboy Bebop",
        title_japanese="カウボーイビバップ",
        title_english="Cowboy Bebop",
        episodes=26,
        score=8.78,
        year=1998,
        type=AnimeType.TV,
        source=AnimeSource.MANGA,
        studios=["Sunrise"],
        genres=["Action", "Sci-Fi"],
        synopsis="In the year 2071...",
    )


@pytest.fixture
def invalid_anime():
    """Create invalid anime for testing."""
    return Anime(
        mal_id=2,
        title="TBA",  # Invalid title
        episodes=5000,  # Invalid episodes (too many)
        score=15,  # Invalid score (too high)
        year=1800,  # Invalid year (too old)
        type=AnimeType.UNKNOWN,
    )


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Import models for fixtures
from luma.models.anime import AnimeType, AnimeSource
