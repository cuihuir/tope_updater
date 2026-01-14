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

        # Check for existing partial download and validate it's the same package
        bytes_downloaded = 0
        if target_path.exists():
            # Check if this is a resume of the same download
            persistent_state = self.state_manager.get_persistent_state()
            if persistent_state:
                # Validate URL, version, and MD5 match
                if (persistent_state.package_url != package_url or
                    persistent_state.version != version or
                    persistent_state.package_md5 != package_md5):
                    self.logger.warning(
                        f"Existing file is from different package "
                        f"(URL/version/MD5 mismatch), deleting and starting fresh"
                    )
                    target_path.unlink()
                    self.state_manager.delete_state()
                else:
                    # Same package, safe to resume
                    bytes_downloaded = target_path.stat().st_size
                    self.logger.info(f"Resuming download from byte {bytes_downloaded}")
            else:
                # No state file but file exists - orphaned file, delete it
                self.logger.warning(
                    f"Found orphaned file without state.json, deleting and starting fresh"
                )
                target_path.unlink()

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
        except ValueError as e:
            # ValueError indicates validation errors (PACKAGE_SIZE_MISMATCH, etc.)
            # These are not resumable, delete state and file
            self.logger.error(f"Validation failed: {e}", exc_info=True)
            target_path.unlink(missing_ok=True)
            self.state_manager.delete_state()
            self.state_manager.update_status(
                stage=StageEnum.FAILED,
                progress=0,
                message="Download validation failed",
                error=str(e),
            )
            raise
        except Exception as e:
            # Network errors, etc. - keep state.json for resumable download
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

            # Update state to FAILED and save to state.json
            from datetime import datetime
            failed_state = StateFile(
                version=version,
                package_url=package_url,
                package_name=package_name,
                package_size=package_size,
                package_md5=package_md5,
                bytes_downloaded=0,  # Reset for potential retry
                last_update=datetime.now(),
                stage=StageEnum.FAILED,
                verified_at=None,
            )
            self.state_manager.save_state(failed_state)
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
            package_size: Total expected bytes (from cloud API)
            bytes_downloaded: Already downloaded bytes
            version: Version being downloaded
            package_md5: Expected MD5 hash

        Raises:
            ValueError: If download incomplete or size mismatch
            httpx.HTTPError: If HTTP request fails
        """
        # Initialize variables before try/catch to avoid UnboundLocalError
        # FIX for BUG-001: Initialize before async with block
        expected_from_server = None

        headers = {}
        if bytes_downloaded > 0:
            headers["Range"] = f"bytes={bytes_downloaded}-"

        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("GET", url, headers=headers) as response:
                response.raise_for_status()

                # Get Content-Length from server (if available)
                content_length_header = response.headers.get("Content-Length")
                if content_length_header:
                    expected_from_server = int(content_length_header)
                    # For Range requests, Content-Length is the remaining bytes
                    if bytes_downloaded > 0:
                        expected_from_server += bytes_downloaded

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

        # HTTP transfer completed, now validate
        self.logger.info(
            f"HTTP transfer completed: {bytes_downloaded} bytes downloaded"
        )

        # Validation 1: Check against HTTP Content-Length (if server provided it)
        if expected_from_server is not None:
            if bytes_downloaded != expected_from_server:
                self.logger.error(
                    f"Incomplete download: HTTP Content-Length={expected_from_server}, "
                    f"but only received {bytes_downloaded} bytes"
                )
                raise ValueError(
                    f"INCOMPLETE_DOWNLOAD: expected {expected_from_server} bytes "
                    f"from server, but only received {bytes_downloaded} bytes"
                )

        # Validation 2: Check against business-declared package_size
        if bytes_downloaded != package_size:
            self.logger.error(
                f"Package size mismatch: declared {package_size} bytes, "
                f"but downloaded {bytes_downloaded} bytes"
            )
            raise ValueError(
                f"PACKAGE_SIZE_MISMATCH: expected {package_size} bytes, "
                f"but downloaded {bytes_downloaded} bytes"
            )

        self.logger.info(f"Download size validation passed: {bytes_downloaded} bytes")
