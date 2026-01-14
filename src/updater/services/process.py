"""Process management for systemd service control."""

import asyncio
from typing import Optional, Literal
from enum import Enum
import logging


class ServiceStatus(Enum):
    """Systemd service status values from systemctl is-active."""
    ACTIVE = "active"
    RELOADING = "reloading"
    INACTIVE = "inactive"
    FAILED = "failed"
    ACTIVATING = "activating"
    DEACTIVATING = "deactivating"
    UNKNOWN = "unknown"


class ProcessManager:
    """Manages systemd service lifecycle with full systemd integration.

    Implements Phase 6 requirements (T047-T051):
    - systemctl stop with status verification
    - systemctl is-active status checks
    - Proper service dependency handling
    - SERVICE_STOP_FAILED error reporting
    """

    # Default timeout for service operations (seconds)
    STOP_TIMEOUT = 10
    START_TIMEOUT = 30
    STATUS_CHECK_INTERVAL = 0.5

    def __init__(self):
        """Initialize process manager."""
        self.logger = logging.getLogger("updater.process")

    async def stop_service(
        self,
        service_name: str,
        timeout: float = STOP_TIMEOUT,
    ) -> None:
        """Stop a systemd service with verification.

        Gracefully terminates the service using systemd, which will:
        1. Send SIGTERM to the service process
        2. Wait for configured TimeoutStopSec (default 90s)
        3. Send SIGKILL if service doesn't respond

        Args:
            service_name: Systemd service name (e.g., "device-api.service")
            timeout: Maximum seconds to wait for service to stop

        Raises:
            RuntimeError: If systemctl stop command fails
            TimeoutError: If service doesn't stop within timeout

        Implementation: T047
        """
        self.logger.info(f"Stopping service: {service_name}")

        command = ["systemctl", "stop", service_name]

        try:
            # Execute systemctl stop
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                self.logger.error(
                    f"systemctl stop failed for {service_name}: "
                    f"exit code {process.returncode}, error: {error_msg}"
                )
                raise RuntimeError(
                    f"SERVICE_STOP_FAILED: systemctl stop {service_name} "
                    f"failed with exit code {process.returncode}: {error_msg}"
                )

            # Wait for service to actually stop
            await self.wait_for_service_status(
                service_name,
                target_status=ServiceStatus.INACTIVE,
                timeout=timeout,
            )

            self.logger.info(f"Service {service_name} stopped successfully")

        except asyncio.TimeoutError:
            self.logger.error(
                f"Service {service_name} did not stop within {timeout}s"
            )
            raise TimeoutError(
                f"SERVICE_STOP_TIMEOUT: {service_name} did not stop "
                f"within {timeout}s (may be stuck)"
            )
        except Exception as e:
            self.logger.error(f"Failed to stop {service_name}: {e}")
            raise

    async def start_service(
        self,
        service_name: str,
        timeout: float = START_TIMEOUT,
    ) -> None:
        """Start a systemd service with verification.

        Args:
            service_name: Systemd service name (e.g., "device-api.service")
            timeout: Maximum seconds to wait for service to become active

        Raises:
            RuntimeError: If systemctl start command fails
            TimeoutError: If service doesn't start within timeout

        Implementation: T047
        """
        self.logger.info(f"Starting service: {service_name}")

        command = ["systemctl", "start", service_name]

        try:
            # Execute systemctl start
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                self.logger.error(
                    f"systemctl start failed for {service_name}: "
                    f"exit code {process.returncode}, error: {error_msg}"
                )
                raise RuntimeError(
                    f"SERVICE_START_FAILED: systemctl start {service_name} "
                    f"failed with exit code {process.returncode}: {error_msg}"
                )

            # Wait for service to become active
            await self.wait_for_service_status(
                service_name,
                target_status=ServiceStatus.ACTIVE,
                timeout=timeout,
            )

            self.logger.info(f"Service {service_name} started successfully")

        except asyncio.TimeoutError:
            self.logger.error(
                f"Service {service_name} did not start within {timeout}s"
            )
            raise TimeoutError(
                f"SERVICE_START_TIMEOUT: {service_name} did not start "
                f"within {timeout}s (check logs for errors)"
            )
        except Exception as e:
            self.logger.error(f"Failed to start {service_name}: {e}")
            raise

    async def restart_service(self, service_name: str) -> None:
        """Restart a systemd service (legacy method, now uses stop + start).

        Note: For deployment workflow, prefer explicit stop_service() + start_service()
        to allow file deployment between stop and start.

        Args:
            service_name: Systemd service name (e.g., "device-api")

        Raises:
            RuntimeError: If restart command fails
        """
        self.logger.warning(
            f"restart_service() called for {service_name} - "
            "consider using explicit stop/start for better control"
        )

        # Use systemctl restart (one-step operation)
        command = ["systemctl", "restart", service_name]

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise RuntimeError(
                    f"Failed to restart {service_name}: "
                    f"exit code {process.returncode}, "
                    f"stderr: {stderr.decode()}"
                )

            self.logger.info(f"Service {service_name} restarted successfully")

        except Exception as e:
            self.logger.error(f"Failed to restart {service_name}: {e}")
            raise

    async def get_service_status(self, service_name: str) -> ServiceStatus:
        """Get current status of a systemd service.

        Uses `systemctl is-active` to query service state.

        Args:
            service_name: Systemd service name (e.g., "device-api.service")

        Returns:
            ServiceStatus enum value

        Raises:
            RuntimeError: If systemctl command fails

        Implementation: T048
        """
        command = ["systemctl", "is-active", service_name]

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            status_str = stdout.decode().strip()

            # Map systemctl output to ServiceStatus enum
            try:
                return ServiceStatus(status_str)
            except ValueError:
                self.logger.warning(
                    f"Unknown service status '{status_str}' for {service_name}"
                )
                return ServiceStatus.UNKNOWN

        except Exception as e:
            self.logger.error(f"Failed to get status for {service_name}: {e}")
            return ServiceStatus.UNKNOWN

    async def wait_for_service_status(
        self,
        service_name: str,
        target_status: ServiceStatus,
        timeout: float,
        check_interval: float = STATUS_CHECK_INTERVAL,
    ) -> None:
        """Wait for service to reach target status.

        Polls systemctl is-active until service reaches target status.

        Args:
            service_name: Systemd service name
            target_status: Desired ServiceStatus (ACTIVE or INACTIVE)
            timeout: Maximum seconds to wait
            check_interval: Seconds between status checks

        Raises:
            TimeoutError: If service doesn't reach target status within timeout
            RuntimeError: If status check fails

        Implementation: T048
        """
        self.logger.debug(
            f"Waiting for {service_name} to reach {target_status.value} "
            f"(timeout={timeout}s)"
        )

        start_time = asyncio.get_event_loop().time()

        while True:
            current_status = await self.get_service_status(service_name)

            if current_status == target_status:
                self.logger.debug(
                    f"Service {service_name} reached {target_status.value}"
                )
                return

            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                raise asyncio.TimeoutError(
                    f"Service {service_name} did not reach {target_status.value} "
                    f"within {timeout}s (current: {current_status.value})"
                )

            # Wait before next check
            await asyncio.sleep(check_interval)
