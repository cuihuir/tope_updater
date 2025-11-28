"""Deployment service for OTA package installation."""

import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional
import logging

from updater.models.manifest import Manifest
from updater.models.state import StateFile
from updater.models.status import StageEnum
from updater.services.state_manager import StateManager


class DeployService:
    """Handles manifest-driven package deployment with atomic operations."""

    def __init__(self, state_manager: Optional[StateManager] = None):
        """Initialize deployment service.

        Args:
            state_manager: StateManager instance (uses singleton if None)
        """
        self.logger = logging.getLogger("updater.deploy")
        self.state_manager = state_manager or StateManager()
        self.backup_dir = Path("./backups")

    async def deploy_package(self, package_path: Path, version: str) -> None:
        """Deploy OTA package following embedded manifest.

        Args:
            package_path: Path to verified ZIP package
            version: Version being installed

        Raises:
            FileNotFoundError: If package or manifest not found
            ValueError: If manifest parsing fails
            IOError: If file operations fail
        """
        self.logger.info(f"Starting deployment for version {version}")
        self.state_manager.update_status(
            stage=StageEnum.INSTALLING,
            progress=0,
            message=f"Installing version {version}...",
        )

        # Extract and parse manifest
        manifest = await self._extract_and_parse_manifest(package_path)
        self.logger.info(
            f"Manifest loaded: version={manifest.version}, "
            f"modules={len(manifest.modules)}"
        )

        # Validate version match
        if manifest.version != version:
            raise ValueError(
                f"Version mismatch: package claims {manifest.version}, "
                f"expected {version}"
            )

        # Deploy each module
        total_modules = len(manifest.modules)
        for idx, module in enumerate(manifest.modules, start=1):
            progress = int((idx / total_modules) * 100)
            self.logger.info(
                f"Deploying module {idx}/{total_modules}: {module.name}"
            )
            self.state_manager.update_status(
                stage=StageEnum.INSTALLING,
                progress=progress,
                message=f"Installing module {module.name}...",
            )

            await self._deploy_module(package_path, module, version)

        self.logger.info(f"Deployment complete for version {version}")
        self.state_manager.update_status(
            stage=StageEnum.SUCCESS,
            progress=100,
            message=f"Successfully installed version {version}",
        )

    async def _extract_and_parse_manifest(self, package_path: Path) -> Manifest:
        """Extract manifest.json from ZIP and parse it.

        Args:
            package_path: Path to ZIP package

        Returns:
            Parsed Manifest object

        Raises:
            FileNotFoundError: If manifest.json not found in ZIP
            ValueError: If manifest parsing fails
        """
        try:
            with zipfile.ZipFile(package_path, "r") as zf:
                # Check if manifest.json exists
                if "manifest.json" not in zf.namelist():
                    raise FileNotFoundError(
                        "manifest.json not found in package root"
                    )

                # Read and parse manifest
                manifest_data = zf.read("manifest.json").decode("utf-8")
                manifest_dict = json.loads(manifest_data)
                manifest = Manifest(**manifest_dict)

                self.logger.debug(f"Parsed manifest: {manifest.model_dump()}")
                return manifest

        except zipfile.BadZipFile as e:
            raise ValueError(f"Invalid ZIP package: {e}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid manifest JSON: {e}")

    async def _deploy_module(
        self, package_path: Path, module, version: str
    ) -> None:
        """Deploy a single module with atomic file operations.

        Args:
            package_path: Path to ZIP package
            module: ManifestModule to deploy
            version: Version being installed

        Raises:
            FileNotFoundError: If source file not found in ZIP
            IOError: If file operations fail
        """
        src_path = module.src
        dst_path = Path(module.dst)

        self.logger.debug(
            f"Deploying module {module.name}: {src_path} -> {dst_path}"
        )

        # Validate destination path
        if not dst_path.is_absolute():
            raise ValueError(
                f"Destination path must be absolute: {dst_path}"
            )

        # Create destination directory if needed
        dst_path.parent.mkdir(parents=True, exist_ok=True)

        # Backup existing file if it exists
        if dst_path.exists():
            await self._backup_file(dst_path, version)

        # Extract to temporary file first (atomic operation)
        tmp_path = dst_path.parent / f"{dst_path.name}.tmp"
        try:
            with zipfile.ZipFile(package_path, "r") as zf:
                if src_path not in zf.namelist():
                    raise FileNotFoundError(
                        f"Source file {src_path} not found in package"
                    )

                # Extract to temp file
                with zf.open(src_path) as src_file:
                    with open(tmp_path, "wb") as tmp_file:
                        shutil.copyfileobj(src_file, tmp_file)

            # Atomic rename to final destination
            tmp_path.rename(dst_path)
            self.logger.info(f"Deployed {module.name} to {dst_path}")

        except Exception as e:
            # Cleanup temp file on error
            tmp_path.unlink(missing_ok=True)
            self.logger.error(f"Failed to deploy {module.name}: {e}")
            raise

    async def _backup_file(self, file_path: Path, version: str) -> None:
        """Backup existing file before replacement.

        Args:
            file_path: File to backup
            version: Version being installed (for backup naming)
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.name}.{version}.{timestamp}.bak"
        backup_path = self.backup_dir / backup_name

        self.backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, backup_path)

        self.logger.info(f"Backed up {file_path.name} to {backup_path}")
