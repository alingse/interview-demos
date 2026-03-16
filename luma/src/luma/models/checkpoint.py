"""Checkpoint and pipeline state models."""

from enum import Enum
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class PipelineStage(str, Enum):
    """Pipeline processing stages."""

    IDLE = "idle"
    FETCH = "fetch"
    QUALITY = "quality"
    MATCH = "match"
    STORE = "store"
    COMPLETE = "complete"
    ERROR = "error"


class ProcessingError(BaseModel):
    """A processing error record."""

    anime_id: Optional[int] = Field(None, description="Anime ID that failed")
    stage: PipelineStage = Field(..., description="Stage where error occurred")
    error_type: str = Field(..., description="Type of error")
    error_message: str = Field(..., description="Error message")
    stack_trace: Optional[str] = Field(None, description="Stack trace")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PipelineStats(BaseModel):
    """Pipeline statistics."""

    total: int = Field(default=0, description="Total items to process")
    processed: int = Field(default=0, description="Successfully processed")
    failed: int = Field(default=0, description="Failed items")
    skipped: int = Field(default=0, description="Skipped items")

    # Quality stats
    quality_passed: int = Field(default=0)
    quality_failed: int = Field(default=0)

    # Match stats
    matched: int = Field(default=0, description="Items with Wikidata match")
    unmatched: int = Field(default=0, description="Items without match")

    # Timing
    start_time: Optional[datetime] = Field(None, description="Pipeline start time")
    end_time: Optional[datetime] = Field(None, description="Pipeline end time")

    @property
    def progress_percent(self) -> float:
        """Progress percentage."""
        if self.total == 0:
            return 0.0
        return (self.processed / self.total) * 100

    @property
    def duration_seconds(self) -> Optional[float]:
        """Pipeline duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None


class CheckpointState(BaseModel):
    """Checkpoint state for resume capability."""

    checkpoint_id: str = Field(..., description="Unique checkpoint ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Checkpoint time")

    # Processing range
    start_id: int = Field(..., description="Starting MAL ID")
    end_id: int = Field(..., description="Ending MAL ID")
    total_count: int = Field(..., description="Total count to process")

    # Progress tracking
    processed_ids: set[int] = Field(default_factory=set, description="Completed IDs")
    in_progress_ids: set[int] = Field(default_factory=set, description="In-progress IDs")
    pending_ids: set[int] = Field(default_factory=set, description="Pending IDs")

    # Current state
    current_stage: PipelineStage = Field(default=PipelineStage.IDLE)
    current_batch_index: int = Field(default=0, description="Current batch index")

    # Statistics
    stats: PipelineStats = Field(default_factory=PipelineStats)

    # Errors
    errors: list[ProcessingError] = Field(default_factory=list)

    @field_validator("processed_ids", "in_progress_ids", "pending_ids", mode="before")
    @classmethod
    def validate_sets(cls, v):
        """Ensure list is converted to set."""
        if isinstance(v, list):
            return set(v)
        return v

    def get_progress_summary(self) -> dict:
        """Get progress summary."""
        total_done = len(self.processed_ids)
        total = self.total_count
        return {
            "checkpoint_id": self.checkpoint_id,
            "stage": self.current_stage,
            "progress": f"{total_done}/{total}",
            "percent": round((total_done / total * 100) if total > 0 else 0, 2),
            "processed": len(self.processed_ids),
            "in_progress": len(self.in_progress_ids),
            "pending": len(self.pending_ids),
        }


class PipelineReport(BaseModel):
    """Final pipeline execution report."""

    checkpoint_id: str
    start_time: datetime
    end_time: datetime
    start_id: int
    end_id: int

    total_processed: int
    successful: int
    failed: int
    skipped: int

    quality_passed: int
    quality_failed: int
    matched: int
    unmatched: int

    errors: list[ProcessingError] = Field(default_factory=list)

    resumed: bool = Field(default=False, description="Was this a resumed run")
