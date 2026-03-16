"""Tests for quality checking module."""

import pytest

from luma.core.quality import QualityChecker
from luma.models.anime import Anime
from luma.models.quality import QualityRule


@pytest.mark.asyncio
async def test_quality_check_pass(sample_anime, quality_checker):
    """Test quality check passes for valid anime."""
    result = quality_checker.check(sample_anime)

    assert result.passed is True
    assert len(result.violations) == 0


def test_quality_check_missing_title():
    """Test quality check fails for missing title."""
    checker = QualityChecker()

    anime = Anime(
        mal_id=1,
        title="",  # Empty title
        episodes=12,
        score=8.5,
        year=2020,
    )

    result = checker.check(anime)

    assert result.passed is False
    assert any(v.rule == QualityRule.TITLE_FORMAT for v in result.violations)


def test_quality_check_invalid_score():
    """Test quality check fails for invalid score."""
    checker = QualityChecker()

    anime = Anime(
        mal_id=1,
        title="Test Anime",
        episodes=12,
        score=15,  # Invalid score
        year=2020,
    )

    result = checker.check(anime)

    assert result.passed is False
    assert any(v.rule == QualityRule.VALUE_RANGE and v.field == "score" for v in result.violations)


def test_quality_check_invalid_episodes():
    """Test quality check fails for invalid episodes."""
    checker = QualityChecker()

    anime = Anime(
        mal_id=1,
        title="Test Anime",
        episodes=5000,  # Invalid episodes
        score=8.5,
        year=2020,
    )

    result = checker.check(anime)

    assert result.passed is False
    assert any(
        v.rule == QualityRule.VALUE_RANGE and v.field == "episodes" for v in result.violations
    )


def test_quality_check_invalid_year():
    """Test quality check fails for invalid year."""
    checker = QualityChecker()

    anime = Anime(
        mal_id=1,
        title="Test Anime",
        episodes=12,
        score=8.5,
        year=1800,  # Invalid year
    )

    result = checker.check(anime)

    assert result.passed is False
    assert any(v.rule == QualityRule.VALUE_RANGE and v.field == "year" for v in result.violations)


def test_quality_check_placeholder_title():
    """Test quality check fails for placeholder title."""
    checker = QualityChecker()

    anime = Anime(
        mal_id=1,
        title="TBA",  # Placeholder title
        episodes=12,
        score=8.5,
        year=2020,
    )

    result = checker.check(anime)

    assert result.passed is False
    assert any(v.rule == QualityRule.TITLE_FORMAT for v in result.violations)
