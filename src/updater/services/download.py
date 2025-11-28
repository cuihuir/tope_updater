"""Download service with resumable HTTP downloads."""

import asyncio
from pathlib import Path
from typing import Optional
import logging

import httpx
import aiofiles

from updater.models.state import StateFile
from updater.models.status import StageEnum
from updater.services.state_manager import StateManager
from updater.utils.verification import verify_md5_or_raise


class DownloadService:
    """Handles resumable package downloads with progress reporting."""

    def __init__(self, state_manager: Optional[StateManager] = None):
        """Initialize download service.

        Args:
            state_manager: StateManager instance (uses singleton if None)
        """
        self.logger = logging.getLogger("updater.download")
        self.state_manager = state_manager or StateManager()
        self.chunk_size = 64 * 1024  # 64KB chunks for progress granularity

    async def download_package(
        self,
        version: str,
        package_url: str,
        package_name: str,
        package_size: int,
        package_md5: str,
    ) -> Path:
        """Download package with resumable support and MD5 verification.

        Args:
            version: Version being downloaded
            package_url: HTTPS URL to download from
            package_name: Target filename
            package_size: Total expected bytes
            package_md5: Expected MD5 hash

        Returns:
            Path to downloaded and verified package file

        Raises:
            httpx.HTTPError: If download fails
            ValueError: If MD5 verification fails
        """
        target_path = Path("./tmp") / package_name
        self.logger.info(
            f"Starting download: version={version}, url={package_url}, "
            f"size={package_size} bytes"
        )

        # Check for existing partial download
        bytes_downloaded = 0
        if target_path.exists():
            bytes_downloaded = target_path.stat().st_size
            self.logger.info(f"Resuming download from byte {bytes_downloaded}")

        # Update state to downloading
        self.state_manager.update_status(
            stage=StageEnum.DOWNLOADING,
            progress=int((bytes_downloaded / package_size) * 100),
            message=f"Downloading version {version}...",
        )

        # Perform resumable download
        try:
            await self._download_with_resume(
                url=package_url,
                target_path=target_path,
                package_size=package_size,
                bytes_downloaded=bytes_downloaded,
                version=version,
                package_md5=package_md5,
            )
        except Exception as e:
            self.logger.error(f"Download failed: {e}", exc_info=True)
            self.state_manager.update_status(
                stage=StageEnum.FAILED,
                progress=0,
                message="Download failed",
                error=f"DOWNLOAD_FAILED: {str(e)}",
            )
            raise

        # Verify MD5
        self.logger.info(f"Download complete, verifying MD5...")
        self.state_manager.update_status(
            stage=StageEnum.VERIFYING,
            progress=0,
            message="Verifying package integrity...",
        )

        try:
            verify_md5_or_raise(target_path, package_md5)
        except ValueError as e:
            self.logger.error(f"MD5 verification failed: {e}")
            target_path.unlink(missing_ok=True)  # Delete corrupted file
            self.state_manager.update_status(
                stage=StageEnum.FAILED,
                progress=0,
                message="MD5 verification failed",
                error=str(e),
            )
            raise

        # MD5 verified successfully
        self.logger.info(f"MD5 verification passed")
        self.state_manager.update_status(
            stage=StageEnum.TO_INSTALL,
            progress=100,
            message=f"Package ready to install: {version}",
        )

        return target_path

    async def _download_with_resume(
        self,
        url: str,
        target_path: Path,
        package_size: int,
        bytes_downloaded: int,
        version: str,
        package_md5: str,
    ) -> None:
        """Perform resumable HTTP download using Range header.

        Args:
            url: Download URL
            target_path: Target file path
            package_size: Total expected bytes
            bytes_downloaded: Already downloaded bytes
            version: Version being downloaded
            package_md5: Expected MD5 hash
        """
        headers = {}
        if bytes_downloaded > 0:
            headers["Range"] = f"bytes={bytes_downloaded}-"

        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("GET", url, headers=headers) as response:
                response.raise_for_status()

                # Open file in append mode if resuming, write mode if starting fresh
                mode = "ab" if bytes_downloaded > 0 else "wb"
                async with aiofiles.open(target_path, mode) as f:
                    last_progress = -1
                    async for chunk in response.aiter_bytes(chunk_size=self.chunk_size):
                        await f.write(chunk)
                        bytes_downloaded += len(chunk)

                        # Update progress every 5%
                        current_progress = int((bytes_downloaded / package_size) * 100)
                        if current_progress >= last_progress + 5:
                            last_progress = current_progress
                            self.logger.debug(
                                f"Download progress: {current_progress}% "
                                f"({bytes_downloaded}/{package_size} bytes)"
                            )
                            self.state_manager.update_status(
                                stage=StageEnum.DOWNLOADING,
                                progress=current_progress,
                                message=f"Downloading version {version}...",
                            )

                            # Save persistent state for resume capability
                            state = StateFile(
                                version=version,
                                package_url=url,
                                package_name=target_path.name,
                                package_size=package_size,
                                package_md5=package_md5,
                                bytes_downloaded=bytes_downloaded,
                                stage=StageEnum.DOWNLOADING,
                            )
                            self.state_manager.save_state(state)

        self.logger.info(f"Downloaded {bytes_downloaded} bytes")
