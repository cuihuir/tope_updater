"""Status enums and models for OTA updater."""

from enum import Enum


class StageEnum(str, Enum):
    """OTA lifecycle stages.

    State transitions:
    idle → downloading → verifying → toInstall → installing → rebooting → success
                ↓            ↓           ↓            ↓
              failed ←─────────────────────────────────
    """

    IDLE = "idle"
    DOWNLOADING = "downloading"
    VERIFYING = "verifying"
    TO_INSTALL = "toInstall"
    INSTALLING = "installing"
    REBOOTING = "rebooting"
    SUCCESS = "success"
    FAILED = "failed"
