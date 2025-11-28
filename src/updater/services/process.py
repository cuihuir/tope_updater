"""Process management for systemd service control."""

import asyncio
from typing import Optional
import logging


class ProcessManager:
    """Manages systemd service lifecycle (simplified for now, will be enhanced later)."""

    def __init__(self):
        """Initialize process manager."""
        self.logger = logging.getLogger("updater.process")

    async def restart_service(self, service_name: str) -> None:
        """Restart a systemd service.

        Args:
            service_name: Systemd service name (e.g., "device-api")

        Raises:
            RuntimeError: If restart command fails
        """
        self.logger.info(f"Restarting service: {service_name}")

        # TODO: Enhance this in future iterations with proper service dependency handling
        command = f"systemctl restart {service_name}"

        try:
            process = await asyncio.create_subprocess_shell(
                command,
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
