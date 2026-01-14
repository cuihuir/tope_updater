"""Unit tests for ReportService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from updater.services.reporter import ReportService
from updater.models.status import StageEnum


@pytest.mark.unit
class TestReportService:
    """Test ReportService in isolation."""

    @pytest.fixture
    def report_service(self):
        """Create ReportService instance."""
        return ReportService(device_api_url="http://test-api:9080")

    @pytest.mark.asyncio
    async def test_init_default_url(self):
        """Test ReportService initialization with default URL."""
        # Act
        service = ReportService()

        # Assert
        assert service.device_api_url == "http://localhost:9080"
        assert service.report_endpoint == "http://localhost:9080/api/v1.0/ota/report"

    @pytest.mark.asyncio
    async def test_init_custom_url(self):
        """Test ReportService initialization with custom URL."""
        # Act
        service = ReportService(device_api_url="http://custom:8080")

        # Assert
        assert service.device_api_url == "http://custom:8080"
        assert service.report_endpoint == "http://custom:8080/api/v1.0/ota/report"

    @pytest.mark.asyncio
    async def test_report_progress_success(self, report_service):
        """Test successful progress report."""
        # Arrange
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch('updater.services.reporter.httpx.AsyncClient', return_value=mock_client):
            # Act
            await report_service.report_progress(
                stage=StageEnum.DOWNLOADING,
                progress=50,
                message="Downloading package...",
                error=None
            )

            # Assert
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "http://test-api:9080/api/v1.0/ota/report"

            # Verify payload structure
            payload = call_args[1]['json']
            assert payload['stage'] == 'downloading'
            assert payload['progress'] == 50
            assert payload['message'] == "Downloading package..."
            assert payload['error'] is None

    @pytest.mark.asyncio
    async def test_report_progress_with_error(self, report_service):
        """Test progress report with error message."""
        # Arrange
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch('updater.services.reporter.httpx.AsyncClient', return_value=mock_client):
            # Act
            await report_service.report_progress(
                stage=StageEnum.FAILED,
                progress=0,
                message="Update failed",
                error="MD5_MISMATCH: checksum verification failed"
            )

            # Assert
            payload = mock_client.post.call_args[1]['json']
            assert payload['stage'] == 'failed'
            assert payload['progress'] == 0
            assert payload['error'] == "MD5_MISMATCH: checksum verification failed"

    @pytest.mark.asyncio
    async def test_report_progress_all_stages(self, report_service):
        """Test reporting all lifecycle stages."""
        # Arrange
        stages = [
            (StageEnum.IDLE, 0, "Idle"),
            (StageEnum.DOWNLOADING, 50, "Downloading"),
            (StageEnum.VERIFYING, 75, "Verifying"),
            (StageEnum.TO_INSTALL, 100, "Ready to install"),
            (StageEnum.INSTALLING, 80, "Installing"),
            (StageEnum.SUCCESS, 100, "Success"),
            (StageEnum.REBOOTING, 100, "Rebooting"),
            (StageEnum.FAILED, 0, "Failed"),
        ]

        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch('updater.services.reporter.httpx.AsyncClient', return_value=mock_client):
            # Act - report all stages
            for stage, progress, message in stages:
                await report_service.report_progress(
                    stage=stage,
                    progress=progress,
                    message=message
                )

            # Assert - all stages were reported
            assert mock_client.post.call_count == len(stages)

    @pytest.mark.asyncio
    async def test_report_progress_http_error_does_not_raise(self, report_service):
        """Test HTTP errors are logged but not raised."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.HTTPStatusError(
            "Server error",
            request=MagicMock(),
            response=MagicMock()
        ))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch('updater.services.reporter.httpx.AsyncClient', return_value=mock_client):
            # Act - should not raise exception
            await report_service.report_progress(
                stage=StageEnum.DOWNLOADING,
                progress=30,
                message="Test"
            )

            # Assert - completed without exception

    @pytest.mark.asyncio
    async def test_report_progress_network_error_does_not_raise(self, report_service):
        """Test network errors are logged but not raised."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch('updater.services.reporter.httpx.AsyncClient', return_value=mock_client):
            # Act - should not raise exception
            await report_service.report_progress(
                stage=StageEnum.INSTALLING,
                progress=50,
                message="Test"
            )

            # Assert - completed without exception

    @pytest.mark.asyncio
    async def test_report_progress_timeout_error_does_not_raise(self, report_service):
        """Test timeout errors are logged but not raised."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch('updater.services.reporter.httpx.AsyncClient', return_value=mock_client):
            # Act - should not raise exception
            await report_service.report_progress(
                stage=StageEnum.VERIFYING,
                progress=90,
                message="Test"
            )

            # Assert - completed without exception

    @pytest.mark.asyncio
    async def test_report_progress_unexpected_exception_does_not_raise(self, report_service):
        """Test unexpected exceptions are logged but not raised."""
        # Arrange
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=RuntimeError("Unexpected error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch('updater.services.reporter.httpx.AsyncClient', return_value=mock_client):
            # Act - should not raise exception
            await report_service.report_progress(
                stage=StageEnum.FAILED,
                progress=0,
                message="Test"
            )

            # Assert - completed without exception

    @pytest.mark.asyncio
    async def test_report_progress_timeout_config(self, report_service):
        """Test that httpx client uses 5 second timeout."""
        # Arrange
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch('updater.services.reporter.httpx.AsyncClient') as mock_client_class:
            mock_client_class.return_value = mock_client

            # Act
            await report_service.report_progress(
                stage=StageEnum.IDLE,
                progress=0,
                message="Test"
            )

            # Assert - verify timeout was set to 5.0 seconds
            mock_client_class.assert_called_once_with(timeout=5.0)

    @pytest.mark.asyncio
    async def test_report_progress_boundary_values(self, report_service):
        """Test reporting with boundary progress values."""
        # Arrange
        boundary_cases = [
            (0, "Start"),      # Minimum progress
            (50, "Middle"),    # Middle progress
            (100, "Complete"), # Maximum progress
        ]

        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch('updater.services.reporter.httpx.AsyncClient', return_value=mock_client):
            # Act
            for progress, message in boundary_cases:
                await report_service.report_progress(
                    stage=StageEnum.DOWNLOADING,
                    progress=progress,
                    message=message
                )

            # Assert
            assert mock_client.post.call_count == len(boundary_cases)

            # Verify all calls succeeded
            for i, (progress, message) in enumerate(boundary_cases):
                payload = mock_client.post.call_args_list[i][1]['json']
                assert payload['progress'] == progress
                assert payload['message'] == message
