"""State file model for persistent OTA state."""

from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, Field, field_validator

from updater.models.status import StageEnum


class StateFile(BaseModel):
    """Persistent state at ./tmp/state.json.

    Survives reboots for resumable downloads and self-healing.
    """

    version: str = Field(..., description="Version being downloaded/installed")
    package_url: str = Field(..., description="Original download URL")
    package_name: str = Field(..., description="Target filename")
    package_size: int = Field(..., gt=0, description="Total expected bytes")
    package_md5: str = Field(
        ..., pattern=r"^[a-f0-9]{32}$", description="Expected MD5 hash"
    )
    bytes_downloaded: int = Field(
        default=0, ge=0, description="Current byte position for resume"
    )
    last_update: datetime = Field(
        default_factory=datetime.now, description="Last state update timestamp"
    )
    stage: StageEnum = Field(..., description="Last known stage")
    verified_at: Optional[datetime] = Field(
        None, description="Timestamp when MD5 verification completed"
    )

    @field_validator("last_update", "verified_at", mode="before")
    @classmethod
    def parse_iso8601(cls, v):
        """Parse ISO 8601 timestamp strings."""
        if v is None:
            return None
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v

    def is_package_expired(self) -> bool:
        """Check if package has exceeded 24-hour trust window.

        Returns:
            True if verified_at exists and >24h old, False otherwise
        """
        if self.verified_at is None:
            return False
        return (datetime.now() - self.verified_at) > timedelta(hours=24)

    class Config:
        """Pydantic config."""

        json_encoders = {datetime: lambda v: v.isoformat()}
