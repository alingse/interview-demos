"""Checkpoint management for resume capability."""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from luma.models.checkpoint import CheckpointState, PipelineStage, ProcessingError, PipelineStats

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manager for saving and loading checkpoint state."""

    def __init__(self, checkpoint_path: str = "data/checkpoint.json"):
        self.checkpoint_path = Path(checkpoint_path)
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    def create_new(
        self,
        start_id: int,
        end_id: int,
    ) -> CheckpointState:
        """Create a new checkpoint state.

        Args:
            start_id: Starting MAL ID
            end_id: Ending MAL ID

        Returns:
            New CheckpointState
        """
        total_count = end_id - start_id + 1
        pending_ids = set(range(start_id, end_id + 1))

        checkpoint_id = f"ckpt_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        state = CheckpointState(
            checkpoint_id=checkpoint_id,
            start_id=start_id,
            end_id=end_id,
            total_count=total_count,
            pending_ids=pending_ids,
            current_stage=PipelineStage.IDLE,
            stats=PipelineStats(total=total_count, start_time=datetime.utcnow()),
        )

        logger.info(f"Created new checkpoint {checkpoint_id} for IDs {start_id}-{end_id}")
        return state

    def save(self, state: CheckpointState) -> None:
        """Save checkpoint state to file.

        Uses atomic write: write to temp file, then rename.

        Args:
            state: CheckpointState to save
        """
        # Convert sets to lists for JSON serialization
        data = {
            "checkpoint_id": state.checkpoint_id,
            "timestamp": state.timestamp.isoformat(),
            "start_id": state.start_id,
            "end_id": state.end_id,
            "total_count": state.total_count,
            "processed_ids": list(state.processed_ids),
            "in_progress_ids": list(state.in_progress_ids),
            "pending_ids": list(state.pending_ids),
            "current_stage": state.current_stage.value,
            "current_batch_index": state.current_batch_index,
            "stats": {
                "total": state.stats.total,
                "processed": state.stats.processed,
                "failed": state.stats.failed,
                "skipped": state.stats.skipped,
                "quality_passed": state.stats.quality_passed,
                "quality_failed": state.stats.quality_failed,
                "matched": state.stats.matched,
                "unmatched": state.stats.unmatched,
                "start_time": state.stats.start_time.isoformat() if state.stats.start_time else None,
                "end_time": state.stats.end_time.isoformat() if state.stats.end_time else None,
            },
            "errors": [
                {
                    "anime_id": e.anime_id,
                    "stage": e.stage.value,
                    "error_type": e.error_type,
                    "error_message": e.error_message,
                    "stack_trace": e.stack_trace,
                    "timestamp": e.timestamp.isoformat(),
                }
                for e in state.errors
            ],
        }

        # Atomic write: temp file + rename
        temp_path = self.checkpoint_path.with_suffix(".tmp")
        try:
            with open(temp_path, "w") as f:
                json.dump(data, f, indent=2)

            # Atomic rename
            temp_path.replace(self.checkpoint_path)

            logger.debug(
                f"Saved checkpoint {state.checkpoint_id} "
                f"({len(state.processed_ids)}/{state.total_count} processed)"
            )

        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            if temp_path.exists():
                temp_path.unlink()

    def load(self) -> Optional[CheckpointState]:
        """Load checkpoint state from file.

        Returns:
            CheckpointState if exists, None otherwise
        """
        if not self.checkpoint_path.exists():
            return None

        try:
            with open(self.checkpoint_path, "r") as f:
                data = json.load(f)

            stats_data = data.pop("stats", {})
            errors_data = data.pop("errors", [])

            state = CheckpointState(
                checkpoint_id=data["checkpoint_id"],
                timestamp=datetime.fromisoformat(data["timestamp"]),
                start_id=data["start_id"],
                end_id=data["end_id"],
                total_count=data["total_count"],
                processed_ids=set(data.get("processed_ids", [])),
                in_progress_ids=set(data.get("in_progress_ids", [])),
                pending_ids=set(data.get("pending_ids", [])),
                current_stage=PipelineStage(data.get("current_stage", "idle")),
                current_batch_index=data.get("current_batch_index", 0),
                stats=PipelineStats(
                    total=stats_data.get("total", 0),
                    processed=stats_data.get("processed", 0),
                    failed=stats_data.get("failed", 0),
                    skipped=stats_data.get("skipped", 0),
                    quality_passed=stats_data.get("quality_passed", 0),
                    quality_failed=stats_data.get("quality_failed", 0),
                    matched=stats_data.get("matched", 0),
                    unmatched=stats_data.get("unmatched", 0),
                    start_time=datetime.fromisoformat(stats_data["start_time"]) if stats_data.get("start_time") else None,
                    end_time=datetime.fromisoformat(stats_data["end_time"]) if stats_data.get("end_time") else None,
                ),
                errors=[
                    ProcessingError(
                        anime_id=e.get("anime_id"),
                        stage=PipelineStage(e["stage"]),
                        error_type=e["error_type"],
                        error_message=e["error_message"],
                        stack_trace=e.get("stack_trace"),
                        timestamp=datetime.fromisoformat(e["timestamp"]),
                    )
                    for e in errors_data
                ],
            )

            logger.info(
                f"Loaded checkpoint {state.checkpoint_id} "
                f"({len(state.processed_ids)}/{state.total_count} processed, "
                f"stage: {state.current_stage})"
            )

            return state

        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None

    def clear(self) -> None:
        """Clear checkpoint file."""
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()
            logger.info("Cleared checkpoint file")

    def exists(self) -> bool:
        """Check if checkpoint file exists."""
        return self.checkpoint_path.exists()

    def update_stats(
        self,
        state: CheckpointState,
        processed_increment: int = 0,
        failed_increment: int = 0,
        skipped_increment: int = 0,
        quality_passed_increment: int = 0,
        quality_failed_increment: int = 0,
        matched_increment: int = 0,
        unmatched_increment: int = 0,
    ) -> None:
        """Update checkpoint statistics.

        Args:
            state: CheckpointState to update
            processed_increment: Add to processed count
            failed_increment: Add to failed count
            skipped_increment: Add to skipped count
            quality_passed_increment: Add to quality passed count
            quality_failed_increment: Add to quality failed count
            matched_increment: Add to matched count
            unmatched_increment: Add to unmatched count
        """
        state.stats.processed += processed_increment
        state.stats.failed += failed_increment
        state.stats.skipped += skipped_increment
        state.stats.quality_passed += quality_passed_increment
        state.stats.quality_failed += quality_failed_increment
        state.stats.matched += matched_increment
        state.stats.unmatched += unmatched_increment

    def add_error(
        self,
        state: CheckpointState,
        anime_id: Optional[int],
        stage: PipelineStage,
        error_type: str,
        error_message: str,
        stack_trace: Optional[str] = None,
    ) -> None:
        """Add error to checkpoint state.

        Args:
            state: CheckpointState to update
            anime_id: MAL ID that failed
            stage: Stage where error occurred
            error_type: Type of error
            error_message: Error message
            stack_trace: Stack trace
        """
        state.errors.append(
            ProcessingError(
                anime_id=anime_id,
                stage=stage,
                error_type=error_type,
                error_message=error_message,
                stack_trace=stack_trace,
                timestamp=datetime.utcnow(),
            )
        )
