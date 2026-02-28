"""Unit tests for VersionManager."""

import pytest
import os
import stat
import unittest.mock
from pathlib import Path
from unittest.mock import patch, MagicMock
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


@pytest.mark.unit
class TestVersionManagerEdgeCases:
    """测试 VersionManager 边界情况和异常路径。"""

    @pytest.fixture
    def version_manager(self, tmp_path):
        """创建使用临时目录的 VersionManager。"""
        base_dir = tmp_path / "versions"
        return VersionManager(base_dir=str(base_dir))

    # ------------------------------------------------------------------
    # update_symlink 异常清理路径 (lines 101-105)
    # ------------------------------------------------------------------

    def test_update_symlink_cleans_up_temp_on_failure(self, version_manager):
        """update_symlink 在 replace 失败时应清理临时文件。"""
        target = version_manager.base_dir / "v1.0.0"
        target.mkdir()
        link_path = version_manager.base_dir / "current"

        # 让 temp_link.replace 抛出异常，模拟 rename 失败
        original_replace = Path.replace

        def _bad_replace(self, *args, **kwargs):
            raise OSError("replace failed")

        with patch.object(Path, "replace", _bad_replace):
            with pytest.raises(OSError, match="Failed to update symlink"):
                version_manager.update_symlink(link_path, target)

        # 临时文件应已被清理
        temp_files = list(version_manager.base_dir.glob(".current.tmp.*"))
        assert len(temp_files) == 0

    # ------------------------------------------------------------------
    # get_current_version 边界情况 (lines 122-123, 131)
    # ------------------------------------------------------------------

    def test_get_current_version_not_symlink(self, version_manager):
        """current 是普通目录（不是符号链接）时应返回 None。"""
        # 创建普通目录冒充 current 链接
        version_manager.current_link.mkdir()
        assert version_manager.get_current_version() is None

    def test_get_current_version_without_v_prefix(self, version_manager):
        """版本目录名不以 v 开头时，返回原始名称。"""
        # 创建不带 v 前缀的目录，手动建符号链接
        no_prefix_dir = version_manager.base_dir / "1.0.0"
        no_prefix_dir.mkdir()
        version_manager.current_link.symlink_to("1.0.0")
        assert version_manager.get_current_version() == "1.0.0"

    # ------------------------------------------------------------------
    # get_previous_version 边界情况 (lines 143-144, 151)
    # ------------------------------------------------------------------

    def test_get_previous_version_not_symlink(self, version_manager):
        """previous 是普通目录时应返回 None。"""
        version_manager.previous_link.mkdir()
        assert version_manager.get_previous_version() is None

    def test_get_previous_version_without_v_prefix(self, version_manager):
        """previous 版本目录无 v 前缀时返回原始名称。"""
        no_prefix_dir = version_manager.base_dir / "1.0.0"
        no_prefix_dir.mkdir()
        version_manager.previous_link.symlink_to("1.0.0")
        assert version_manager.get_previous_version() == "1.0.0"

    # ------------------------------------------------------------------
    # get_factory_version 边界情况 (lines 163-164, 171)
    # ------------------------------------------------------------------

    def test_get_factory_version_not_symlink(self, version_manager):
        """factory 是普通目录时应返回 None。"""
        version_manager.factory_link.mkdir()
        assert version_manager.get_factory_version() is None

    def test_get_factory_version_without_v_prefix(self, version_manager):
        """factory 版本目录无 v 前缀时返回原始名称。"""
        no_prefix_dir = version_manager.base_dir / "1.0.0"
        no_prefix_dir.mkdir()
        version_manager.factory_link.symlink_to("1.0.0")
        assert version_manager.get_factory_version() == "1.0.0"

    # ------------------------------------------------------------------
    # list_versions 无 v 前缀 (line 191)
    # ------------------------------------------------------------------

    def test_list_versions_without_v_prefix(self, version_manager):
        """list_versions 对无 v 前缀目录也应正常列出。"""
        # 手动创建无前缀目录
        (version_manager.base_dir / "1.0.0").mkdir()
        versions = version_manager.list_versions()
        assert "1.0.0" in versions

    # ------------------------------------------------------------------
    # rollback_to_previous 目录不存在 (line 266)
    # ------------------------------------------------------------------

    def test_rollback_to_previous_dir_missing(self, version_manager):
        """previous 指向无 v 前缀目录时，rollback 应抛出 'directory not found'。

        场景：previous 链接指向 base_dir/1.0.0（无 v 前缀），
        get_previous_version() 因此返回 "1.0.0"，但
        rollback_to_previous() 查找的是 base_dir/v1.0.0（不存在）。
        """
        # 创建无 v 前缀目录并手动建符号链接
        no_prefix_dir = version_manager.base_dir / "1.0.0"
        no_prefix_dir.mkdir()
        version_manager.previous_link.symlink_to("1.0.0")

        with pytest.raises(RuntimeError, match="Previous version directory not found"):
            version_manager.rollback_to_previous()

    # ------------------------------------------------------------------
    # rollback_to_factory 目录不存在 (line 291)
    # ------------------------------------------------------------------

    def test_rollback_to_factory_dir_missing(self, version_manager):
        """factory 指向无 v 前缀目录时，rollback 应抛出 'directory not found'。"""
        no_prefix_dir = version_manager.base_dir / "1.0.0"
        no_prefix_dir.mkdir()
        version_manager.factory_link.symlink_to("1.0.0")

        with pytest.raises(RuntimeError, match="Factory version directory not found"):
            version_manager.rollback_to_factory()

    # ------------------------------------------------------------------
    # create_factory_version 不同版本（复制路径）(lines 377-381)
    # ------------------------------------------------------------------

    def test_create_factory_version_different_version(self, version_manager):
        """当前版本与 factory 版本不同时，应复制目录。"""
        # 当前版本为 1.0.0，factory 设为 0.9.0
        version_dir = version_manager.create_version_dir("1.0.0")
        version_manager.promote_version("1.0.0")
        test_file = version_dir / "app.py"
        test_file.write_text("print('hello')")

        factory_dir = version_manager.create_factory_version("0.9.0")

        assert factory_dir.exists()
        assert factory_dir.name == "v0.9.0"
        assert (factory_dir / "app.py").exists()
        assert version_manager.get_factory_version() == "0.9.0"

    # ------------------------------------------------------------------
    # create_factory_version 异常清理 (lines 389-393)
    # ------------------------------------------------------------------

    def test_create_factory_version_cleanup_on_failure(self, version_manager):
        """create_factory_version 中途失败时应清理已创建的目录。"""
        version_dir = version_manager.create_version_dir("1.0.0")
        version_manager.promote_version("1.0.0")
        (version_dir / "app.py").write_text("code")

        # 让 set_factory_version 抛出异常（复制路径）
        with patch.object(version_manager, "set_factory_version", side_effect=OSError("mock fail")):
            with pytest.raises(OSError, match="Failed to create factory version"):
                version_manager.create_factory_version("0.9.0")

        # 已复制的目录应被清理
        assert not (version_manager.base_dir / "v0.9.0").exists()

    # ------------------------------------------------------------------
    # _set_directory_readonly 含子目录 (lines 403-405)
    # ------------------------------------------------------------------

    def test_set_directory_readonly_with_subdirs(self, version_manager, tmp_path):
        """_set_directory_readonly 应递归处理子目录。"""
        test_dir = tmp_path / "testdir"
        subdir = test_dir / "subdir"
        subdir.mkdir(parents=True)
        (subdir / "file.txt").write_text("content")

        version_manager._set_directory_readonly(test_dir)

        # 子目录应为只读 (555)
        subdir_mode = subdir.stat().st_mode & 0o777
        assert not (subdir_mode & 0o222), "子目录应无写权限"

        # 清理：恢复写权限才能让 tmp_path 清理
        subdir.chmod(0o755)
        (subdir / "file.txt").chmod(0o644)

    # ------------------------------------------------------------------
    # verify_factory_version 边界情况 (lines 433-434, 438-439, 453-454, 462-464)
    # ------------------------------------------------------------------

    def test_verify_factory_version_not_symlink(self, version_manager):
        """factory 存在但不是符号链接时应返回 False。"""
        version_manager.factory_link.mkdir()
        assert version_manager.verify_factory_version() is False

    def test_verify_factory_version_target_dir_missing(self, version_manager):
        """factory 符号链接指向不存在的目录时应返回 False。"""
        # 创建指向不存在路径的符号链接
        version_manager.factory_link.symlink_to("v_nonexistent")
        assert version_manager.verify_factory_version() is False

    def test_verify_factory_version_only_symlinks_in_dir(self, version_manager):
        """factory 目录中只有符号链接（无文件/目录）时应返回 False。"""
        # 创建 factory 目录，内部只放一个指向自身的符号链接
        factory_dir = version_manager.base_dir / "v1.0.0"
        factory_dir.mkdir()
        # 在 factory_dir 内放一个符号链接（既不是文件也不是目录的情况用 dangling symlink）
        dangling_link = factory_dir / "dead_link"
        dangling_link.symlink_to("nonexistent_target")

        version_manager.update_symlink(version_manager.factory_link, factory_dir)

        # factory_dir 有条目但 file_count=0, dir_count=0（都是符号链接）
        assert version_manager.verify_factory_version() is False

    def test_verify_factory_version_exception(self, version_manager):
        """iterdir 抛出异常时 verify_factory_version 应返回 False。"""
        factory_dir = version_manager.base_dir / "v1.0.0"
        factory_dir.mkdir()
        (factory_dir / "file.txt").write_text("x")
        version_manager.update_symlink(version_manager.factory_link, factory_dir)

        with patch.object(Path, "iterdir", side_effect=PermissionError("no access")):
            assert version_manager.verify_factory_version() is False

    # ------------------------------------------------------------------
    # is_factory_readonly (lines 477-504)
    # ------------------------------------------------------------------

    def test_is_factory_readonly_factory_dir_missing(self, version_manager):
        """factory 符号链接指向不存在目录时应返回 False。"""
        version_manager.factory_link.symlink_to("v_nonexistent")
        assert version_manager.is_factory_readonly() is False

    def test_is_factory_readonly_when_writable(self, version_manager):
        """factory 目录有写权限时 is_factory_readonly 应返回 False。"""
        factory_dir = version_manager.base_dir / "v1.0.0"
        factory_dir.mkdir(mode=0o755)
        version_manager.update_symlink(version_manager.factory_link, factory_dir)
        # 目录有写权限 → 不是只读
        assert version_manager.is_factory_readonly() is False

    def test_is_factory_readonly_file_with_write_permission(self, version_manager):
        """factory 目录中有可写文件时 is_factory_readonly 应返回 False。"""
        factory_dir = version_manager.base_dir / "v1.0.0"
        factory_dir.mkdir()
        # 先写文件（目录权限正常时），再调整目录权限
        test_file = factory_dir / "app.py"
        test_file.write_text("code")
        test_file.chmod(0o644)   # 文件保留写权限
        factory_dir.chmod(0o555)  # 目录设为只读（无写权限）
        version_manager.update_symlink(version_manager.factory_link, factory_dir)

        result = version_manager.is_factory_readonly()
        # 清理：恢复权限，让 tmp_path 能正常删除
        factory_dir.chmod(0o755)
        test_file.chmod(0o644)
        assert result is False

    def test_is_factory_readonly_truly_readonly(self, version_manager):
        """factory 目录和文件均只读时 is_factory_readonly 应返回 True。"""
        factory_dir = version_manager.base_dir / "v1.0.0"
        factory_dir.mkdir(mode=0o755)
        test_file = factory_dir / "app.py"
        test_file.write_text("code")
        version_manager._set_directory_readonly(factory_dir)
        # 目录本身也设只读
        factory_dir.chmod(0o555)
        version_manager.update_symlink(version_manager.factory_link, factory_dir)

        result = version_manager.is_factory_readonly()
        # 清理：恢复权限
        factory_dir.chmod(0o755)
        test_file.chmod(0o644)
        assert result is True

    def test_is_factory_readonly_exception_returns_false(self, version_manager):
        """rglob 抛出异常时 is_factory_readonly 应返回 False。"""
        factory_dir = version_manager.base_dir / "v1.0.0"
        factory_dir.mkdir(mode=0o555)
        version_manager.update_symlink(version_manager.factory_link, factory_dir)

        with patch.object(Path, "rglob", side_effect=PermissionError("denied")):
            result = version_manager.is_factory_readonly()

        factory_dir.chmod(0o755)
        assert result is False
