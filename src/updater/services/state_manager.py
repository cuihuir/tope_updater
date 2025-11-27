"""State manager for persistent state and in-memory status."""

import json
from pathlib import Path
from typing import Optional
import logging

from updater.models.state import StateFile
from updater.models.status import StageEnum
from updater.api.models import ProgressData


class StateManager:
    """Singleton state manager for OTA operations.

    Manages:
    - In-memory status state (for GET /progress endpoint)
    - Persistent state file at ./tmp/state.json (for resumable downloads)
    """

    _instance: Optional["StateManager"] = None

    def __new__(cls):
        """Implement singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize state manager (only once due to singleton)."""
        if self._initialized:
            return

        self.logger = logging.getLogger("updater.state_manager")
        self.state_file_path = Path("./tmp/state.json")

        # In-memory status state (for GET /progress)
        self._current_stage: StageEnum = StageEnum.IDLE
        self._current_progress: int = 0
        self._current_message: str = "Updater ready"
        self._current_error: Optional[str] = None

        # Persistent state (for resumable downloads)
        self._persistent_state: Optional[StateFile] = None

        self._initialized = True
        self.logger.info("StateManager initialized")

    def get_status(self) -> ProgressData:
        """Get current status for GET /progress endpoint.

        Returns:
            ProgressData with current stage, progress, message, error
        """
        return ProgressData(
            stage=self._current_stage,
            progress=self._current_progress,
            message=self._current_message,
            error=self._current_error,
        )

    def update_status(
        self,
        stage: StageEnum,
        progress: int,
        message: str,
        error: Optional[str] = None,
    ) -> None:
        """Update in-memory status state.

        Args:
            stage: Current lifecycle stage
            progress: Percentage completion (0-100)
            message: Human-readable description
            error: Error message if stage == failed
        """
        self._current_stage = stage
        self._current_progress = progress
        self._current_message = message
        self._current_error = error
        self.logger.debug(
            f"Status updated: stage={stage.value}, progress={progress}%, message={message}"
        )

    def load_state(self) -> Optional[StateFile]:
        """Load persistent state from ./tmp/state.json.

        Returns:
            StateFile if exists and valid, None otherwise
        """
        if not self.state_file_path.exists():
            self.logger.debug("No state file found")
            return None

        try:
            with open(self.state_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            state = StateFile(**data)
            self._persistent_state = state
            self.logger.info(f"Loaded state: version={state.version}, stage={state.stage.value}")
            return state
        except Exception as e:
            self.logger.error(f"Failed to load state file: {e}", exc_info=True)
            # Corrupted state file, delete it per FR-026
            self.state_file_path.unlink(missing_ok=True)
            return None

    def save_state(self, state: StateFile) -> None:
        """Save persistent state to ./tmp/state.json.

        Args:
            state: StateFile to persist
        """
        try:
            self.state_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file_path, "w", encoding="utf-8") as f:
                json.dump(state.model_dump(mode="json"), f, indent=2)
            self._persistent_state = state
            self.logger.debug(f"Saved state: version={state.version}, bytes={state.bytes_downloaded}")
        except Exception as e:
            self.logger.error(f"Failed to save state file: {e}", exc_info=True)
            raise

    def delete_state(self) -> None:
        """Delete persistent state file (called after successful update or on errors)."""
        if self.state_file_path.exists():
            self.state_file_path.unlink()
            self._persistent_state = None
            self.logger.info("Deleted state file")

    def get_persistent_state(self) -> Optional[StateFile]:
        """Get current persistent state without reloading from disk.

        Returns:
            Cached StateFile if loaded, None otherwise
        """
        return self._persistent_state

    def reset(self) -> None:
        """Reset to idle state (called after success or failure cleanup)."""
        self._current_stage = StageEnum.IDLE
        self._current_progress = 0
        self._current_message = "Updater ready"
        self._current_error = None
        self._persistent_state = None
        self.logger.info("State reset to idle")
