"""Pipeline orchestrator for data processing."""

import asyncio
import logging
import traceback

from luma.core.fetch import AnimeFetcher
from luma.core.match import WikidataMatcher
from luma.core.quality import QualityChecker
from luma.core.storage import Storage
from luma.infrastructure.rate_limiter import ConcurrencyLimiter
from luma.models.checkpoint import CheckpointState, PipelineReport, PipelineStage
from luma.pipeline.checkpoint import CheckpointManager
from luma.pipeline.reporter import PipelineReporter

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Orchestrates the anime processing pipeline."""

    def __init__(
        self,
        fetcher: AnimeFetcher,
        quality_checker: QualityChecker,
        matcher: WikidataMatcher,
        storage: Storage,
        checkpoint_manager: CheckpointManager,
        reporter: PipelineReporter,
        batch_size: int = 10,
        max_concurrent: int = 5,
    ):
        self.fetcher = fetcher
        self.quality_checker = quality_checker
        self.matcher = matcher
        self.storage = storage
        self.checkpoint_manager = checkpoint_manager
        self.reporter = reporter
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.concurrency_limiter = ConcurrencyLimiter(max_concurrent)

    async def run(
        self,
        start_id: int,
        end_id: int,
        resume: bool = False,
    ) -> PipelineReport:
        """Run the pipeline.

        Args:
            start_id: Starting MAL ID
            end_id: Ending MAL ID
            resume: Whether to resume from checkpoint

        Returns:
            PipelineReport with execution results
        """
        # start_time = asyncio.get_event_loop().time()  # Unused

        # Initialize or load checkpoint
        if resume and self.checkpoint_manager.exists():
            state = self.checkpoint_manager.load()
            if state is None:
                logger.warning("Failed to load checkpoint, starting fresh")
                state = self.checkpoint_manager.create_new(start_id, end_id)
        else:
            state = self.checkpoint_manager.create_new(start_id, end_id)

        logger.info(
            f"Starting pipeline: {state.start_id}-{state.end_id} "
            f"({state.total_count} items, resume={resume})"
        )

        try:
            # Process batches
            state.current_stage = PipelineStage.FETCH

            while state.pending_ids:
                # Get next batch
                batch_ids = list(state.pending_ids)[: self.batch_size]

                # Move to in-progress
                state.in_progress_ids.update(batch_ids)
                state.pending_ids.difference_update(batch_ids)
                state.current_batch_index += 1

                logger.info(
                    f"Processing batch {state.current_batch_index}: "
                    f"{len(batch_ids)} items "
                    f"(total: {len(state.processed_ids)}/{state.total_count})"
                )

                # Process batch
                await self._process_batch(state, batch_ids)

                # Save checkpoint after batch
                self.checkpoint_manager.save(state)

            # Finalize
            state.current_stage = PipelineStage.COMPLETE
            state.stats.end_time = asyncio.get_event_loop().time()
            self.checkpoint_manager.save(state)

            # Generate report
            report = await self.reporter.generate(state, resumed=resume)

            logger.info(
                f"Pipeline complete: {report.successful} successful, " f"{report.failed} failed"
            )

            return report

        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            state.current_stage = PipelineStage.ERROR
            state.stats.end_time = asyncio.get_event_loop().time()

            # Add error to checkpoint
            self.checkpoint_manager.add_error(
                state,
                anime_id=None,
                stage=state.current_stage,
                error_type=type(e).__name__,
                error_message=str(e),
                stack_trace=traceback.format_exc(),
            )
            self.checkpoint_manager.save(state)

            raise

    async def _process_batch(self, state: CheckpointState, batch_ids: list[int]) -> None:
        """Process a batch of anime IDs.

        Args:
            state: Checkpoint state
            batch_ids: List of MAL IDs to process
        """
        # Process each anime ID
        tasks = [self._process_anime(state, anime_id) for anime_id in batch_ids]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Move processed from in-progress to processed
        state.in_progress_ids.clear()

    async def _process_anime(self, state: CheckpointState, anime_id: int) -> None:
        """Process a single anime through the pipeline.

        Args:
            state: Checkpoint state
            anime_id: MAL ID to process
        """
        async with self.concurrency_limiter:
            try:
                # 1. Fetch
                anime = await self.fetcher.fetch_anime(anime_id)

                if anime is None:
                    logger.debug(f"Anime {anime_id} not found, skipping")
                    self.checkpoint_manager.update_stats(state, skipped_increment=1)
                    state.processed_ids.add(anime_id)
                    return

                # 2. Save anime
                db_id = await self.storage.save_anime(anime, status="processing")

                # 3. Quality check
                state.current_stage = PipelineStage.QUALITY
                quality_result = self.quality_checker.check(anime)

                await self.storage.save_quality_check(db_id, quality_result)

                if quality_result.passed:
                    self.checkpoint_manager.update_stats(state, quality_passed_increment=1)
                else:
                    logger.debug(
                        f"Anime {anime_id} failed quality check: "
                        f"{quality_result.overall_reason}"
                    )
                    self.checkpoint_manager.update_stats(state, quality_failed_increment=1)
                    await self.storage.mark_anime_failed(anime_id)
                    state.processed_ids.add(anime_id)
                    return

                # 4. Wikidata match
                state.current_stage = PipelineStage.MATCH
                match_result = await self.matcher.match(anime)

                await self.storage.save_match(db_id, match_result)

                if match_result.is_match():
                    self.checkpoint_manager.update_stats(state, matched_increment=1)
                    logger.debug(f"Anime {anime_id} matched to {match_result.wikidata_id}")
                else:
                    self.checkpoint_manager.update_stats(state, unmatched_increment=1)

                # 5. Mark complete
                state.current_stage = PipelineStage.STORE
                await self.storage.mark_anime_completed(anime_id)

                self.checkpoint_manager.update_stats(state, processed_increment=1)
                state.processed_ids.add(anime_id)

            except Exception as e:
                logger.error(f"Error processing anime {anime_id}: {e}")
                self.checkpoint_manager.add_error(
                    state,
                    anime_id=anime_id,
                    stage=state.current_stage,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    stack_trace=traceback.format_exc(),
                )
                self.checkpoint_manager.update_stats(state, failed_increment=1)
                state.processed_ids.add(anime_id)  # Mark as processed to avoid retry
