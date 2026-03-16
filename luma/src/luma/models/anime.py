"""Anime data models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class AnimeType(str, Enum):
    """Anime type classification."""

    TV = "TV"
    MOVIE = "Movie"
    OVA = "OVA"
    SPECIAL = "Special"
    ONA = "ONA"
    MUSIC = "Music"
    UNKNOWN = "Unknown"


class AnimeSource(str, Enum):
    """Anime source material."""

    MANGA = "Manga"
    ORIGINAL = "Original"
    LIGHT_NOVEL = "Light novel"
    NOVEL = "Novel"
    GAME = "Game"
    VISUAL_NOVEL = "Visual novel"
    WEB_MANGA = "Web manga"
    WEB_NOVEL = "Web novel"
    OTHER = "Other"
    UNKNOWN = "Unknown"


class Anime(BaseModel):
    """Anime metadata from MAL."""

    mal_id: int = Field(..., description="MyAnimeList ID")
    title: str = Field(..., description="Main title")
    title_japanese: str | None = Field(None, description="Japanese title")
    title_english: str | None = Field(None, description="English title")
    titles: list[dict] = Field(default_factory=list, description="All titles")

    episodes: int | None = Field(None, description="Number of episodes")
    score: float | None = Field(None, ge=0, le=10, description="MAL score")
    year: int | None = Field(None, description="Release year")

    type: AnimeType = Field(default=AnimeType.UNKNOWN, description="Anime type")
    source: AnimeSource = Field(default=AnimeSource.UNKNOWN, description="Source material")

    studios: list[str] = Field(default_factory=list, description="Studios")
    genres: list[str] = Field(default_factory=list, description="Genres")
    synopsis: str | None = Field(None, description="Synopsis")

    aired: dict | None = Field(None, description="Aired date info")
    duration: str | None = Field(None, description="Duration")
    rating: str | None = Field(None, description="Age rating")

    url: str | None = Field(None, description="MAL URL")
    images: dict | None = Field(None, description="Image URLs")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Validate title is not empty or placeholder."""
        if not v or v.strip() in ("", "TBA", "N/A", "tba", "n/a"):
            raise ValueError("Invalid title")
        return v.strip()

    @field_validator("episodes")
    @classmethod
    def validate_episodes(cls, v: int | None) -> int | None:
        """Validate episodes are within valid range."""
        if v is not None and (v < 1 or v > 2000):
            raise ValueError("Episodes must be between 1 and 2000")
        return v

    @field_validator("year")
    @classmethod
    def validate_year(cls, v: int | None) -> int | None:
        """Validate year is reasonable."""
        from datetime import datetime

        current_year = datetime.now().year
        if v is not None and (v < 1900 or v > current_year + 5):
            raise ValueError(f"Year must be between 1900 and {current_year + 5}")
        return v


class AnimeDB(BaseModel):
    """Anime as stored in database."""

    id: int
    mal_id: int
    title: str
    title_japanese: str | None = None
    title_english: str | None = None
    episodes: int | None = None
    score: float | None = None
    year: int | None = None
    type: str | None = None
    source: str | None = None
    studios: str | None = None  # JSON string
    genres: str | None = None  # JSON string
    synopsis: str | None = None
    processing_status: str = "pending"
    created_at: datetime | None = None
    updated_at: datetime | None = None
