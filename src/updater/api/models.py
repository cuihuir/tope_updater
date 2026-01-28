"""Pydantic models for HTTP API requests and responses."""

from typing import Optional
from pydantic import BaseModel, Field

from updater.models.status import StageEnum


class DownloadRequest(BaseModel):
    """POST /api/v1.0/download payload.

    Triggers async package download from cloud storage.

    Example:
        {
            "version": "1.0.0",
            "package_url": "http://localhost:8888/test-update-1.0.0.zip",
            "package_name": "test-update-1.0.0.zip",
            "package_size": 468,
            "package_md5": "600aff0f78265dd25bb6907828f916dd"
        }
    """

    version: str = Field(
        ...,
        pattern=r"^\d+\.\d+\.\d+$",
        description="Semantic version (e.g., 1.0.0)",
        examples=["1.0.0", "2.1.3"]
    )
    package_url: str = Field(
        ...,
        pattern=r"^https?://.+",
        description="HTTP/HTTPS URL to download package",
        examples=["http://localhost:8888/test-update-1.0.0.zip", "https://s3.example.com/updates/v1.0.0.zip"]
    )
    package_name: str = Field(
        ...,
        description="Filename for local storage",
        examples=["test-update-1.0.0.zip", "firmware-v2.0.0.zip"]
    )
    package_size: int = Field(
        ...,
        gt=0,
        description="Total size in bytes",
        examples=[468, 1048576, 3221225472]
    )
    package_md5: str = Field(
        ...,
        pattern=r"^[a-f0-9]{32}$",
        description="Expected MD5 hash (32-char hex)",
        examples=["600aff0f78265dd25bb6907828f916dd", "d41d8cd98f00b204e9800998ecf8427e"]
    )


class UpdateRequest(BaseModel):
    """POST /api/v1.0/update payload.

    Triggers async installation of downloaded package.

    Example:
        {
            "version": "1.0.0"
        }
    """

    version: str = Field(
        ...,
        pattern=r"^\d+\.\d+\.\d+$",
        description="Version to install (must match downloaded package)",
        examples=["1.0.0", "2.1.3"]
    )


class ProgressData(BaseModel):
    """Progress data nested in response."""

    stage: StageEnum = Field(..., description="Current lifecycle stage")
    progress: int = Field(..., ge=0, le=100, description="Percentage completion (0-100)")
    message: str = Field(..., description="Human-readable status description")
    error: Optional[str] = Field(
        None, description="Error code and message if stage == failed"
    )


class ProgressResponse(BaseModel):
    """GET /api/v1.0/progress response.

    Returns current status state with application-level status code.
    """

    code: int = Field(..., description="Application-level status code (200/500)")
    msg: str = Field(..., description="Status message or error description")
    data: ProgressData = Field(..., description="Progress data")
    stage: Optional[StageEnum] = Field(
        None, description="Current stage (for failed responses at root level)"
    )
    progress: Optional[int] = Field(
        None, description="Current progress (for failed responses at root level)"
    )


class SuccessResponse(BaseModel):
    """Success response for command endpoints.

    Used by POST /download and POST /update when operation starts successfully.
    """

    code: int = Field(default=200, description="Application-level status code (200)")
    msg: str = Field(default="success", description="Success message")
    data: Optional[dict] = Field(None, description="Optional response data")


class ErrorResponse(BaseModel):
    """Error response for all endpoints.

    HTTP status code is always 200, real status in 'code' field.
    """

    code: int = Field(
        ..., description="Application-level error code (400/404/409/410/500)"
    )
    msg: str = Field(..., description="Error message with error code prefix")
    stage: Optional[StageEnum] = Field(
        None, description="Current stage (for operation state errors)"
    )
    progress: Optional[int] = Field(
        None, description="Current progress (for operation state errors)"
    )


class ReportPayload(BaseModel):
    """Payload for POST to device-api /api/v1.0/ota/report.

    Used for callbacks to device-api every 5% progress and stage transitions.
    """

    stage: StageEnum = Field(..., description="Current OTA lifecycle stage")
    progress: int = Field(..., ge=0, le=100, description="Percentage completion")
    message: str = Field(..., description="Human-readable status description")
    error: Optional[str] = Field(
        None, description="Error code and message if stage == failed"
    )
