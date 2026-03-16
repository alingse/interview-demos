"""Anime data models."""

from enum import Enum
from typing import Optional
from datetime import datetime

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
    title_japanese: Optional[str] = Field(None, description="Japanese title")
    title_english: Optional[str] = Field(None, description="English title")
    titles: list[dict] = Field(default_factory=list, description="All titles")

    episodes: Optional[int] = Field(None, description="Number of episodes")
    score: Optional[float] = Field(None, ge=0, le=10, description="MAL score")
    year: Optional[int] = Field(None, description="Release year")

    type: AnimeType = Field(default=AnimeType.UNKNOWN, description="Anime type")
    source: AnimeSource = Field(default=AnimeSource.UNKNOWN, description="Source material")

    studios: list[str] = Field(default_factory=list, description="Studios")
    genres: list[str] = Field(default_factory=list, description="Genres")
    synopsis: Optional[str] = Field(None, description="Synopsis")

    aired: Optional[dict] = Field(None, description="Aired date info")
    duration: Optional[str] = Field(None, description="Duration")
    rating: Optional[str] = Field(None, description="Age rating")

    url: Optional[str] = Field(None, description="MAL URL")
    images: Optional[dict] = Field(None, description="Image URLs")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Validate title is not empty or placeholder."""
        if not v or v.strip() in ("", "TBA", "N/A", "tba", "n/a"):
            raise ValueError("Invalid title")
        return v.strip()

    @field_validator("episodes")
    @classmethod
    def validate_episodes(cls, v: Optional[int]) -> Optional[int]:
        """Validate episodes are within valid range."""
        if v is not None and (v < 1 or v > 2000):
            raise ValueError("Episodes must be between 1 and 2000")
        return v

    @field_validator("year")
    @classmethod
    def validate_year(cls, v: Optional[int]) -> Optional[int]:
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
    title_japanese: Optional[str] = None
    title_english: Optional[str] = None
    episodes: Optional[int] = None
    score: Optional[float] = None
    year: Optional[int] = None
    type: Optional[str] = None
    source: Optional[str] = None
    studios: Optional[str] = None  # JSON string
    genres: Optional[str] = None  # JSON string
    synopsis: Optional[str] = None
    processing_status: str = "pending"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
