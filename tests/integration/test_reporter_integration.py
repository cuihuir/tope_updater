"""Integration tests for reporter with download and deploy services."""

import asyncio
import json
import pytest
from pathlib import Path
from typing import List, Dict, Any
from unittest.mock import patch, MagicMock, AsyncMock, call
import zipfile
import hashlib

from updater.services.download import DownloadService
from updater.services.deploy import DeployService
from updater.services.reporter import ReportService
from updater.services.state_manager import StateManager
from updater.models.status import StageEnum


@pytest.mark.integration
class TestReporterIntegration:
    """Integration tests for reporter with services."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Setup and teardown for each test."""
        # Reset singletons
        StateManager._instance = None
        ReportService._instance = None

        yield

        # Cleanup
        StateManager._instance = None
        ReportService._instance = None

    @pytest.mark.asyncio
    async def test_download_service_reports_progress(self, tmp_path):
        """Test that DownloadService reports progress to device-api."""
        # Arrange
        test_content = b"Test package content" * 100  # ~2KB
        md5_hash = hashlib.md5(test_content).hexdigest()

        # Mock reporter to track calls
        with patch.object(ReportService, 'report_progress', new_callable=AsyncMock) as mock_report:
            reporter = ReportService()
            download_service = DownloadService(reporter=reporter)

            # Mock httpx to serve the test file
            async def mock_aiter_bytes(chunk_size=8192):
                yield test_content

            mock_response = AsyncMock()
            mock_response.headers = {'content-length': str(len(test_content))}
            mock_response.aiter_bytes = mock_aiter_bytes
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.stream = MagicMock()
            mock_client.stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_client.stream.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            with patch('updater.services.download.httpx.AsyncClient', return_value=mock_client):
                # Act
                await download_service.download_package(
                    version="1.0.0",
                    package_url="http://test.com/package.zip",
                    package_name="test_package.zip",
                    package_size=len(test_content),
                    package_md5=md5_hash,
                )

            # Assert
            assert mock_report.call_count > 0, "Should have called report_progress"

            # Check first call - should be DOWNLOADING
            first_call = mock_report.call_args_list[0]
            assert first_call.kwargs['stage'] == StageEnum.DOWNLOADING

            # Check last call - should be TO_INSTALL (success)
            last_call = mock_report.call_args_list[-1]
            assert last_call.kwargs['stage'] == StageEnum.TO_INSTALL
            assert last_call.kwargs['progress'] == 100
            assert last_call.kwargs.get('error') is None

    @pytest.mark.asyncio
    async def test_download_service_reports_failure(self):
        """Test that DownloadService reports failures to device-api."""
        # Arrange
        valid_md5 = "d41d8cd98f00b204e9800998ecf8427e"

        # Mock reporter to track calls
        with patch.object(ReportService, 'report_progress', new_callable=AsyncMock) as mock_report:
            reporter = ReportService()
            download_service = DownloadService(reporter=reporter)

            # Mock httpx to simulate network error
            import httpx
            mock_client = AsyncMock()
            mock_client.stream = MagicMock(side_effect=httpx.RequestError("Network error"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            with patch('updater.services.download.httpx.AsyncClient', return_value=mock_client):
                # Act
                await download_service.download_package(
                    version="1.0.0",
                    package_url="http://test.com/package.zip",
                    package_name="test_package.zip",
                    package_size=1000,
                    package_md5=valid_md5,
                )

            # Assert
            assert mock_report.call_count > 0

            # Find FAILED stage call
            failed_calls = [c for c in mock_report.call_args_list
                          if c.kwargs['stage'] == StageEnum.FAILED]
            assert len(failed_calls) > 0, "Should have FAILED stage report"

            # Check error message
            failed_call = failed_calls[0]
            assert failed_call.kwargs['error'] is not None
            assert 'DOWNLOAD_FAILED' in failed_call.kwargs['error']

    @pytest.mark.asyncio
    async def test_deploy_service_reports_progress(self, tmp_path):
        """Test that DeployService reports progress to device-api."""
        # Arrange
        # Mock reporter to track calls
        with patch.object(ReportService, 'report_progress', new_callable=AsyncMock) as mock_report:
            reporter = ReportService()

            # Mock ProcessManager
            mock_process_manager = MagicMock()
            mock_process_manager.stop_service = AsyncMock()
            mock_process_manager.start_service = AsyncMock()
            mock_process_manager.get_service_status = MagicMock(return_value="active")

            deploy_service = DeployService(
                reporter=reporter,
                process_manager=mock_process_manager
            )

            # Create test package
            package_path = tmp_path / "test_package.zip"
            manifest_content = {
                "version": "1.0.0",
                "modules": [
                    {
                        "name": "test-module",
                        "src": "test.txt",
                        "dst": str(tmp_path / "deploy" / "test.txt"),
                    }
                ]
            }

            with zipfile.ZipFile(package_path, 'w') as zf:
                zf.writestr('manifest.json', json.dumps(manifest_content))
                zf.writestr('test.txt', 'test content')

            # Act
            await deploy_service.deploy_package(package_path, "1.0.0")

            # Assert
            assert mock_report.call_count > 0, "Should have called report_progress"

            # Check for INSTALLING stage
            installing_calls = [c for c in mock_report.call_args_list
                              if c.kwargs['stage'] == StageEnum.INSTALLING]
            assert len(installing_calls) > 0, "Should have INSTALLING stage reports"

            # Check last call - should be SUCCESS
            last_call = mock_report.call_args_list[-1]
            assert last_call.kwargs['stage'] == StageEnum.SUCCESS
            assert last_call.kwargs['progress'] == 100
            assert last_call.kwargs.get('error') is None

    @pytest.mark.asyncio
    async def test_deploy_service_reports_failure_and_rollback(self, tmp_path):
        """Test that DeployService reports deployment failure and rollback."""
        # Arrange
        with patch.object(ReportService, 'report_progress', new_callable=AsyncMock) as mock_report:
            reporter = ReportService()

            # Mock ProcessManager to simulate failure
            mock_process_manager = MagicMock()
            mock_process_manager.stop_service = AsyncMock()
            mock_process_manager.start_service = AsyncMock(
                side_effect=RuntimeError("Service failed to start")
            )
            mock_process_manager.get_service_status = MagicMock(return_value="inactive")

            deploy_service = DeployService(
                reporter=reporter,
                process_manager=mock_process_manager
            )

            # Create test package
            package_path = tmp_path / "test_package.zip"
            manifest_content = {
                "version": "1.0.0",
                "modules": [
                    {
                        "name": "test-module",
                        "src": "test.txt",
                        "dst": str(tmp_path / "deploy" / "test.txt"),
                        "process_name": "test-service"
                    }
                ]
            }

            with zipfile.ZipFile(package_path, 'w') as zf:
                zf.writestr('manifest.json', json.dumps(manifest_content))
                zf.writestr('test.txt', 'test content')

            # Act
            await deploy_service.deploy_package(package_path, "1.0.0")

            # Assert
            assert mock_report.call_count > 0

            # Check for FAILED stage
            failed_calls = [c for c in mock_report.call_args_list
                          if c.kwargs['stage'] == StageEnum.FAILED]
            assert len(failed_calls) > 0, "Should have FAILED stage report"

            # Check error message contains deployment failure and rollback info
            last_failed_call = failed_calls[-1]
            assert last_failed_call.kwargs['error'] is not None
            assert 'DEPLOYMENT_FAILED' in last_failed_call.kwargs['error']

    @pytest.mark.asyncio
    async def test_reporter_singleton_behavior(self):
        """Test that ReportService maintains singleton behavior."""
        # Act
        reporter1 = ReportService()
        reporter2 = ReportService()

        # Assert
        assert reporter1 is reporter2, "ReportService should be a singleton"

    @pytest.mark.asyncio
    async def test_download_preserves_progress_on_failure(self):
        """Test that download failure reports preserve progress for analysis."""
        # Arrange
        test_content = b"X" * 1000
        half_content = test_content[:500]
        valid_md5 = hashlib.md5(test_content).hexdigest()

        with patch.object(ReportService, 'report_progress', new_callable=AsyncMock) as mock_report:
            reporter = ReportService()
            download_service = DownloadService(reporter=reporter)

            # Mock httpx to simulate failure at 50%
            import httpx

            async def mock_aiter_bytes(chunk_size=8192):
                yield half_content
                raise httpx.RequestError("Connection lost")

            mock_response = AsyncMock()
            mock_response.headers = {'content-length': str(len(test_content))}
            mock_response.aiter_bytes = mock_aiter_bytes
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.stream = MagicMock()
            mock_client.stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_client.stream.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            with patch('updater.services.download.httpx.AsyncClient', return_value=mock_client):
                # Act
                await download_service.download_package(
                    version="1.0.0",
                    package_url="http://test.com/package.zip",
                    package_name="test_package.zip",
                    package_size=len(test_content),
                    package_md5=valid_md5,
                )

            # Assert
            failed_calls = [c for c in mock_report.call_args_list
                          if c.kwargs['stage'] == StageEnum.FAILED]
            assert len(failed_calls) > 0

            # Progress should be preserved (around 50%), not 0
            failed_call = failed_calls[0]
            assert failed_call.kwargs['progress'] > 0, "Progress should be preserved on failure"
            assert failed_call.kwargs['progress'] < 100, "Progress should not be 100% on failure"
