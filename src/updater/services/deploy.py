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
from updater.services.process import ProcessManager


class DeployService:
    """Handles manifest-driven package deployment with atomic operations."""

    def __init__(
        self,
        state_manager: Optional[StateManager] = None,
        process_manager: Optional[ProcessManager] = None,
    ):
        """Initialize deployment service.

        Args:
            state_manager: StateManager instance (uses singleton if None)
            process_manager: ProcessManager instance (creates new if None)
        """
        self.logger = logging.getLogger("updater.deploy")
        self.state_manager = state_manager or StateManager()
        self.process_manager = process_manager or ProcessManager()
        self.backup_dir = Path("./backups")

        # Track backup paths for rollback (T040)
        # Key: destination file path (str), Value: backup path (Path)
        self.backup_paths: dict[str, Path] = {}

    async def deploy_package(self, package_path: Path, version: str) -> None:
        """Deploy OTA package following embedded manifest.

        Args:
            package_path: Path to verified ZIP package
            version: Version being installed

        Raises:
            FileNotFoundError: If package or manifest not found
            ValueError: If manifest parsing fails
            IOError: If file operations fail
            RuntimeError: If deployment fails and rollback is attempted

        Implementation: T040, T041
        """
        # Clear previous backup tracking
        self.backup_paths.clear()

        self.logger.info(f"Starting deployment for version {version}")
        self.state_manager.update_status(
            stage=StageEnum.INSTALLING,
            progress=0,
            message=f"Installing version {version}...",
        )

        try:
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

            # Phase 1: Stop services (停服)
            # Collect all unique services that need to be stopped
            modules_with_services = [
                m for m in manifest.modules if m.process_name is not None
            ]
            if modules_with_services:
                self.logger.info(
                    f"Stopping {len(modules_with_services)} services before deployment"
                )
                self.state_manager.update_status(
                    stage=StageEnum.INSTALLING,
                    progress=5,
                    message="Stopping services...",
                )
                await self._stop_services(modules_with_services)

            # Phase 2: Deploy files (备份 + 替换)
            total_modules = len(manifest.modules)
            for idx, module in enumerate(manifest.modules, start=1):
                progress = int((idx / total_modules) * 80)  # 0-80% for file deployment
                self.logger.info(
                    f"Deploying module {idx}/{total_modules}: {module.name}"
                )
                self.state_manager.update_status(
                    stage=StageEnum.INSTALLING,
                    progress=progress,
                    message=f"Installing module {module.name}...",
                )

                await self._deploy_module(package_path, module, version)

            # Phase 3: Start services (启动服务)
            # Note: systemd will automatically handle dependency ordering
            if modules_with_services:
                self.logger.info(
                    f"Starting {len(modules_with_services)} services after deployment"
                )
                self.state_manager.update_status(
                    stage=StageEnum.INSTALLING,
                    progress=85,
                    message="Starting services...",
                )

                await self._start_services(modules_with_services)

            # Phase 4: Verify deployment (检查)
            self.state_manager.update_status(
                stage=StageEnum.INSTALLING,
                progress=95,
                message="Verifying deployment...",
            )
            await self._verify_deployment(manifest)

            # Phase 5: Report success (report成功)
            self.logger.info(f"Deployment complete for version {version}")
            self.state_manager.update_status(
                stage=StageEnum.SUCCESS,
                progress=100,
                message=f"Successfully installed version {version}",
            )

        except Exception as e:
            # Deployment failed - attempt rollback (T040, T041)
            self.logger.error(f"Deployment failed: {e}")
            self.logger.warning("Attempting rollback from backups...")

            try:
                await self._rollback_deployment()
            except Exception as rollback_error:
                self.logger.error(
                    f"Rollback also failed: {rollback_error}"
                )
                raise RuntimeError(
                    f"DEPLOYMENT_FAILED: {e}\n"
                    f"ROLLBACK_FAILED: {rollback_error}\n"
                    f"Manual intervention may be required!"
                ) from rollback_error

            # If rollback succeeded, still report original failure
            raise RuntimeError(
                f"DEPLOYMENT_FAILED: {e}\n"
                f"Rollback completed successfully."
            ) from e

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
            backup_path = await self._backup_file(dst_path, version)
            # Track backup for potential rollback (T040)
            self.backup_paths[str(dst_path)] = backup_path

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

    async def _stop_services(self, modules_with_services: list) -> None:
        """Stop all services before deployment.

        Args:
            modules_with_services: List of modules with process_name to stop

        Implementation: T047, T050
        """
        # Collect unique service names
        service_names = list(set(
            m.process_name for m in modules_with_services if m.process_name
        ))

        self.logger.info(f"Stopping {len(service_names)} unique services")

        for service_name in service_names:
            try:
                self.logger.info(f"Stopping service: {service_name}")
                await self.process_manager.stop_service(service_name)
                self.logger.info(f"✓ Stopped {service_name}")
            except Exception as e:
                # If stop fails, we cannot safely proceed
                # Raise error to abort deployment
                self.logger.error(f"Failed to stop {service_name}: {e}")
                raise RuntimeError(
                    f"SERVICE_STOP_FAILED: Cannot safely deploy while "
                    f"{service_name} is still running. Error: {e}"
                )

    async def _start_services(self, modules_with_services: list) -> None:
        """Start all services after deployment.

        Args:
            modules_with_services: List of modules with process_name to start

        Note:
            systemd will automatically handle dependency ordering via
            After= and Requires= directives in service unit files.
            We don't need to manually sort by restart_order anymore.

        Implementation: T049, T050
        """
        # Collect unique service names
        service_names = list(set(
            m.process_name for m in modules_with_services if m.process_name
        ))

        self.logger.info(f"Starting {len(service_names)} unique services")

        for service_name in service_names:
            try:
                self.logger.info(f"Starting service: {service_name}")
                await self.process_manager.start_service(service_name)
                self.logger.info(f"✓ Started {service_name}")
            except Exception as e:
                # Log error but don't fail deployment
                # Files are already deployed, service start failure is less critical
                self.logger.error(
                    f"Failed to start {service_name}: {e}"
                )
                self.logger.warning(
                    "Service start failed after deployment, "
                    "but files have been updated. "
                    "Manual intervention may be required."
                )

    async def _backup_file(self, file_path: Path, version: str) -> Path:
        """Backup existing file before replacement.

        Args:
            file_path: File to backup
            version: Version being installed (for backup naming)

        Returns:
            Path to the backup file

        Implementation: T038
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.name}.{version}.{timestamp}.bak"
        backup_path = self.backup_dir / backup_name

        self.backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, backup_path)

        self.logger.info(f"Backed up {file_path.name} to {backup_path}")
        return backup_path

    async def _verify_deployment(self, manifest: Manifest) -> None:
        """Verify all deployed files exist and are accessible.

        Args:
            manifest: Manifest with module deployment information

        Raises:
            FileNotFoundError: If deployed file doesn't exist
        """
        self.logger.info("Verifying deployment of all modules")

        for module in manifest.modules:
            dst_path = Path(module.dst)

            if not dst_path.exists():
                raise FileNotFoundError(
                    f"Deployment verification failed: {dst_path} does not exist"
                )

            # Check file is readable
            if not dst_path.is_file():
                raise ValueError(
                    f"Deployment verification failed: {dst_path} is not a file"
                )

            file_size = dst_path.stat().st_size
            self.logger.debug(
                f"✓ Verified {module.name}: {dst_path} ({file_size} bytes)"
            )

        self.logger.info(
            f"Deployment verification passed: all {len(manifest.modules)} modules deployed"
        )

    async def _rollback_deployment(self) -> None:
        """Rollback deployment by restoring files from backups.

        Iterates through all tracked backups and restores them to their
        original locations. This is called automatically when deployment fails.

        Raises:
            FileNotFoundError: If backup file is missing
            IOError: If restore operation fails

        Implementation: T040
        """
        if not self.backup_paths:
            self.logger.warning("No backups to restore")
            return

        self.logger.info(f"Rolling back {len(self.backup_paths)} files...")

        restore_errors = []

        for dst_path_str, backup_path in self.backup_paths.items():
            dst_path = Path(dst_path_str)

            try:
                if not backup_path.exists():
                    error_msg = f"Backup file not found: {backup_path}"
                    self.logger.error(error_msg)
                    restore_errors.append(error_msg)
                    continue

                # Restore from backup
                self.logger.info(f"Restoring {dst_path} from {backup_path}")
                shutil.copy2(backup_path, dst_path)
                self.logger.info(f"✓ Restored {dst_path}")

            except Exception as e:
                error_msg = f"Failed to restore {dst_path}: {e}"
                self.logger.error(error_msg)
                restore_errors.append(error_msg)

        # Clear backup tracking after rollback attempt
        self.backup_paths.clear()

        if restore_errors:
            raise RuntimeError(
                f"Rollback completed with {len(restore_errors)} errors:\n" +
                "\n".join(restore_errors)
            )

        self.logger.info("Rollback completed successfully")
