"""Wikidata matching models."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MatchMethod(str, Enum):
    """Wikidata matching methods."""

    EXACT_ID = "exact_id"
    EXACT_TITLE_YEAR = "exact_title_year"
    FUZZY_TITLE = "fuzzy_title"
    MULTI_FIELD = "multi_field"
    NO_MATCH = "no_match"


class MatchResult(BaseModel):
    """Result of Wikidata matching."""

    wikidata_id: str | None = Field(None, description="Wikidata Q-ID")
    wikidata_label: str | None = Field(None, description="Wikidata label")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Match confidence")
    match_method: MatchMethod = Field(..., description="How the match was made")
    match_metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @classmethod
    def no_match(cls) -> "MatchResult":
        """Create a no-match result."""
        return cls(
            wikidata_id=None,
            wikidata_label=None,
            confidence=0.0,
            match_method=MatchMethod.NO_MATCH,
        )

    def is_match(self) -> bool:
        """Check if this represents a valid match."""
        return self.wikidata_id is not None and self.confidence >= 0.5


class MatchDB(BaseModel):
    """Match result as stored in database."""

    id: int
    anime_id: int
    wikidata_id: str | None = None
    wikidata_label: str | None = None
    confidence: float
    match_method: str
    match_metadata: str | None = None  # JSON string
    created_at: datetime | None = None
