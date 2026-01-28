"""Unit tests for VersionManager."""

import pytest
import os
import unittest.mock
from pathlib import Path
from updater.services.version_manager import VersionManager


@pytest.mark.unit
class TestVersionManager:
    """Test VersionManager in isolation."""

    @pytest.fixture
    def version_manager(self, tmp_path):
        """Create VersionManager with temporary directory."""
        base_dir = tmp_path / "versions"
        return VersionManager(base_dir=str(base_dir))

    def test_init_creates_base_directory(self, tmp_path):
        """Test that initialization creates base directory."""
        base_dir = tmp_path / "versions"
        vm = VersionManager(base_dir=str(base_dir))

        assert base_dir.exists()
        assert base_dir.is_dir()
        assert vm.base_dir == base_dir

    def test_create_version_dir(self, version_manager):
        """Test creating a new version directory."""
        version_dir = version_manager.create_version_dir("1.0.0")

        assert version_dir.exists()
        assert version_dir.is_dir()
        assert version_dir.name == "v1.0.0"

    def test_create_version_dir_duplicate_raises_error(self, version_manager):
        """Test that creating duplicate version raises error."""
        version_manager.create_version_dir("1.0.0")

        with pytest.raises(ValueError, match="already exists"):
            version_manager.create_version_dir("1.0.0")

    def test_update_symlink_creates_new_link(self, version_manager):
        """Test creating a new symlink."""
        # Create target directory
        target = version_manager.base_dir / "v1.0.0"
        target.mkdir()

        # Create symlink
        link = version_manager.base_dir / "test_link"
        version_manager.update_symlink(link, target)

        assert link.exists()
        assert link.is_symlink()
        assert link.resolve() == target

    def test_update_symlink_replaces_existing_link(self, version_manager):
        """Test that update_symlink atomically replaces existing link."""
        # Create two target directories
        target1 = version_manager.base_dir / "v1.0.0"
        target1.mkdir()
        target2 = version_manager.base_dir / "v1.1.0"
        target2.mkdir()

        # Create initial symlink
        link = version_manager.base_dir / "test_link"
        version_manager.update_symlink(link, target1)
        assert link.resolve() == target1

        # Update symlink to new target
        version_manager.update_symlink(link, target2)
        assert link.resolve() == target2

    def test_update_symlink_target_not_exists_raises_error(self, version_manager):
        """Test that update_symlink raises error if target doesn't exist."""
        target = version_manager.base_dir / "nonexistent"
        link = version_manager.base_dir / "test_link"

        with pytest.raises(FileNotFoundError, match="Target does not exist"):
            version_manager.update_symlink(link, target)

    def test_get_current_version_not_set(self, version_manager):
        """Test get_current_version when not set."""
        assert version_manager.get_current_version() is None

    def test_get_current_version(self, version_manager):
        """Test get_current_version returns correct version."""
        # Create version and set as current
        version_dir = version_manager.create_version_dir("1.2.0")
        version_manager.update_symlink(version_manager.current_link, version_dir)

        assert version_manager.get_current_version() == "1.2.0"

    def test_get_previous_version_not_set(self, version_manager):
        """Test get_previous_version when not set."""
        assert version_manager.get_previous_version() is None

    def test_get_previous_version(self, version_manager):
        """Test get_previous_version returns correct version."""
        # Create version and set as previous
        version_dir = version_manager.create_version_dir("1.1.0")
        version_manager.update_symlink(version_manager.previous_link, version_dir)

        assert version_manager.get_previous_version() == "1.1.0"

    def test_get_factory_version_not_set(self, version_manager):
        """Test get_factory_version when not set."""
        assert version_manager.get_factory_version() is None

    def test_get_factory_version(self, version_manager):
        """Test get_factory_version returns correct version."""
        # Create version and set as factory
        version_dir = version_manager.create_version_dir("1.0.0")
        version_manager.update_symlink(version_manager.factory_link, version_dir)

        assert version_manager.get_factory_version() == "1.0.0"

    def test_list_versions_empty(self, version_manager):
        """Test list_versions when no versions exist."""
        assert version_manager.list_versions() == []

    def test_list_versions(self, version_manager):
        """Test list_versions returns all versions sorted."""
        # Create multiple versions
        version_manager.create_version_dir("1.2.0")
        version_manager.create_version_dir("1.0.0")
        version_manager.create_version_dir("1.1.0")

        versions = version_manager.list_versions()

        assert versions == ["1.0.0", "1.1.0", "1.2.0"]

    def test_list_versions_ignores_symlinks(self, version_manager):
        """Test that list_versions ignores symlinks."""
        # Create version and symlink
        version_dir = version_manager.create_version_dir("1.0.0")
        version_manager.update_symlink(version_manager.current_link, version_dir)

        versions = version_manager.list_versions()

        # Should only include actual version directories, not symlinks
        assert versions == ["1.0.0"]

    def test_promote_version_first_time(self, version_manager):
        """Test promoting a version when no current version exists."""
        # Create version
        version_manager.create_version_dir("1.0.0")

        # Promote to current
        version_manager.promote_version("1.0.0")

        assert version_manager.get_current_version() == "1.0.0"
        assert version_manager.get_previous_version() is None

    def test_promote_version_with_existing_current(self, version_manager):
        """Test promoting a version moves current to previous."""
        # Create and promote first version
        version_manager.create_version_dir("1.0.0")
        version_manager.promote_version("1.0.0")

        # Create and promote second version
        version_manager.create_version_dir("1.1.0")
        version_manager.promote_version("1.1.0")

        assert version_manager.get_current_version() == "1.1.0"
        assert version_manager.get_previous_version() == "1.0.0"

    def test_promote_version_nonexistent_raises_error(self, version_manager):
        """Test promoting nonexistent version raises error."""
        with pytest.raises(FileNotFoundError, match="not found"):
            version_manager.promote_version("9.9.9")

    def test_set_factory_version(self, version_manager):
        """Test setting factory version."""
        # Create version
        version_manager.create_version_dir("1.0.0")

        # Set as factory
        version_manager.set_factory_version("1.0.0")

        assert version_manager.get_factory_version() == "1.0.0"

    def test_set_factory_version_already_set_raises_error(self, version_manager):
        """Test that setting factory version twice raises error."""
        version_manager.create_version_dir("1.0.0")
        version_manager.set_factory_version("1.0.0")

        version_manager.create_version_dir("1.1.0")

        with pytest.raises(ValueError, match="already set"):
            version_manager.set_factory_version("1.1.0")

    def test_set_factory_version_nonexistent_raises_error(self, version_manager):
        """Test setting nonexistent factory version raises error."""
        with pytest.raises(FileNotFoundError, match="not found"):
            version_manager.set_factory_version("9.9.9")

    def test_rollback_to_previous(self, version_manager):
        """Test rolling back to previous version."""
        # Setup: v1.0.0 (previous) and v1.1.0 (current)
        version_manager.create_version_dir("1.0.0")
        version_manager.promote_version("1.0.0")
        version_manager.create_version_dir("1.1.0")
        version_manager.promote_version("1.1.0")

        # Rollback
        rolled_back_version = version_manager.rollback_to_previous()

        assert rolled_back_version == "1.0.0"
        assert version_manager.get_current_version() == "1.0.0"

    def test_rollback_to_previous_not_available_raises_error(self, version_manager):
        """Test rollback when no previous version raises error."""
        with pytest.raises(RuntimeError, match="No previous version"):
            version_manager.rollback_to_previous()

    def test_rollback_to_factory(self, version_manager):
        """Test rolling back to factory version."""
        # Setup: factory v1.0.0, current v1.2.0
        version_manager.create_version_dir("1.0.0")
        version_manager.set_factory_version("1.0.0")
        version_manager.promote_version("1.0.0")

        version_manager.create_version_dir("1.2.0")
        version_manager.promote_version("1.2.0")

        # Rollback to factory
        rolled_back_version = version_manager.rollback_to_factory()

        assert rolled_back_version == "1.0.0"
        assert version_manager.get_current_version() == "1.0.0"

    def test_rollback_to_factory_not_available_raises_error(self, version_manager):
        """Test rollback to factory when not set raises error."""
        with pytest.raises(RuntimeError, match="No factory version"):
            version_manager.rollback_to_factory()

    def test_delete_version(self, version_manager):
        """Test deleting a version."""
        # Create multiple versions
        version_manager.create_version_dir("1.0.0")
        version_manager.create_version_dir("1.1.0")
        version_manager.create_version_dir("1.2.0")

        # Delete one
        version_manager.delete_version("1.1.0")

        versions = version_manager.list_versions()
        assert "1.1.0" not in versions
        assert versions == ["1.0.0", "1.2.0"]

    def test_delete_current_version_raises_error(self, version_manager):
        """Test that deleting current version raises error."""
        version_manager.create_version_dir("1.0.0")
        version_manager.promote_version("1.0.0")

        with pytest.raises(ValueError, match="Cannot delete current version"):
            version_manager.delete_version("1.0.0")

    def test_delete_previous_version_raises_error(self, version_manager):
        """Test that deleting previous version raises error."""
        version_manager.create_version_dir("1.0.0")
        version_manager.promote_version("1.0.0")
        version_manager.create_version_dir("1.1.0")
        version_manager.promote_version("1.1.0")

        with pytest.raises(ValueError, match="Cannot delete previous version"):
            version_manager.delete_version("1.0.0")

    def test_delete_factory_version_raises_error(self, version_manager):
        """Test that deleting factory version raises error."""
        version_manager.create_version_dir("1.0.0")
        version_manager.set_factory_version("1.0.0")

        with pytest.raises(ValueError, match="Cannot delete factory version"):
            version_manager.delete_version("1.0.0")

    def test_delete_nonexistent_version_raises_error(self, version_manager):
        """Test deleting nonexistent version raises error."""
        with pytest.raises(FileNotFoundError, match="not found"):
            version_manager.delete_version("9.9.9")

    def test_full_upgrade_workflow(self, version_manager):
        """Test complete upgrade workflow with rollback capability."""
        # Step 1: Initial setup with factory version
        version_manager.create_version_dir("1.0.0")
        version_manager.set_factory_version("1.0.0")
        version_manager.promote_version("1.0.0")

        assert version_manager.get_current_version() == "1.0.0"
        assert version_manager.get_factory_version() == "1.0.0"

        # Step 2: Upgrade to v1.1.0
        version_manager.create_version_dir("1.1.0")
        version_manager.promote_version("1.1.0")

        assert version_manager.get_current_version() == "1.1.0"
        assert version_manager.get_previous_version() == "1.0.0"

        # Step 3: Upgrade to v1.2.0
        version_manager.create_version_dir("1.2.0")
        version_manager.promote_version("1.2.0")

        assert version_manager.get_current_version() == "1.2.0"
        assert version_manager.get_previous_version() == "1.1.0"

        # Step 4: Rollback to previous (v1.1.0)
        version_manager.rollback_to_previous()

        assert version_manager.get_current_version() == "1.1.0"

        # Step 5: If still failing, rollback to factory (v1.0.0)
        version_manager.rollback_to_factory()

        assert version_manager.get_current_version() == "1.0.0"

    def test_symlink_is_atomic(self, version_manager):
        """Test that symlink update is atomic (no intermediate state)."""
        # Create two versions
        v1 = version_manager.create_version_dir("1.0.0")
        v2 = version_manager.create_version_dir("1.1.0")

        # Create initial symlink
        link = version_manager.base_dir / "test"
        version_manager.update_symlink(link, v1)

        # Update symlink - should be atomic
        version_manager.update_symlink(link, v2)

        # Verify no temporary files left behind
        temp_files = list(version_manager.base_dir.glob(".test.tmp.*"))
        assert len(temp_files) == 0, "Temporary symlink files should be cleaned up"

        # Verify link points to new target
        assert link.resolve() == v2

    def test_create_factory_version_from_current(self, version_manager, tmp_path):
        """Test creating factory version from current version."""
        # Create and promote current version
        version_manager.create_version_dir("1.0.0")
        version_manager.promote_version("1.0.0")

        # Add a test file to verify it's copied
        test_file = version_manager.current_link.resolve() / "test.txt"
        test_file.write_text("test content")

        # Create factory version
        factory_dir = version_manager.create_factory_version("1.0.0")

        # Verify factory version created
        assert factory_dir.exists()
        assert factory_dir.is_dir()
        assert factory_dir.name == "v1.0.0"

        # Verify factory symlink
        assert version_manager.factory_link.exists()
        assert version_manager.get_factory_version() == "1.0.0"

        # Verify content was preserved (if same version, just symlink)
        assert (factory_dir / "test.txt").exists()

    def test_create_factory_version_no_current_raises_error(self, version_manager):
        """Test creating factory version without current version raises error."""
        with pytest.raises(RuntimeError, match="No current version"):
            version_manager.create_factory_version("1.0.0")

    def test_create_factory_version_already_set_raises_error(self, version_manager):
        """Test creating factory version twice raises error."""
        # Setup current and factory
        version_manager.create_version_dir("1.0.0")
        version_manager.promote_version("1.0.0")
        version_manager.create_factory_version("1.0.0")

        # Try to create factory version again
        with pytest.raises(ValueError, match="already set"):
            version_manager.create_factory_version("1.1.0")

    def test_verify_factory_version_valid(self, version_manager):
        """Test verifying a valid factory version."""
        # Create factory version with content
        version_manager.create_version_dir("1.0.0")
        version_manager.promote_version("1.0.0")

        # Add a test file to make it non-empty
        test_file = version_manager.current_link.resolve() / "test.txt"
        test_file.write_text("test content")

        version_manager.create_factory_version("1.0.0")

        # Verify
        assert version_manager.verify_factory_version() is True

    def test_verify_factory_version_no_symlink(self, version_manager):
        """Test verifying factory version when symlink doesn't exist."""
        assert version_manager.verify_factory_version() is False

    def test_verify_factory_version_empty_directory(self, version_manager):
        """Test verifying factory version with empty directory."""
        # Create empty factory directory
        version_manager.create_version_dir("1.0.0")
        version_manager.set_factory_version("1.0.0")

        # Empty factory directory should fail verification
        # Note: create_version_dir creates empty dir, so verification fails
        # This is expected behavior - factory should have content
        assert version_manager.verify_factory_version() is False

    def test_is_factory_readonly_after_creation(self, version_manager):
        """Test that factory version is created and _set_directory_readonly is called."""
        # Create factory version with content
        version_manager.create_version_dir("1.0.0")
        version_manager.promote_version("1.0.0")

        # Add a test file to current version
        test_file = version_manager.current_link.resolve() / "test.txt"
        test_file.write_text("test content")

        # Mock the _set_directory_readonly method to verify it's called
        with unittest.mock.patch.object(
            version_manager,
            '_set_directory_readonly'
        ) as mock_set_readonly:
            # Create factory version
            version_manager.create_factory_version("1.0.0")

            # Verify _set_directory_readonly was called
            mock_set_readonly.assert_called_once()

            # Verify factory symlink exists
            assert version_manager.factory_link.exists()
            assert version_manager.get_factory_version() == "1.0.0"

    def test_is_factory_readonly_no_factory(self, version_manager):
        """Test is_factory_readonly when no factory version exists."""
        assert version_manager.is_factory_readonly() is False

    def test_factory_version_protected_from_deletion(self, version_manager):
        """Test that factory version cannot be deleted."""
        # Create factory version
        version_manager.create_version_dir("1.0.0")
        version_manager.set_factory_version("1.0.0")

        # Try to delete factory version
        with pytest.raises(ValueError, match="Cannot delete factory version"):
            version_manager.delete_version("1.0.0")

