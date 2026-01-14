"""Unit tests for StateManager."""

import json
import pytest
from pathlib import Path

from updater.services.state_manager import StateManager
from updater.models.status import StageEnum


@pytest.mark.unit
class TestStateManager:
    """Test StateManager in isolation."""

    def test_singleton_pattern(self):
        """Test that StateManager follows singleton pattern."""
        manager1 = StateManager()
        manager2 = StateManager()
        assert manager1 is manager2

    def test_initial_state(self):
        """Test initial state after initialization."""
        manager = StateManager()
        status = manager.get_status()
        
        assert status.stage == StageEnum.IDLE
        assert status.progress == 0
        assert status.message == "Updater ready"
        assert status.error is None

    def test_update_status(self):
        """Test updating in-memory status."""
        manager = StateManager()
        
        manager.update_status(
            stage=StageEnum.DOWNLOADING,
            progress=50,
            message="Downloading package",
            error=None
        )
        
        status = manager.get_status()
        assert status.stage == StageEnum.DOWNLOADING
        assert status.progress == 50
        assert status.message == "Downloading package"
        assert status.error is None

    def test_update_status_with_error(self):
        """Test updating status with error."""
        manager = StateManager()
        
        manager.update_status(
            stage=StageEnum.FAILED,
            progress=0,
            message="Download failed",
            error="Network timeout"
        )
        
        status = manager.get_status()
        assert status.stage == StageEnum.FAILED
        assert status.error == "Network timeout"

    def test_reset_state(self):
        """Test resetting to idle state."""
        manager = StateManager()
        
        # Update to some state
        manager.update_status(
            stage=StageEnum.DOWNLOADING,
            progress=50,
            message="Downloading",
            error=None
        )
        
        # Reset
        manager.reset()
        
        # Verify back to idle
        status = manager.get_status()
        assert status.stage == StageEnum.IDLE
        assert status.progress == 0
        assert status.message == "Updater ready"
        assert status.error is None

    def test_load_state_no_file(self, tmp_path):
        """Test loading state when no file exists."""
        manager = StateManager()
        manager.state_file_path = tmp_path / "state.json"
        
        state = manager.load_state()
        assert state is None

    def test_save_and_load_state(self, tmp_path):
        """Test saving and loading persistent state."""
        from updater.models.state import StateFile
        
        manager = StateManager()
        manager.state_file_path = tmp_path / "state.json"
        
        # Save state
        test_state = StateFile(
            version="1.0.0",
            stage=StageEnum.DOWNLOADING,
            bytes_downloaded=1024,
            package_url="http://example.com/package.zip",
            package_name="package.zip",
            package_size=2048,
            package_md5="098f6bcd4621d373cade4e832627b4f6"  # Valid MD5 hash
        )
        manager.save_state(test_state)
        
        # Verify file exists
        assert manager.state_file_path.exists()
        
        # Load state
        loaded_state = manager.load_state()
        assert loaded_state is not None
        assert loaded_state.version == "1.0.0"
        assert loaded_state.stage == StageEnum.DOWNLOADING
        assert loaded_state.bytes_downloaded == 1024

    def test_delete_state(self, tmp_path):
        """Test deleting state file."""
        from updater.models.state import StateFile
        
        manager = StateManager()
        manager.state_file_path = tmp_path / "state.json"
        
        # Create state file
        test_state = StateFile(
            version="1.0.0",
            stage=StageEnum.DOWNLOADING,
            bytes_downloaded=1024,
            package_url="http://example.com/package.zip",
            package_name="package.zip",
            package_size=2048,
            package_md5="098f6bcd4621d373cade4e832627b4f6"  # Valid MD5 hash
        )
        manager.save_state(test_state)
        
        # Delete
        manager.delete_state()
        
        # Verify deleted
        assert not manager.state_file_path.exists()
        assert manager.get_persistent_state() is None

    def test_load_corrupted_state(self, tmp_path):
        """Test loading corrupted state file."""
        manager = StateManager()
        manager.state_file_path = tmp_path / "state.json"
        
        # Create corrupted state file
        with open(manager.state_file_path, 'w') as f:
            f.write("{ invalid json }")
        
        # Load should return None and delete corrupted file
        state = manager.load_state()
        assert state is None
        assert not manager.state_file_path.exists()
