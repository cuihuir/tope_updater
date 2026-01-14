"""Unit tests for ProcessManager."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from updater.services.process import ProcessManager, ServiceStatus


@pytest.mark.unit
class TestProcessManager:
    """Test ProcessManager in isolation."""

    @pytest.fixture
    def process_manager(self):
        """Create ProcessManager instance."""
        return ProcessManager()

    @pytest.mark.asyncio
    async def test_get_service_status_active(self, process_manager):
        """Test getting active service status."""
        # Arrange
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"active\n", b""))
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            # Act
            status = await process_manager.get_service_status("test.service")

            # Assert
            assert status == ServiceStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_get_service_status_inactive(self, process_manager):
        """Test getting inactive service status."""
        # Arrange
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"inactive\n", b""))
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            # Act
            status = await process_manager.get_service_status("test.service")

            # Assert
            assert status == ServiceStatus.INACTIVE

    @pytest.mark.asyncio
    async def test_get_service_status_failed(self, process_manager):
        """Test getting failed service status."""
        # Arrange
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"failed\n", b""))
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            # Act
            status = await process_manager.get_service_status("test.service")

            # Assert
            assert status == ServiceStatus.FAILED

    @pytest.mark.asyncio
    async def test_get_service_status_unknown(self, process_manager):
        """Test getting unknown service status."""
        # Arrange
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"weird-status\n", b""))
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            # Act
            status = await process_manager.get_service_status("test.service")

            # Assert
            assert status == ServiceStatus.UNKNOWN

    @pytest.mark.asyncio
    async def test_get_service_status_exception(self, process_manager):
        """Test get_service_status returns UNKNOWN on exception."""
        # Arrange
        with patch('asyncio.create_subprocess_exec', side_effect=RuntimeError("Command failed")):
            # Act
            status = await process_manager.get_service_status("test.service")

            # Assert
            assert status == ServiceStatus.UNKNOWN

    @pytest.mark.asyncio
    async def test_stop_service_success(self, process_manager):
        """Test successful service stop."""
        # Arrange
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch.object(process_manager, 'wait_for_service_status', new_callable=AsyncMock):
                # Act
                await process_manager.stop_service("test.service")

                # Assert
                process_manager.wait_for_service_status.assert_called_once_with(
                    "test.service",
                    target_status=ServiceStatus.INACTIVE,
                    timeout=ProcessManager.STOP_TIMEOUT,
                )

    @pytest.mark.asyncio
    async def test_stop_service_command_failure(self, process_manager):
        """Test stop_service raises RuntimeError when systemctl fails."""
        # Arrange
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b"Unit not found\n"))
        mock_process.returncode = 1

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            # Act & Assert
            with pytest.raises(RuntimeError, match="SERVICE_STOP_FAILED"):
                await process_manager.stop_service("test.service")

    @pytest.mark.asyncio
    async def test_stop_service_timeout(self, process_manager):
        """Test stop_service raises TimeoutError when service doesn't stop."""
        # Arrange
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch.object(
                process_manager,
                'wait_for_service_status',
                side_effect=asyncio.TimeoutError("Timeout")
            ):
                # Act & Assert
                with pytest.raises(TimeoutError, match="SERVICE_STOP_TIMEOUT"):
                    await process_manager.stop_service("test.service")

    @pytest.mark.asyncio
    async def test_start_service_success(self, process_manager):
        """Test successful service start."""
        # Arrange
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch.object(process_manager, 'wait_for_service_status', new_callable=AsyncMock):
                # Act
                await process_manager.start_service("test.service")

                # Assert
                process_manager.wait_for_service_status.assert_called_once_with(
                    "test.service",
                    target_status=ServiceStatus.ACTIVE,
                    timeout=ProcessManager.START_TIMEOUT,
                )

    @pytest.mark.asyncio
    async def test_start_service_command_failure(self, process_manager):
        """Test start_service raises RuntimeError when systemctl fails."""
        # Arrange
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b"Service failed to start\n"))
        mock_process.returncode = 1

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            # Act & Assert
            with pytest.raises(RuntimeError, match="SERVICE_START_FAILED"):
                await process_manager.start_service("test.service")

    @pytest.mark.asyncio
    async def test_start_service_timeout(self, process_manager):
        """Test start_service raises TimeoutError when service doesn't start."""
        # Arrange
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch.object(
                process_manager,
                'wait_for_service_status',
                side_effect=asyncio.TimeoutError("Timeout")
            ):
                # Act & Assert
                with pytest.raises(TimeoutError, match="SERVICE_START_TIMEOUT"):
                    await process_manager.start_service("test.service")

    @pytest.mark.asyncio
    async def test_restart_service_success(self, process_manager):
        """Test successful service restart."""
        # Arrange
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            # Act
            await process_manager.restart_service("test.service")

            # Assert - no exception raised

    @pytest.mark.asyncio
    async def test_restart_service_failure(self, process_manager):
        """Test restart_service raises RuntimeError on failure."""
        # Arrange
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b"Restart failed\n"))
        mock_process.returncode = 1

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            # Act & Assert
            with pytest.raises(RuntimeError, match="Failed to restart"):
                await process_manager.restart_service("test.service")

    @pytest.mark.asyncio
    async def test_wait_for_service_status_immediate_match(self, process_manager):
        """Test wait_for_service_status returns immediately when status matches."""
        # Arrange
        with patch.object(
            process_manager,
            'get_service_status',
            return_value=ServiceStatus.ACTIVE
        ):
            # Act
            await process_manager.wait_for_service_status(
                "test.service",
                target_status=ServiceStatus.ACTIVE,
                timeout=5.0
            )

            # Assert - no exception raised

    @pytest.mark.asyncio
    async def test_wait_for_service_status_eventual_match(self, process_manager):
        """Test wait_for_service_status waits until status matches."""
        # Arrange - return ACTIVATING twice, then ACTIVE
        status_sequence = [
            ServiceStatus.ACTIVATING,
            ServiceStatus.ACTIVATING,
            ServiceStatus.ACTIVE,
        ]

        with patch.object(
            process_manager,
            'get_service_status',
            side_effect=status_sequence
        ):
            # Act
            await process_manager.wait_for_service_status(
                "test.service",
                target_status=ServiceStatus.ACTIVE,
                timeout=5.0,
                check_interval=0.01  # Fast checks for testing
            )

            # Assert - completed without timeout

    @pytest.mark.asyncio
    async def test_wait_for_service_status_timeout(self, process_manager):
        """Test wait_for_service_status raises TimeoutError."""
        # Arrange - always return wrong status
        with patch.object(
            process_manager,
            'get_service_status',
            return_value=ServiceStatus.ACTIVATING
        ):
            # Act & Assert
            with pytest.raises(asyncio.TimeoutError, match="did not reach"):
                await process_manager.wait_for_service_status(
                    "test.service",
                    target_status=ServiceStatus.ACTIVE,
                    timeout=0.1,  # Very short timeout
                    check_interval=0.01
                )

    @pytest.mark.asyncio
    async def test_stop_service_custom_timeout(self, process_manager):
        """Test stop_service with custom timeout."""
        # Arrange
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0

        custom_timeout = 20.0

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch.object(process_manager, 'wait_for_service_status', new_callable=AsyncMock):
                # Act
                await process_manager.stop_service("test.service", timeout=custom_timeout)

                # Assert
                process_manager.wait_for_service_status.assert_called_once_with(
                    "test.service",
                    target_status=ServiceStatus.INACTIVE,
                    timeout=custom_timeout,
                )

    @pytest.mark.asyncio
    async def test_start_service_custom_timeout(self, process_manager):
        """Test start_service with custom timeout."""
        # Arrange
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0

        custom_timeout = 60.0

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch.object(process_manager, 'wait_for_service_status', new_callable=AsyncMock):
                # Act
                await process_manager.start_service("test.service", timeout=custom_timeout)

                # Assert
                process_manager.wait_for_service_status.assert_called_once_with(
                    "test.service",
                    target_status=ServiceStatus.ACTIVE,
                    timeout=custom_timeout,
                )

    @pytest.mark.asyncio
    async def test_all_service_status_enum_values(self, process_manager):
        """Test all ServiceStatus enum values are correctly parsed."""
        # Arrange
        test_cases = [
            ("active", ServiceStatus.ACTIVE),
            ("reloading", ServiceStatus.RELOADING),
            ("inactive", ServiceStatus.INACTIVE),
            ("failed", ServiceStatus.FAILED),
            ("activating", ServiceStatus.ACTIVATING),
            ("deactivating", ServiceStatus.DEACTIVATING),
        ]

        for status_str, expected_enum in test_cases:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(status_str.encode() + b"\n", b""))
            mock_process.returncode = 0

            with patch('asyncio.create_subprocess_exec', return_value=mock_process):
                # Act
                status = await process_manager.get_service_status("test.service")

                # Assert
                assert status == expected_enum, f"Failed for status: {status_str}"

    @pytest.mark.asyncio
    async def test_stop_service_exception_propagation(self, process_manager):
        """Test stop_service propagates unexpected exceptions."""
        # Arrange
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch.object(
                process_manager,
                'wait_for_service_status',
                side_effect=RuntimeError("Unexpected error")
            ):
                # Act & Assert
                with pytest.raises(RuntimeError, match="Unexpected error"):
                    await process_manager.stop_service("test.service")

    @pytest.mark.asyncio
    async def test_start_service_exception_propagation(self, process_manager):
        """Test start_service propagates unexpected exceptions."""
        # Arrange
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch.object(
                process_manager,
                'wait_for_service_status',
                side_effect=RuntimeError("Unexpected error")
            ):
                # Act & Assert
                with pytest.raises(RuntimeError, match="Unexpected error"):
                    await process_manager.start_service("test.service")
