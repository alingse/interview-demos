"""Tests for pipeline orchestration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from luma.pipeline.orchestrator import PipelineOrchestrator
from luma.pipeline.checkpoint import CheckpointManager
from luma.pipeline.reporter import PipelineReporter
from luma.core.fetch import AnimeFetcher
from luma.core.quality import QualityChecker
from luma.core.match import WikidataMatcher
from luma.core.storage import Storage
from luma.models.checkpoint import PipelineStage
from luma.models.anime import Anime
import tempfile


@pytest.fixture
def mock_components():
    """Create mocked pipeline components."""
    mock_fetcher = MagicMock(spec=AnimeFetcher)
    mock_fetcher.fetch_anime = AsyncMock(return_value=Anime(
        mal_id=1,
        title="Test Anime",
        episodes=12,
        score=8.5,
        year=2020,
    ))
    mock_fetcher.close = AsyncMock()

    mock_quality = MagicMock(spec=QualityChecker)
    from luma.models.quality import QualityResult
    mock_quality.check = MagicMock(return_value=QualityResult.pass_result())

    mock_matcher = MagicMock(spec=WikidataMatcher)
    from luma.models.match import MatchResult, MatchMethod
    mock_matcher.match = AsyncMock(return_value=MatchResult.no_match())
    mock_matcher.close = AsyncMock()

    mock_storage = MagicMock(spec=Storage)
    mock_storage.save_anime = AsyncMock(return_value=1)
    mock_storage.save_quality_check = AsyncMock(return_value=1)
    mock_storage.save_match = AsyncMock(return_value=1)
    mock_storage.mark_anime_completed = AsyncMock()
    mock_storage.mark_anime_failed = AsyncMock()

    with tempfile.NamedTemporaryFile(suffix=".json") as f:
        checkpoint_manager = CheckpointManager(f.name)

    reporter = MagicMock(spec=PipelineReporter)
    reporter.generate = AsyncMock()
    reporter.print_report = MagicMock()

    return {
        "fetcher": mock_fetcher,
        "quality": mock_quality,
        "matcher": mock_matcher,
        "storage": mock_storage,
        "checkpoint_manager": checkpoint_manager,
        "reporter": reporter,
    }


@pytest.mark.asyncio
async def test_orchestrator_run(mock_components):
    """Test pipeline orchestrator execution."""
    orchestrator = PipelineOrchestrator(
        fetcher=mock_components["fetcher"],
        quality_checker=mock_components["quality"],
        matcher=mock_components["matcher"],
        storage=mock_components["storage"],
        checkpoint_manager=mock_components["checkpoint_manager"],
        reporter=mock_components["reporter"],
        batch_size=10,
        max_concurrent=2,
    )

    report = await orchestrator.run(start_id=1, end_id=5)

    assert report is not None
    assert mock_components["fetcher"].fetch_anime.call_count == 5
    assert mock_components["storage"].save_anime.call_count == 5


@pytest.mark.asyncio
async def test_orchestrator_resume(mock_components):
    """Test pipeline resume from checkpoint."""
    # Create initial checkpoint
    state = mock_components["checkpoint_manager"].create_new(1, 10)
    state.processed_ids.add(1)
    state.pending_ids.discard(1)
    mock_components["checkpoint_manager"].save(state)

    orchestrator = PipelineOrchestrator(
        fetcher=mock_components["fetcher"],
        quality_checker=mock_components["quality"],
        matcher=mock_components["matcher"],
        storage=mock_components["storage"],
        checkpoint_manager=mock_components["checkpoint_manager"],
        reporter=mock_components["reporter"],
    )

    report = await orchestrator.run(start_id=1, end_id=10, resume=True)

    assert report is not None
