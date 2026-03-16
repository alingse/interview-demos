"""Tests for data fetching module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from luma.core.fetch import AnimeFetcher


@pytest.mark.asyncio
async def test_fetch_anime_success():
    """Test successful anime fetch."""
    # Mock client
    mock_client = MagicMock()
    mock_client.get_anime = AsyncMock(
        return_value={
            "data": {
                "mal_id": 1,
                "title": "Test Anime",
                "episodes": 12,
                "score": 8.5,
                "type": "TV",
                "source": "Manga",
                "aired": {"from": "2020-01-01"},
                "studios": [{"name": "Test Studio"}],
                "genres": [{"name": "Action"}],
                "titles": [],
            }
        }
    )

    fetcher = AnimeFetcher(client=mock_client)
    anime = await fetcher.fetch_anime(1)

    assert anime is not None
    assert anime.mal_id == 1
    assert anime.title == "Test Anime"
    assert anime.episodes == 12


@pytest.mark.asyncio
async def test_fetch_anime_not_found():
    """Test fetching non-existent anime."""
    mock_client = MagicMock()
    mock_client.get_anime = AsyncMock(return_value=None)

    fetcher = AnimeFetcher(client=mock_client)
    anime = await fetcher.fetch_anime(99999)

    assert anime is None


@pytest.mark.asyncio
async def test_fetch_anime_batch():
    """Test batch fetching."""
    mock_client = MagicMock()
    mock_client.get_anime = AsyncMock(
        return_value={
            "data": {
                "mal_id": 1,
                "title": "Test Anime",
                "episodes": 12,
                "score": 8.5,
                "type": "TV",
                "source": "Manga",
                "aired": {"from": "2020-01-01"},
                "studios": [],
                "genres": [],
                "titles": [],
            }
        }
    )

    fetcher = AnimeFetcher(client=mock_client)
    results = await fetcher.fetch_anime_batch([1, 2, 3], batch_size=2)

    assert len(results) == 3
    assert all(r is not None for r in results)


def test_parse_anime_valid():
    """Test parsing valid anime data."""
    fetcher = AnimeFetcher()

    data = {
        "mal_id": 1,
        "title": "Test Anime",
        "episodes": 12,
        "score": 8.5,
        "year": 2020,
        "type": "TV",
        "source": "Manga",
        "aired": {"from": "2020-01-01"},
        "studios": [{"name": "Test Studio"}],
        "genres": [{"name": "Action"}],
        "titles": [],
    }

    anime = fetcher._parse_anime(data)

    assert anime is not None
    assert anime.mal_id == 1
    assert anime.title == "Test Anime"
    assert anime.episodes == 12
