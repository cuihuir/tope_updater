"""Version snapshot management for two-level rollback strategy.

This module manages version snapshots and symlinks for the OTA updater.
It implements a two-level rollback strategy:
- Level 1: Rollback to previous version
- Level 2: Rollback to factory version (if previous fails)

Directory structure:
    /opt/tope/versions/
    ├── v1.0.0/              # Version snapshot directory
    ├── v1.1.0/
    ├── v1.2.0/
    ├── current -> v1.2.0/   # Current running version (symlink)
    ├── previous -> v1.1.0/  # Previous version (symlink)
    └── factory -> v1.0.0/   # Factory version (symlink, read-only)
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Optional, List
from datetime import datetime


class VersionManager:
    """Manages version snapshots and symlinks for rollback support."""

    def __init__(self, base_dir: str = "/opt/tope/versions"):
        """Initialize version manager.

        Args:
            base_dir: Base directory for version snapshots (default: /opt/tope/versions)
        """
        self.logger = logging.getLogger("updater.version_manager")
        self.base_dir = Path(base_dir)
        self.current_link = self.base_dir / "current"
        self.previous_link = self.base_dir / "previous"
        self.factory_link = self.base_dir / "factory"

        # Ensure base directory exists
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"VersionManager initialized with base_dir={base_dir}")

    def create_version_dir(self, version: str) -> Path:
        """Create a new version snapshot directory.

        Args:
            version: Version string (e.g., "1.0.0")

        Returns:
            Path to the created version directory

        Raises:
            ValueError: If version directory already exists
        """
        version_dir = self.base_dir / f"v{version}"

        if version_dir.exists():
            raise ValueError(f"Version directory already exists: {version_dir}")

        version_dir.mkdir(parents=True, exist_ok=False)
        self.logger.info(f"Created version directory: {version_dir}")

        return version_dir

    def update_symlink(self, link_path: Path, target: Path) -> None:
        """Atomically update a symlink to point to a new target.

        Uses the atomic rename technique:
        1. Create temporary symlink
        2. Atomically rename to final location

        Args:
            link_path: Path to the symlink
            target: Target path (relative to link_path's parent)

        Raises:
            FileNotFoundError: If target does not exist
            OSError: If symlink update fails
        """
        # Verify target exists
        if not target.exists():
            raise FileNotFoundError(f"Target does not exist: {target}")

        # Create temporary symlink
        temp_link = link_path.parent / f".{link_path.name}.tmp.{os.getpid()}"

        try:
            # Calculate relative path from link to target
            relative_target = os.path.relpath(target, link_path.parent)

            # Create temporary symlink
            temp_link.symlink_to(relative_target)

            # Atomically replace old symlink with new one
            temp_link.replace(link_path)

            self.logger.info(f"Updated symlink: {link_path} -> {target}")

        except Exception as e:
            # Cleanup temporary symlink on failure
            if temp_link.exists():
                temp_link.unlink()
            raise OSError(f"Failed to update symlink {link_path}: {e}") from e

    def get_current_version(self) -> Optional[str]:
        """Get the current running version.

        Returns:
            Version string (e.g., "1.0.0") or None if not set

        Example:
            >>> vm = VersionManager()
            >>> vm.get_current_version()
            '1.2.0'
        """
        if not self.current_link.exists():
            return None

        if not self.current_link.is_symlink():
            self.logger.warning(f"current is not a symlink: {self.current_link}")
            return None

        # Resolve symlink and extract version
        target = self.current_link.resolve()
        version_name = target.name  # e.g., "v1.0.0"

        if version_name.startswith("v"):
            return version_name[1:]  # Remove "v" prefix
        return version_name

    def get_previous_version(self) -> Optional[str]:
        """Get the previous version (for rollback).

        Returns:
            Version string (e.g., "1.0.0") or None if not set
        """
        if not self.previous_link.exists():
            return None

        if not self.previous_link.is_symlink():
            self.logger.warning(f"previous is not a symlink: {self.previous_link}")
            return None

        target = self.previous_link.resolve()
        version_name = target.name

        if version_name.startswith("v"):
            return version_name[1:]
        return version_name

    def get_factory_version(self) -> Optional[str]:
        """Get the factory version (for factory reset).

        Returns:
            Version string (e.g., "1.0.0") or None if not set
        """
        if not self.factory_link.exists():
            return None

        if not self.factory_link.is_symlink():
            self.logger.warning(f"factory is not a symlink: {self.factory_link}")
            return None

        target = self.factory_link.resolve()
        version_name = target.name

        if version_name.startswith("v"):
            return version_name[1:]
        return version_name

    def list_versions(self) -> List[str]:
        """List all available version snapshots.

        Returns:
            List of version strings sorted by name (e.g., ["1.0.0", "1.1.0", "1.2.0"])
        """
        versions = []

        for item in self.base_dir.iterdir():
            # Skip symlinks and non-directories
            if item.is_symlink() or not item.is_dir():
                continue

            # Extract version from directory name
            version_name = item.name
            if version_name.startswith("v"):
                versions.append(version_name[1:])
            else:
                versions.append(version_name)

        # Sort versions
        versions.sort()
        return versions

    def promote_version(self, version: str) -> None:
        """Promote a version to current, moving current to previous.

        This is the main operation for version upgrades:
        1. Move current -> previous
        2. Move new version -> current

        Args:
            version: Version to promote (e.g., "1.2.0")

        Raises:
            FileNotFoundError: If version directory does not exist
            OSError: If symlink update fails
        """
        version_dir = self.base_dir / f"v{version}"

        if not version_dir.exists():
            raise FileNotFoundError(f"Version directory not found: {version_dir}")

        # Step 1: Save current as previous (if current exists)
        if self.current_link.exists():
            current_target = self.current_link.resolve()
            self.update_symlink(self.previous_link, current_target)
            self.logger.info(f"Moved current to previous: {current_target.name}")

        # Step 2: Promote new version to current
        self.update_symlink(self.current_link, version_dir)
        self.logger.info(f"Promoted version to current: {version}")

    def set_factory_version(self, version: str) -> None:
        """Set the factory version (one-time operation).

        This should only be called once during initial setup.

        Args:
            version: Factory version (e.g., "1.0.0")

        Raises:
            FileNotFoundError: If version directory does not exist
            ValueError: If factory version is already set
        """
        if self.factory_link.exists():
            raise ValueError(f"Factory version already set: {self.get_factory_version()}")

        version_dir = self.base_dir / f"v{version}"

        if not version_dir.exists():
            raise FileNotFoundError(f"Version directory not found: {version_dir}")

        self.update_symlink(self.factory_link, version_dir)
        self.logger.info(f"Set factory version: {version}")

    def rollback_to_previous(self) -> str:
        """Rollback to previous version.

        Returns:
            Version string that was rolled back to

        Raises:
            RuntimeError: If previous version is not available
        """
        previous_version = self.get_previous_version()

        if not previous_version:
            raise RuntimeError("No previous version available for rollback")

        previous_dir = self.base_dir / f"v{previous_version}"

        if not previous_dir.exists():
            raise RuntimeError(f"Previous version directory not found: {previous_dir}")

        # Update current to point to previous
        self.update_symlink(self.current_link, previous_dir)
        self.logger.info(f"Rolled back to previous version: {previous_version}")

        return previous_version

    def rollback_to_factory(self) -> str:
        """Rollback to factory version (last resort).

        Returns:
            Version string that was rolled back to

        Raises:
            RuntimeError: If factory version is not available
        """
        factory_version = self.get_factory_version()

        if not factory_version:
            raise RuntimeError("No factory version available for rollback")

        factory_dir = self.base_dir / f"v{factory_version}"

        if not factory_dir.exists():
            raise RuntimeError(f"Factory version directory not found: {factory_dir}")

        # Update current to point to factory
        self.update_symlink(self.current_link, factory_dir)
        self.logger.info(f"Rolled back to factory version: {factory_version}")

        return factory_version

    def delete_version(self, version: str) -> None:
        """Delete a version snapshot directory.

        Safety checks:
        - Cannot delete current version
        - Cannot delete previous version
        - Cannot delete factory version

        Args:
            version: Version to delete (e.g., "1.0.0")

        Raises:
            ValueError: If trying to delete a protected version
            FileNotFoundError: If version directory does not exist
        """
        # Safety checks
        if version == self.get_current_version():
            raise ValueError(f"Cannot delete current version: {version}")

        if version == self.get_previous_version():
            raise ValueError(f"Cannot delete previous version: {version}")

        if version == self.get_factory_version():
            raise ValueError(f"Cannot delete factory version: {version}")

        version_dir = self.base_dir / f"v{version}"

        if not version_dir.exists():
            raise FileNotFoundError(f"Version directory not found: {version_dir}")

        # Delete directory
        shutil.rmtree(version_dir)
        self.logger.info(f"Deleted version: {version}")

    def create_factory_version(self, version: str) -> Path:
        """Create factory version from current version.

        If the specified version matches the current version, it simply sets
        the factory symlink. Otherwise, it copies the current version to create
        a new factory snapshot.

        Args:
            version: Version string for factory version (e.g., "1.0.0")

        Returns:
            Path to the factory version directory

        Raises:
            RuntimeError: If no current version exists
            ValueError: If factory version is already set
            OSError: If copy operation fails

        Note:
            This should be called once during initial system setup.
            The factory version will be set as read-only to prevent modification.
        """
        # Check if current version exists
        current_version = self.get_current_version()
        if not current_version:
            raise RuntimeError("No current version to create factory version from")

        current_dir = self.current_link.resolve()
        factory_dir = self.base_dir / f"v{version}"

        # Check if factory version already set
        if self.factory_link.exists():
            raise ValueError(f"Factory version already set: {self.get_factory_version()}")

        self.logger.info(f"Creating factory version {version} from current {current_version}")

        try:
            # If current version matches factory version, just set symlink
            if current_version == version:
                self.logger.info(f"Current version {version} matches factory version")
                self.set_factory_version(version)
                factory_dir = current_dir
            else:
                # Copy current version to factory version directory
                shutil.copytree(current_dir, factory_dir)
                self.logger.info(f"Copied {current_dir} to {factory_dir}")

                # Set as factory version
                self.set_factory_version(version)

            # Make factory version read-only
            self._set_directory_readonly(factory_dir)
            self.logger.info(f"Set factory version {version} as read-only")

            return factory_dir

        except Exception as e:
            # Cleanup on failure (only if we created a new directory)
            if factory_dir != current_dir and factory_dir.exists():
                shutil.rmtree(factory_dir)
            raise OSError(f"Failed to create factory version: {e}") from e

    def _set_directory_readonly(self, directory: Path) -> None:
        """Recursively set directory and files as read-only.

        Args:
            directory: Directory path to make read-only
        """
        for root, dirs, files in os.walk(directory):
            for d in dirs:
                dir_path = Path(root) / d
                # Set directory permissions to read-only (555 = r-xr-xr-x)
                dir_path.chmod(0o555)

            for f in files:
                file_path = Path(root) / f
                # Set file permissions to read-only (444 = r--r--r--)
                file_path.chmod(0o444)

        self.logger.debug(f"Set read-only permissions for: {directory}")

    def verify_factory_version(self) -> bool:
        """Verify that factory version exists and is complete.

        Returns:
            True if factory version is valid, False otherwise

        Checks:
        1. Factory symlink exists
        2. Factory directory exists
        3. Factory directory is not empty
        4. Factory directory has reasonable structure
        """
        # Check factory symlink exists
        if not self.factory_link.exists():
            self.logger.warning("Factory symlink does not exist")
            return False

        # Check factory symlink points to valid directory
        if not self.factory_link.is_symlink():
            self.logger.warning("Factory is not a symlink")
            return False

        factory_dir = self.factory_link.resolve()
        if not factory_dir.exists() or not factory_dir.is_dir():
            self.logger.warning(f"Factory directory does not exist: {factory_dir}")
            return False

        # Check directory is not empty
        try:
            items = list(factory_dir.iterdir())
            if len(items) == 0:
                self.logger.warning(f"Factory directory is empty: {factory_dir}")
                return False

            # Check for reasonable structure (has at least some files/directories)
            file_count = sum(1 for item in items if item.is_file())
            dir_count = sum(1 for item in items if item.is_dir())

            if file_count == 0 and dir_count == 0:
                self.logger.warning(f"Factory directory has no content: {factory_dir}")
                return False

            self.logger.info(
                f"Factory version verified: {factory_dir.name} "
                f"({file_count} files, {dir_count} directories)"
            )
            return True

        except Exception as e:
            self.logger.error(f"Error verifying factory version: {e}")
            return False

    def is_factory_readonly(self) -> bool:
        """Check if factory version is read-only.

        Checks if the factory directory and all its contents are read-only.

        Returns:
            True if factory version is read-only, False otherwise
        """
        if not self.factory_link.exists():
            return False

        factory_dir = self.factory_link.resolve()
        if not factory_dir.exists():
            return False

        # Check factory directory itself
        stat_info = factory_dir.stat()
        mode = stat_info.st_mode

        # Check if write bit is set for owner, group, or others
        if mode & 0o222:  # Directory has write permission
            return False

        # Check all files in directory tree
        try:
            for item in factory_dir.rglob("*"):
                if item.is_file():
                    item_mode = item.stat().st_mode
                    # If any file has write permission, not read-only
                    if item_mode & 0o222:
                        self.logger.debug(f"File has write permission: {item}")
                        return False
        except Exception as e:
            # If we can't check permissions, assume not read-only
            self.logger.error(f"Error checking factory permissions: {e}")
            return False

        self.logger.debug(f"Factory version read-only status: True")
        return True

