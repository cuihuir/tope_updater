"""Progress reporting service for device-api callbacks."""

import logging
from typing import Optional

import httpx

from updater.api.models import ReportPayload
from updater.models.status import StageEnum


class ReportService:
    """Handles progress reporting to device-api."""

    def __init__(self, device_api_url: str = "http://localhost:9080"):
        """Initialize report service.

        Args:
            device_api_url: Base URL of device-api service (default: http://localhost:9080)
        """
        self.logger = logging.getLogger("updater.reporter")
        self.device_api_url = device_api_url
        self.report_endpoint = f"{device_api_url}/api/v1.0/ota/report"

    async def report_progress(
        self,
        stage: StageEnum,
        progress: int,
        message: str,
        error: Optional[str] = None,
    ) -> None:
        """Send progress report to device-api.

        Args:
            stage: Current OTA lifecycle stage
            progress: Percentage completion (0-100)
            message: Human-readable status description
            error: Error message if stage == failed

        Note:
            Failures are logged but not raised to avoid blocking OTA operations
        """
        payload = ReportPayload(
            stage=stage,
            progress=progress,
            message=message,
            error=error,
        )

        self.logger.debug(
            f"Reporting to device-api: stage={stage.value}, progress={progress}%"
        )

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    self.report_endpoint,
                    json=payload.model_dump(mode="json"),
                )
                response.raise_for_status()
                self.logger.debug(f"Report sent successfully")

        except httpx.HTTPError as e:
            self.logger.warning(
                f"Failed to report progress to device-api: {e}. "
                f"Continuing OTA operation..."
            )
        except Exception as e:
            self.logger.error(
                f"Unexpected error reporting to device-api: {e}",
                exc_info=True,
            )
