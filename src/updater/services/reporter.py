"""Progress reporting service for device-api callbacks."""

import logging
from typing import Optional

import httpx

from updater.api.models import ReportPayload
from updater.models.status import StageEnum
from updater.utils.version import format_report_version


class ReportService:
    """Singleton service for progress reporting to device-api."""

    _instance: Optional["ReportService"] = None

    def __new__(cls, device_api_url: str = "http://localhost:9080"):
        """Implement singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, device_api_url: str = "http://localhost:9080"):
        """Initialize report service (only once due to singleton).

        Args:
            device_api_url: Base URL of device-api service (default: http://localhost:9080)
        """
        if self._initialized:
            return

        self.logger = logging.getLogger("updater.reporter")
        self.device_api_url = device_api_url
        self.report_endpoint = f"{device_api_url}/api/v1.0/ota/report"
        self._initialized = True
        self.logger.info("ReportService initialized")

    async def report_progress(
        self,
        stage: StageEnum,
        progress: int,
        message: str,
        error: Optional[str] = None,
        version: Optional[str] = None,
    ) -> bool:
        """Send progress report to device-api.

        Args:
            stage: Current OTA lifecycle stage
            progress: Percentage completion (0-100)
            message: Human-readable status description
            error: Error message if stage == failed
            version: OTA target version; reported with v prefix

        Note:
            Failures are logged but not raised to avoid blocking OTA operations

        Returns:
            True when device-api accepted the report, False otherwise.
        """
        payload = ReportPayload(
            stage=stage,
            progress=progress,
            message=message,
            error=error,
            version=format_report_version(version),
        )
        payload_json = payload.model_dump(mode="json")

        self.logger.info(
            f"device-api report request: endpoint={self.report_endpoint}, "
            f"payload={payload_json}"
        )

        try:
            async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
                response = await client.post(
                    self.report_endpoint,
                    json=payload_json,
                )
                self.logger.info(
                    "device-api report response: "
                    f"status_code={response.status_code}, "
                    f"response_body={response.text}"
                )
                response.raise_for_status()
                return True

        except httpx.HTTPError as e:
            response = getattr(e, "response", None)
            if response is not None:
                self.logger.warning(
                    "device-api report failed: "
                    f"status_code={response.status_code}, "
                    f"response_body={response.text}, "
                    f"payload={payload_json}"
                )
            self.logger.warning(
                f"Failed to report progress to device-api: {e}. "
                f"Continuing OTA operation..."
            )
            return False
        except Exception as e:
            self.logger.error(
                f"Unexpected error reporting to device-api: {e}. "
                f"payload={payload_json}",
                exc_info=True,
            )
            return False
