"""Tests for checkpoint management."""

import pytest
from pathlib import Path
import tempfile

from luma.pipeline.checkpoint import CheckpointManager
from luma.models.checkpoint import PipelineStage


@pytest.fixture
def temp_checkpoint_path():
    """Create temporary checkpoint path."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        yield f.name
    # Cleanup


def test_create_new_checkpoint(temp_checkpoint_path):
    """Test creating a new checkpoint."""
    manager = CheckpointManager(temp_checkpoint_path)
    state = manager.create_new(1, 100)

    assert state.checkpoint_id is not None
    assert state.start_id == 1
    assert state.end_id == 100
    assert state.total_count == 100
    assert len(state.pending_ids) == 100
    assert len(state.processed_ids) == 0
    assert state.current_stage == PipelineStage.IDLE


def test_save_and_load_checkpoint(temp_checkpoint_path):
    """Test saving and loading checkpoint."""
    manager = CheckpointManager(temp_checkpoint_path)
    state = manager.create_new(1, 100)

    # Modify state
    state.processed_ids.add(1)
    state.processed_ids.add(2)
    state.pending_ids.difference_update([1, 2])
    state.current_stage = PipelineStage.FETCH

    # Save
    manager.save(state)

    # Load
    loaded_state = manager.load()

    assert loaded_state is not None
    assert loaded_state.checkpoint_id == state.checkpoint_id
    assert loaded_state.start_id == 1
    assert loaded_state.end_id == 100
    assert 1 in loaded_state.processed_ids
    assert 2 in loaded_state.processed_ids
    assert 1 not in loaded_state.pending_ids
    assert loaded_state.current_stage == PipelineStage.FETCH


def test_checkpoint_exists(temp_checkpoint_path):
    """Test checkpoint existence check."""
    manager = CheckpointManager(temp_checkpoint_path)

    assert manager.exists() is False

    state = manager.create_new(1, 100)
    manager.save(state)

    assert manager.exists() is True


def test_clear_checkpoint(temp_checkpoint_path):
    """Test clearing checkpoint."""
    manager = CheckpointManager(temp_checkpoint_path)

    state = manager.create_new(1, 100)
    manager.save(state)
    assert manager.exists() is True

    manager.clear()
    assert manager.exists() is False


def test_load_nonexistent_checkpoint(temp_checkpoint_path):
    """Test loading non-existent checkpoint returns None."""
    manager = CheckpointManager(temp_checkpoint_path)
    state = manager.load()

    assert state is None


def test_update_stats(temp_checkpoint_path):
    """Test updating checkpoint statistics."""
    manager = CheckpointManager(temp_checkpoint_path)
    state = manager.create_new(1, 100)

    manager.update_stats(
        state,
        processed_increment=10,
        failed_increment=2,
        quality_passed_increment=8,
        matched_increment=5,
    )

    assert state.stats.processed == 10
    assert state.stats.failed == 2
    assert state.stats.quality_passed == 8
    assert state.stats.matched == 5
