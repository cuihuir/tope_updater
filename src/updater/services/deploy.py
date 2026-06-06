"""Deployment service for OTA package installation with version snapshot support.

This module handles manifest-driven package deployment using version snapshots.
Files are deployed to version-specific directories (e.g., v1.0.0/, v1.1.0/),
and symlinks (current, previous, factory) are atomically updated for rollback support.

Deployment workflow:
1. Create new version directory (versions/v{version}/)
2. Extract files to version directory
3. Stop services
4. Deploy files to version directory
5. Start services
6. Verify deployment
7. Atomically update symlinks (current -> new, previous -> old)
8. Report success

Rollback workflow:
- Level 1: Rollback to previous version
- Level 2: Rollback to factory version (if previous fails)
"""

import asyncio
import json
import os
import shutil
import zipfile
from pathlib import Path
from typing import Optional
import logging

from updater.models.manifest import Manifest
from updater.models.status import StageEnum
from updater.services.state_manager import StateManager
from updater.services.process import ProcessManager, ServiceStatus
from updater.services.reporter import ReportService
from updater.services.version_manager import VersionManager
from updater.utils.version import normalize_version


class DeployService:
    """Handles manifest-driven package deployment with version snapshots."""

    def __init__(
        self,
        state_manager: Optional[StateManager] = None,
        process_manager: Optional[ProcessManager] = None,
        reporter: Optional[ReportService] = None,
        version_manager: Optional[VersionManager] = None,
    ):
        """Initialize deployment service.

        Args:
            state_manager: StateManager instance (uses singleton if None)
            process_manager: ProcessManager instance (creates new if None)
            reporter: ReportService instance for device-api callbacks (optional)
            version_manager: VersionManager instance (creates new if None)
        """
        self.logger = logging.getLogger("updater.deploy")
        self.state_manager = state_manager or StateManager()
        self.process_manager = process_manager or ProcessManager()
        self.reporter = reporter
        self.version_manager = version_manager or VersionManager()
        self.services_dir = Path("/opt/tope/services")
        self.legacy_printer_gui_dirs = (
            Path("/home/tope/printer-gui-qml"),
            Path("/home/tope/printer-gui"),
        )
        self.systemd_dir = Path("/etc/systemd/system")
        self.local_bin_dir = Path("/usr/local/bin")

    async def deploy_package(self, package_path: Path, version: str) -> None:
        """Deploy OTA package to version snapshot directory.

        Deployment workflow with version snapshots:
        1. Create version directory (versions/v{version}/)
        2. Extract and parse manifest
        3. Stop services
        4. Deploy files to version directory
        5. Start services
        6. Verify deployment
        7. Promote version (update symlinks atomically)

        Args:
            package_path: Path to verified ZIP package
            version: Version being installed (e.g., "1.0.0")

        Raises:
            FileNotFoundError: If package or manifest not found
            ValueError: If manifest parsing fails
            IOError: If file operations fail
            RuntimeError: If deployment fails

        Implementation: Phase 2 - Version Snapshot Architecture
        """
        self.logger.info(f"Starting deployment for version {version}")
        self.state_manager.update_status(
            stage=StageEnum.INSTALLING,
            progress=0,
            message=f"Installing version {version}...",
        )

        # Report to device-api
        if self.reporter:
            await self.reporter.report_progress(
                stage=StageEnum.INSTALLING,
                progress=0,
                message=f"Installing version {version}...",
                version=version,
            )

        # Track version directory for cleanup on failure
        version_dir = None
        manifest = None
        promoted = False
        external_backups: dict[Path, Optional[Path]] = {}

        try:
            # Step 1: Create version snapshot directory
            self.logger.info(f"Creating version directory for {version}")
            version_dir = self.version_manager.create_version_dir(version)
            self.logger.info(f"Created version directory: {version_dir}")

            # Step 2: Extract and parse manifest
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

            incremental_metadata = await self._read_incremental_metadata(package_path)
            if incremental_metadata:
                self.logger.info(
                    "Incremental package detected: "
                    f"base_ref={incremental_metadata.get('base_ref')}, "
                    f"head_ref={incremental_metadata.get('head_ref')}"
                )
                self._validate_incremental_base(incremental_metadata)
                self.version_manager.seed_version_from_current(version_dir)
                self._apply_incremental_deletes(
                    incremental_metadata, version_dir, external_backups
                )

            # Step 3: Stop services before deployment
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

                # Report to device-api
                if self.reporter:
                    await self.reporter.report_progress(
                        stage=StageEnum.INSTALLING,
                        progress=5,
                        message="Stopping services...",
                        version=version,
                    )

                await self._stop_services(modules_with_services)

            # Step 4: Deploy files to version directory
            total_modules = len(manifest.modules)
            for idx, module in enumerate(manifest.modules, start=1):
                progress = int((idx / total_modules) * 80)  # 5-85% for file deployment
                self.logger.info(
                    f"Deploying module {idx}/{total_modules}: {module.name}"
                )
                self.state_manager.update_status(
                    stage=StageEnum.INSTALLING,
                    progress=progress,
                    message=f"Installing module {module.name}...",
                )

                # Report to device-api (every 10% or every module if < 10 modules)
                if self.reporter and (progress % 10 == 0 or total_modules < 10):
                    await self.reporter.report_progress(
                        stage=StageEnum.INSTALLING,
                        progress=progress,
                        message=f"Installing module {module.name} ({idx}/{total_modules})...",
                        version=version,
                    )

                # Deploy to version directory (not to final destination)
                await self._deploy_module_to_version(
                    package_path, module, version_dir, external_backups
                )

                # Run post-deployment commands (e.g. daemon-reload, sysctl -p)
                await self._run_post_cmds(module)

            # Step 5: Verify deployment
            self.state_manager.update_status(
                stage=StageEnum.INSTALLING,
                progress=95,
                message="Verifying deployment...",
            )

            # Report to device-api
            if self.reporter:
                await self.reporter.report_progress(
                    stage=StageEnum.INSTALLING,
                    progress=95,
                    message="Verifying deployment...",
                    version=version,
                )

            await self._verify_deployment(manifest, version_dir)

            # Step 7: Promote version (atomically update symlinks)
            self.logger.info(f"Promoting version {version} to current")
            self.version_manager.promote_version(version)
            promoted = True
            self.logger.info(f"✓ Version {version} is now current")
            await self._normalize_runtime_environment(manifest)

            # Step 8: Start services after current points at the new version
            if modules_with_services:
                self.logger.info(
                    f"Starting {len(modules_with_services)} services after deployment"
                )
                self.state_manager.update_status(
                    stage=StageEnum.INSTALLING,
                    progress=98,
                    message="Starting services...",
                )

                # Report to device-api
                if self.reporter:
                    await self.reporter.report_progress(
                        stage=StageEnum.INSTALLING,
                        progress=98,
                        message="Starting services...",
                        version=version,
                    )

                await self._start_services(modules_with_services)

            try:
                deleted_versions = self.version_manager.prune_old_versions()
                if deleted_versions:
                    self.logger.info(f"Pruned old versions: {deleted_versions}")
            except Exception as prune_error:
                self.logger.warning(f"Failed to prune old versions: {prune_error}")

            # Step 9: Report success
            self.logger.info(f"Deployment complete for version {version}")
            self.state_manager.update_status(
                stage=StageEnum.SUCCESS,
                progress=100,
                message=f"Successfully installed version {version}",
            )

            # Report to device-api
            if self.reporter:
                await self._report_terminal_progress(
                    stage=StageEnum.SUCCESS,
                    progress=100,
                    message=f"Successfully installed version {version}",
                    version=version,
                )
            self._discard_external_backups(external_backups)

        except Exception as e:
            # Deployment failed - perform two-level rollback
            self.logger.error(f"Deployment failed: {e}")
            self._restore_external_backups(external_backups)

            # Cleanup version directory on failure. If the version was already
            # promoted, rollback first so current never points at a removed tree.
            if version_dir and version_dir.exists() and not promoted:
                self.logger.warning(f"Cleaning up failed version directory: {version_dir}")
                try:
                    shutil.rmtree(version_dir)
                    self.logger.info(f"✓ Cleaned up {version_dir}")
                except Exception as cleanup_error:
                    self.logger.error(f"Failed to cleanup version directory: {cleanup_error}")

            # Report deployment failure to device-api
            if self.reporter:
                await self.reporter.report_progress(
                    stage=StageEnum.FAILED,
                    progress=0,
                    message="Deployment failed, initiating rollback...",
                    error=f"DEPLOYMENT_FAILED: {str(e)}",
                    version=version,
                )

            # Perform two-level rollback: previous → factory
            # Only if manifest was parsed (otherwise we don't know which services to manage)
            if manifest is not None:
                try:
                    await self.perform_two_level_rollback(manifest, e)
                    if version_dir and version_dir.exists() and promoted:
                        self.logger.warning(
                            f"Cleaning up rolled-back version directory: {version_dir}"
                        )
                        shutil.rmtree(version_dir)
                except Exception as rollback_error:
                    # Both rollback levels failed
                    self.logger.error(f"Two-level rollback failed: {rollback_error}")
                    raise rollback_error
            else:
                self.logger.warning("Manifest not available, skipping rollback")

            # Rollback succeeded but still report original failure
            raise RuntimeError(f"DEPLOYMENT_FAILED: {e}\nRollback completed.") from e

    async def _extract_and_parse_manifest(self, package_path: Path) -> Manifest:
        """Extract manifest.json from ZIP and parse it.

        Args:
            package_path: Path to ZIP package

        Returns:
            Parsed Manifest object

        Raises:
            FileNotFoundError: If manifest.json not found in package
            ValueError: If manifest parsing fails
        """
        self.logger.debug(f"Extracting manifest from {package_path}")

        try:
            with zipfile.ZipFile(package_path, "r") as zf:
                if "manifest.json" not in zf.namelist():
                    raise FileNotFoundError(
                        "manifest.json not found in package"
                    )

                # Extract manifest content
                with zf.open("manifest.json") as manifest_file:
                    manifest_content = manifest_file.read().decode("utf-8")
                    manifest_data = json.loads(manifest_content)

                self.logger.debug(f"Manifest JSON: {manifest_data}")
                return Manifest(**manifest_data)

        except zipfile.BadZipFile as e:
            raise ValueError(f"Invalid ZIP package: {e}") from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid manifest.json: {e}") from e

    async def _read_incremental_metadata(
        self, package_path: Path
    ) -> Optional[dict]:
        """Read incremental package metadata if present."""
        try:
            with zipfile.ZipFile(package_path, "r") as zf:
                if "incremental.json" not in zf.namelist():
                    return None

                with zf.open("incremental.json") as metadata_file:
                    metadata = json.loads(metadata_file.read().decode("utf-8"))

            if metadata.get("type") != "incremental":
                raise ValueError("incremental.json type must be 'incremental'")
            return metadata

        except zipfile.BadZipFile as e:
            raise ValueError(f"Invalid ZIP package: {e}") from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid incremental.json: {e}") from e

    def _validate_incremental_base(self, metadata: dict) -> None:
        """Ensure an incremental package is applied to its declared base."""
        base_ref = metadata.get("base_ref")
        if not base_ref:
            raise RuntimeError("INCREMENTAL_BASE_MISSING: incremental.json has no base_ref")

        try:
            base_version = normalize_version(str(base_ref).removeprefix("refs/tags/"))
        except ValueError as e:
            raise RuntimeError(
                f"INCREMENTAL_BASE_INVALID: unsupported base_ref {base_ref!r}"
            ) from e

        current_version = self.version_manager.get_current_version()
        if current_version != base_version:
            raise RuntimeError(
                "INCREMENTAL_BASE_MISMATCH: "
                f"package base is {base_version}, current is {current_version}"
            )

    def _apply_incremental_deletes(
        self,
        metadata: dict,
        version_dir: Path,
        external_backups: dict[Path, Optional[Path]],
    ) -> None:
        """Apply deleted paths after seeding an incremental version snapshot."""
        for deleted in metadata.get("deleted", []):
            dst_path_absolute = Path(deleted)
            dst_in_version = self._get_relative_destination(dst_path_absolute)
            version_path = version_dir / dst_in_version

            if version_path.exists() or version_path.is_symlink():
                if version_path.is_dir() and not version_path.is_symlink():
                    shutil.rmtree(version_path)
                else:
                    version_path.unlink()
                self.logger.info(f"✓ Applied incremental delete: {version_path}")

            if not str(dst_path_absolute).startswith("/opt/tope"):
                if external_backups is not None:
                    self._backup_external_destination(
                        dst_path_absolute, external_backups
                    )
                if dst_path_absolute.exists() or dst_path_absolute.is_symlink():
                    if dst_path_absolute.is_dir() and not dst_path_absolute.is_symlink():
                        shutil.rmtree(dst_path_absolute)
                    else:
                        dst_path_absolute.unlink()

    async def _deploy_module_to_version(
        self,
        package_path: Path,
        module,
        version_dir: Path,
        external_backups: Optional[dict[Path, Optional[Path]]] = None,
    ) -> None:
        """Deploy a single module to version snapshot directory.

        This extracts files from the ZIP package to the version directory.
        The destination path is relative to the version directory.

        Example:
            If module.dst = /opt/tope/services/device-api
            And version_dir = /opt/tope/versions/v1.0.0
            Then file is deployed to /opt/tope/versions/v1.0.0/device-api

        Args:
            package_path: Path to ZIP package
            module: ManifestModule to deploy
            version_dir: Version snapshot directory

        Raises:
            FileNotFoundError: If source file not found in ZIP
            IOError: If file operations fail
        """
        src_path = module.src
        dst_path_absolute = Path(module.dst)

        self.logger.debug(
            f"Deploying module {module.name}: {src_path} -> {version_dir}"
        )

        # Calculate destination path in version directory
        # If module.dst = /opt/tope/services/device-api
        # Then in version dir: services/device-api
        # We strip the /opt/tope/ prefix
        dst_in_version = self._get_relative_destination(dst_path_absolute)
        final_dst = version_dir / dst_in_version

        self.logger.debug(
            f"Final destination in version dir: {final_dst}"
        )

        # Create destination directory if needed
        final_dst.parent.mkdir(parents=True, exist_ok=True)

        # Extract file from ZIP
        try:
            with zipfile.ZipFile(package_path, "r") as zf:
                if src_path not in zf.namelist():
                    raise FileNotFoundError(
                        f"Source file {src_path} not found in package"
                    )

                # Extract to temporary file first (atomic operation)
                tmp_path = final_dst.parent / f"{final_dst.name}.tmp"
                try:
                    zip_info = zf.getinfo(src_path)
                    # Extract Unix permission bits from ZIP external_attr (high 16 bits)
                    unix_mode = (zip_info.external_attr >> 16) & 0xFFFF

                    with zf.open(src_path) as src_file:
                        with open(tmp_path, "wb") as tmp_file:
                            shutil.copyfileobj(src_file, tmp_file)

                    # Apply original permissions if available
                    if unix_mode:
                        tmp_path.chmod(unix_mode)

                    # Atomic rename to final destination
                    tmp_path.rename(final_dst)
                    self.logger.info(f"✓ Deployed {module.name} to {final_dst}")

                    # If dst is not under /opt/tope/, also copy to actual absolute path
                    # shutil.copy preserves permission bits
                    if not str(dst_path_absolute).startswith("/opt/tope"):
                        dst_path_absolute.parent.mkdir(parents=True, exist_ok=True)
                        if external_backups is not None:
                            self._backup_external_destination(
                                dst_path_absolute, external_backups
                            )
                        actual_tmp = (
                            dst_path_absolute.parent
                            / f".{dst_path_absolute.name}.tmp.{os.getpid()}"
                        )
                        try:
                            shutil.copy2(final_dst, actual_tmp)
                            actual_tmp.replace(dst_path_absolute)
                        except Exception:
                            actual_tmp.unlink(missing_ok=True)
                            raise
                        self.logger.info(f"✓ Synced {module.name} to actual dst: {dst_path_absolute}")

                except Exception as e:
                    # Cleanup temp file on error
                    tmp_path.unlink(missing_ok=True)
                    self.logger.error(f"Failed to deploy {module.name}: {e}")
                    raise

        except Exception as e:
            self.logger.error(f"Failed to deploy {module.name}: {e}")
            raise

    def _backup_external_destination(
        self,
        dst_path: Path,
        external_backups: dict[Path, Optional[Path]],
    ) -> None:
        """Record the pre-update state for a non-versioned destination."""
        if dst_path in external_backups:
            return

        if not dst_path.exists():
            external_backups[dst_path] = None
            return

        backup_path = (
            dst_path.parent
            / f".{dst_path.name}.ota-backup.{os.getpid()}.{len(external_backups)}"
        )
        shutil.copy2(dst_path, backup_path)
        external_backups[dst_path] = backup_path
        self.logger.info(f"Backed up external destination: {dst_path}")

    def _restore_external_backups(
        self,
        external_backups: dict[Path, Optional[Path]],
    ) -> None:
        """Best-effort restore for external files changed before a failed deploy."""
        for dst_path, backup_path in reversed(list(external_backups.items())):
            try:
                if backup_path is None:
                    dst_path.unlink(missing_ok=True)
                    self.logger.info(f"Removed new external destination: {dst_path}")
                    continue

                restore_tmp = (
                    dst_path.parent
                    / f".{dst_path.name}.restore.{os.getpid()}"
                )
                try:
                    shutil.copy2(backup_path, restore_tmp)
                    restore_tmp.replace(dst_path)
                finally:
                    restore_tmp.unlink(missing_ok=True)
                    backup_path.unlink(missing_ok=True)
                self.logger.info(f"Restored external destination: {dst_path}")
            except Exception as restore_error:
                self.logger.error(
                    f"Failed to restore external destination {dst_path}: {restore_error}"
                )
        external_backups.clear()

    def _discard_external_backups(
        self,
        external_backups: dict[Path, Optional[Path]],
    ) -> None:
        """Remove external backups after a successful deployment."""
        for backup_path in external_backups.values():
            if backup_path is not None:
                backup_path.unlink(missing_ok=True)
        external_backups.clear()

    async def _run_post_cmds(self, module) -> None:
        """Run post-deployment shell commands for a module.

        Commands are executed in order. If any command exits with a non-zero
        code or times out, a RuntimeError is raised and deployment fails.

        Args:
            module: ManifestModule whose post_cmds to run

        Raises:
            RuntimeError: If a command fails or times out (30s per command)
        """
        if not module.post_cmds:
            return

        for cmd in module.post_cmds:
            self.logger.info(f"Running post_cmd [{module.name}]: {cmd}")
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=30.0
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                raise RuntimeError(
                    f"POST_CMD_TIMEOUT: '{cmd}' timed out after 30s"
                )

            if proc.returncode != 0:
                err = stderr.decode().strip()
                out = stdout.decode().strip()
                raise RuntimeError(
                    f"POST_CMD_FAILED: '{cmd}' exited {proc.returncode}"
                    + (f" — {err}" if err else "")
                    + (f" | stdout: {out}" if out else "")
                )

            self.logger.info(f"✓ post_cmd OK [{module.name}]: {cmd}")

    def _get_relative_destination(self, absolute_dst: Path) -> Path:
        """Convert absolute destination to relative path in version directory.

        Example:
            Input:  /opt/tope/services/device-api
            Output: services/device-api

            Input:  /opt/tope/bin/cli
            Output: bin/cli

        Args:
            absolute_dst: Absolute destination path from manifest

        Returns:
            Relative path for version directory

        Raises:
            ValueError: If path doesn't start with /opt/tope/
        """
        path_str = str(absolute_dst)

        # Remove /opt/tope/ prefix
        if path_str.startswith("/opt/tope/"):
            return Path(path_str[len("/opt/tope/"):])
        elif path_str.startswith("/opt/tope"):
            return Path(path_str[len("/opt/tope"):])
        else:
            # If path doesn't start with /opt/tope/, use as-is
            # This allows flexibility for different deployment targets
            self.logger.warning(
                f"Destination path doesn't start with /opt/tope/: {absolute_dst}"
            )
            return Path(absolute_dst.as_posix().lstrip("/"))

    async def _stop_services(self, modules_with_services: list) -> None:
        """Stop all services before deployment.

        Args:
            modules_with_services: List of modules with process_name to stop

        Note:
            Services are stopped before deployment to ensure files can be updated.
            systemd will handle dependency ordering automatically.
        """
        service_names = self._ordered_unique_service_names(modules_with_services)

        self.logger.info(f"Stopping {len(service_names)} unique services")

        for service_name in service_names:
            try:
                self.logger.info(f"Stopping service: {service_name}")
                await self.process_manager.stop_service(service_name)
                self.logger.info(f"✓ Stopped {service_name}")
            except Exception as e:
                # If stop fails, we cannot safely proceed
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
        """
        service_names = self._ordered_unique_service_names(modules_with_services)

        self.logger.info(f"Starting {len(service_names)} unique services")

        for service_name in service_names:
            try:
                self.logger.info(f"Starting service: {service_name}")
                await self.process_manager.start_service(service_name)

                # systemd can report active briefly before a crash-looping
                # service exits. Require a short stable window before success.
                await self.process_manager.wait_for_service_stable(
                    service_name,
                    stable_for=5,
                    timeout=30,
                )
                self.logger.info(f"✓ Started {service_name}")

            except Exception as e:
                self.logger.error(f"Failed to start {service_name}: {e}")
                raise RuntimeError(
                    f"SERVICE_START_FAILED: Cannot complete deployment because "
                    f"{service_name} failed to start. Error: {e}"
                ) from e

    async def _normalize_runtime_environment(self, manifest: Manifest) -> None:
        """Prepare stable service entrypoints after current has been promoted."""
        linked = self.version_manager.sync_service_links(self.services_dir)
        if linked:
            self.logger.info(f"Synced service entrypoints: {linked}")

        assets_installed = False
        assets_installed = self._migrate_printer_gui_runtime() or assets_installed
        assets_installed = self._install_printer_gui_deploy_assets() or assets_installed

        if assets_installed:
            await self._reload_systemd()

    def _migrate_printer_gui_runtime(self) -> bool:
        """Copy legacy printer GUI venv into the stable OTA entrypoint if needed."""
        target_venv = self.services_dir / "printer-gui" / ".venv"
        if target_venv.exists():
            return False

        target_parent = target_venv.parent
        if not target_parent.exists():
            return False

        for legacy_dir in self.legacy_printer_gui_dirs:
            legacy_venv = legacy_dir / ".venv"
            legacy_python = legacy_venv / "bin" / "python"
            if not legacy_python.exists():
                continue

            self.logger.info(f"Migrating printer GUI runtime: {legacy_venv} -> {target_venv}")
            shutil.copytree(legacy_venv, target_venv, symlinks=True)
            return True

        self.logger.warning(
            f"Printer GUI runtime missing and no legacy runtime found: {target_venv}"
        )
        return False

    def _install_printer_gui_deploy_assets(self) -> bool:
        """Install printer GUI systemd unit and EGLFS start script when packaged."""
        printer_gui_dir = self.services_dir / "printer-gui"
        deploy_dir = printer_gui_dir / "deploy"
        installed = False

        service_src = deploy_dir / "printer-gui-eglfs.service"
        if service_src.exists():
            self.systemd_dir.mkdir(parents=True, exist_ok=True)
            service_dst = self.systemd_dir / "printer-gui-eglfs.service"
            shutil.copy2(service_src, service_dst)
            self.logger.info(f"Installed systemd unit: {service_dst}")
            installed = True

        start_src = deploy_dir / "printer-gui-eglfs-start.sh"
        if start_src.exists():
            self.local_bin_dir.mkdir(parents=True, exist_ok=True)
            start_dst = self.local_bin_dir / "printer-gui-eglfs-start.sh"
            shutil.copy2(start_src, start_dst)
            start_dst.chmod(start_dst.stat().st_mode | 0o755)
            self.logger.info(f"Installed start script: {start_dst}")
            installed = True

        return installed

    async def _reload_systemd(self) -> None:
        """Reload systemd after managed unit files change."""
        proc = await asyncio.create_subprocess_exec(
            "systemctl",
            "daemon-reload",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
        if proc.returncode != 0:
            err = stderr.decode().strip()
            out = stdout.decode().strip()
            raise RuntimeError(
                "SYSTEMD_DAEMON_RELOAD_FAILED"
                + (f": {err}" if err else "")
                + (f" | stdout: {out}" if out else "")
            )

    async def _report_terminal_progress(
        self,
        stage: StageEnum,
        progress: int,
        message: str,
        error: Optional[str] = None,
        version: Optional[str] = None,
        attempts: int = 12,
        delay_seconds: float = 5.0,
    ) -> None:
        """Report a terminal OTA state until device-api accepts it once."""
        if not self.reporter:
            return

        for attempt in range(1, attempts + 1):
            reported = await self.reporter.report_progress(
                stage=stage,
                progress=progress,
                message=message,
                error=error,
                version=version,
            )
            if reported is None or reported:
                return

            if attempt < attempts:
                self.logger.warning(
                    "Terminal OTA report was not accepted by device-api; "
                    f"retrying ({attempt}/{attempts})"
                )
                await asyncio.sleep(delay_seconds)

        self.logger.error(
            "Terminal OTA report was not accepted by device-api after "
            f"{attempts} attempts: stage={stage.value}, version={version}, error={error}"
        )

    def _ordered_unique_service_names(self, modules_with_services: list) -> list[str]:
        """Return unique service names ordered by restart_order and declaration order."""
        service_order: dict[str, tuple[int, int]] = {}

        for index, module in enumerate(modules_with_services):
            service_name = getattr(module, "process_name", None)
            if not service_name:
                continue
            restart_order = getattr(module, "restart_order", None)
            order = restart_order if isinstance(restart_order, int) else 1000
            existing = service_order.get(service_name)
            if existing is None or (order, index) < existing:
                service_order[service_name] = (order, index)

        return [
            service_name
            for service_name, _ in sorted(
                service_order.items(), key=lambda item: item[1]
            )
        ]

    async def _verify_deployment(
        self,
        manifest: Manifest,
        version_dir: Path
    ) -> None:
        """Verify that all files were deployed to version directory.

        Args:
            manifest: Manifest with module deployment information
            version_dir: Version snapshot directory to verify

        Raises:
            FileNotFoundError: If deployed file doesn't exist
        """
        self.logger.info("Verifying deployment in version directory")

        for module in manifest.modules:
            # Calculate expected path in version directory
            dst_absolute = Path(module.dst)
            dst_in_version = self._get_relative_destination(dst_absolute)
            deployed_path = version_dir / dst_in_version

            if not deployed_path.exists():
                raise FileNotFoundError(
                    f"Deployment verification failed: {deployed_path} does not exist"
                )

            # Check file is readable
            if not deployed_path.is_file():
                raise ValueError(
                    f"Deployment verification failed: {deployed_path} is not a file"
                )

            file_size = deployed_path.stat().st_size
            self.logger.debug(
                f"✓ Verified {module.name}: {deployed_path} ({file_size} bytes)"
            )

        self.logger.info(
            f"Deployment verification passed: all {len(manifest.modules)} modules deployed"
        )

    async def rollback_to_previous(self, manifest: Manifest) -> str:
        """Rollback to previous version (Level 1 rollback).

        This is called when deployment fails or when the new version is unhealthy.

        Args:
            manifest: Manifest with service information for health check

        Returns:
            Version string that was rolled back to

        Raises:
            RuntimeError: If no previous version available or rollback fails
        """
        self.logger.info("Starting Level 1 rollback: rolling back to previous version")

        # Report rollback start to device-api
        if self.reporter:
            await self.reporter.report_progress(
                stage=StageEnum.FAILED,
                progress=0,
                message="Rolling back to previous version...",
                error="ROLLBACK_LEVEL_1",
                version=manifest.version,
            )

        try:
            # Stop services before rollback
            modules_with_services = [
                m for m in manifest.modules if m.process_name is not None
            ]
            if modules_with_services:
                self.logger.info("Stopping services before rollback")
                await self._stop_services(modules_with_services)

            # Perform rollback using VersionManager
            previous_version = self.version_manager.rollback_to_previous()
            self.logger.info(f"✓ Rolled back to version {previous_version}")

            # Restart services
            if modules_with_services:
                self.logger.info("Restarting services after rollback")
                await self._start_services(modules_with_services)

            # Verify services are healthy
            self.logger.info("Verifying service health after rollback")
            is_healthy = await self.verify_services_healthy(manifest)

            if not is_healthy:
                self.logger.error("Previous version is unhealthy after rollback")
                raise RuntimeError(
                    f"Previous version {previous_version} is unhealthy"
                )

            self.logger.info(f"✓ Rollback to {previous_version} completed successfully")

            # Report rollback success to device-api
            if self.reporter:
                await self._report_terminal_progress(
                    stage=StageEnum.FAILED,
                    progress=0,
                    message=f"Rolled back to version {previous_version}",
                    error=f"ROLLBACK_LEVEL_1_SUCCESS: {previous_version}",
                    version=previous_version,
                )

            return previous_version

        except Exception as e:
            self.logger.error(f"Level 1 rollback failed: {e}")

            # Report rollback failure to device-api
            if self.reporter:
                await self.reporter.report_progress(
                    stage=StageEnum.FAILED,
                    progress=0,
                    message="Level 1 rollback failed, attempting Level 2...",
                    error=f"ROLLBACK_LEVEL_1_FAILED: {str(e)}",
                    version=manifest.version,
                )

            raise RuntimeError(f"ROLLBACK_LEVEL_1_FAILED: {e}") from e

    async def rollback_to_factory(self, manifest: Manifest) -> str:
        """Rollback to factory version (Level 2 rollback - last resort).

        This is called when Level 1 rollback fails or previous version is unhealthy.

        Args:
            manifest: Manifest with service information for health check

        Returns:
            Version string that was rolled back to

        Raises:
            RuntimeError: If no factory version available or rollback fails
        """
        self.logger.warning("Starting Level 2 rollback: rolling back to factory version")

        # Report factory rollback start to device-api
        if self.reporter:
            await self.reporter.report_progress(
                stage=StageEnum.FAILED,
                progress=0,
                message="Rolling back to factory version...",
                error="ROLLBACK_LEVEL_2",
                version=manifest.version,
            )

        try:
            # Stop services before rollback
            modules_with_services = [
                m for m in manifest.modules if m.process_name is not None
            ]
            if modules_with_services:
                self.logger.info("Stopping services before factory rollback")
                await self._stop_services(modules_with_services)

            # Perform factory rollback using VersionManager
            factory_version = self.version_manager.rollback_to_factory()
            self.logger.warning(f"✓ Rolled back to factory version {factory_version}")

            # Restart services
            if modules_with_services:
                self.logger.info("Restarting services after factory rollback")
                await self._start_services(modules_with_services)

            # Verify services are healthy
            self.logger.info("Verifying service health after factory rollback")
            is_healthy = await self.verify_services_healthy(manifest)

            if not is_healthy:
                self.logger.error("Factory version is unhealthy after rollback!")
                raise RuntimeError(
                    f"Factory version {factory_version} is unhealthy"
                )

            self.logger.info(f"✓ Factory rollback to {factory_version} completed")

            # Report factory rollback success to device-api
            if self.reporter:
                await self._report_terminal_progress(
                    stage=StageEnum.FAILED,
                    progress=0,
                    message=f"Rolled back to factory version {factory_version}",
                    error=f"ROLLBACK_LEVEL_2_SUCCESS: {factory_version}",
                    version=factory_version,
                )

            return factory_version

        except Exception as e:
            self.logger.error(f"Level 2 rollback (factory) failed: {e}")

            # Report factory rollback failure to device-api
            if self.reporter:
                await self.reporter.report_progress(
                    stage=StageEnum.FAILED,
                    progress=0,
                    message="Factory rollback failed - manual intervention required",
                    error=f"ROLLBACK_LEVEL_2_FAILED: {str(e)}",
                    version=manifest.version,
                )

            raise RuntimeError(f"ROLLBACK_LEVEL_2_FAILED: {e}") from e

    async def verify_services_healthy(
        self,
        manifest: Manifest,
        timeout: int = 30
    ) -> bool:
        """Verify that all services are healthy after rollback.

        Args:
            manifest: Manifest with service information
            timeout: Timeout in seconds for service health check

        Returns:
            True if all services are healthy, False otherwise
        """
        modules_with_services = [
            m for m in manifest.modules if m.process_name is not None
        ]

        if not modules_with_services:
            # No services to check, consider healthy
            self.logger.debug("No services to check, marking as healthy")
            return True

        self.logger.info(f"Checking health of {len(modules_with_services)} services")

        all_healthy = True
        service_names = list(set(
            m.process_name for m in modules_with_services if m.process_name
        ))

        for service_name in service_names:
            try:
                self.logger.debug(f"Checking health of {service_name}")

                # Wait for service to be active
                await self.process_manager.wait_for_service_status(
                    service_name,
                    target_status=ServiceStatus.ACTIVE,
                    timeout=timeout
                )

                self.logger.info(f"✓ {service_name} is healthy")

            except Exception as e:
                self.logger.error(f"✗ {service_name} is unhealthy: {e}")
                all_healthy = False

        return all_healthy

    async def perform_two_level_rollback(
        self,
        manifest: Manifest,
        original_error: Exception
    ) -> str:
        """Perform two-level rollback: previous → factory.

        Workflow:
        1. Try Level 1: Rollback to previous version
        2. Verify previous version is healthy
        3. If previous is unhealthy, try Level 2: Rollback to factory
        4. Verify factory version is healthy
        5. If factory is also unhealthy, manual intervention required

        Args:
            manifest: Manifest with service information
            original_error: The original deployment error

        Returns:
            Version string that was finally rolled back to

        Raises:
            RuntimeError: If both rollback levels fail
        """
        self.logger.error("Deployment failed, initiating two-level rollback")

        # Try Level 1 rollback: previous version
        try:
            rolled_back_version = await self.rollback_to_previous(manifest)
            self.logger.info(
                f"Level 1 rollback succeeded: now running version {rolled_back_version}"
            )
            return rolled_back_version

        except Exception as level1_error:
            self.logger.error(
                f"Level 1 rollback failed: {level1_error}. "
                f"Attempting Level 2 rollback to factory version..."
            )

            # Try Level 2 rollback: factory version
            try:
                factory_version = await self.rollback_to_factory(manifest)
                self.logger.warning(
                    f"Level 2 rollback succeeded: now running factory version {factory_version}"
                )
                return factory_version

            except Exception as level2_error:
                self.logger.error(
                    f"Level 2 rollback also failed: {level2_error}. "
                    f"Manual intervention required!"
                )

                # Report complete failure to device-api
                if self.reporter:
                    await self.reporter.report_progress(
                        stage=StageEnum.FAILED,
                        progress=0,
                        message="Both rollbacks failed - manual intervention required",
                        error=(
                            f"DEPLOYMENT_FAILED: {original_error}\n"
                            f"ROLLBACK_LEVEL_1_FAILED: {level1_error}\n"
                            f"ROLLBACK_LEVEL_2_FAILED: {level2_error}"
                        ),
                        version=manifest.version,
                    )

                raise RuntimeError(
                    f"DEPLOYMENT_FAILED: {original_error}\n"
                    f"ROLLBACK_LEVEL_1_FAILED: {level1_error}\n"
                    f"ROLLBACK_LEVEL_2_FAILED: {level2_error}\n"
                    f"Manual intervention required!"
                ) from level2_error
