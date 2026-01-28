"""Unit tests for DeployService."""

import pytest
import json
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from datetime import datetime

from updater.services.deploy import DeployService
from updater.services.version_manager import VersionManager
from updater.models.manifest import Manifest, ManifestModule
from updater.models.status import StageEnum


@pytest.mark.unit
class TestDeployService:
    """Test DeployService in isolation."""

    @pytest.fixture
    def mock_state_manager(self):
        """Mock StateManager."""
        manager = MagicMock()
        manager.update_status = MagicMock()
        return manager

    @pytest.fixture
    def mock_process_manager(self):
        """Mock ProcessManager."""
        manager = AsyncMock()
        manager.stop_service = AsyncMock()
        manager.start_service = AsyncMock()
        return manager

    @pytest.fixture
    def mock_version_manager(self):
        """Mock VersionManager."""
        manager = MagicMock()
        manager.create_version_dir = MagicMock(return_value=Path("/tmp/versions/v1.0.0"))
        manager.promote_version = MagicMock()
        return manager

    @pytest.fixture
    def deploy_service(self, mock_state_manager, mock_process_manager, mock_version_manager):
        """Create DeployService instance with mocked dependencies."""
        return DeployService(
            state_manager=mock_state_manager,
            process_manager=mock_process_manager,
            version_manager=mock_version_manager
        )

    @pytest.fixture
    def sample_manifest(self):
        """Create sample manifest for testing."""
        return Manifest(
            version="1.0.0",
            modules=[
                ManifestModule(
                    name="device-api",
                    src="device-api/main.py",
                    dst="/opt/device-api/main.py",
                    process_name="device-api.service"
                ),
                ManifestModule(
                    name="config",
                    src="config/settings.json",
                    dst="/etc/device/settings.json",
                    process_name=None
                )
            ]
        )

    @pytest.mark.asyncio
    async def test_extract_and_parse_manifest_success(self, deploy_service, sample_manifest, tmp_path):
        """Test successful manifest extraction and parsing."""
        # Arrange
        package_path = tmp_path / "test.zip"
        manifest_json = sample_manifest.model_dump_json()

        # Create ZIP with manifest
        with zipfile.ZipFile(package_path, 'w') as zf:
            zf.writestr("manifest.json", manifest_json)

        # Act
        result = await deploy_service._extract_and_parse_manifest(package_path)

        # Assert
        assert result.version == "1.0.0"
        assert len(result.modules) == 2
        assert result.modules[0].name == "device-api"

    @pytest.mark.asyncio
    async def test_extract_and_parse_manifest_missing(self, deploy_service, tmp_path):
        """Test manifest extraction fails when manifest.json is missing."""
        # Arrange
        package_path = tmp_path / "test.zip"

        # Create ZIP without manifest
        with zipfile.ZipFile(package_path, 'w') as zf:
            zf.writestr("other.txt", "content")

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="manifest.json not found"):
            await deploy_service._extract_and_parse_manifest(package_path)

    @pytest.mark.asyncio
    async def test_extract_and_parse_manifest_invalid_json(self, deploy_service, tmp_path):
        """Test manifest extraction fails with invalid JSON."""
        # Arrange
        package_path = tmp_path / "test.zip"

        # Create ZIP with invalid JSON
        with zipfile.ZipFile(package_path, 'w') as zf:
            zf.writestr("manifest.json", "{ invalid json }")

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid manifest JSON"):
            await deploy_service._extract_and_parse_manifest(package_path)

    @pytest.mark.asyncio
    async def test_extract_and_parse_manifest_bad_zip(self, deploy_service, tmp_path):
        """Test manifest extraction fails with corrupted ZIP."""
        # Arrange
        package_path = tmp_path / "test.zip"
        package_path.write_bytes(b"not a zip file")

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid ZIP package"):
            await deploy_service._extract_and_parse_manifest(package_path)

    @pytest.mark.asyncio
    async def test_backup_file_success(self, deploy_service, tmp_path):
        """Test successful file backup."""
        # Arrange
        test_file = tmp_path / "test.txt"
        test_file.write_text("original content")

        deploy_service.backup_dir = tmp_path / "backups"
        version = "1.0.0"

        # Act
        backup_path = await deploy_service._backup_file(test_file, version)

        # Assert
        assert backup_path.exists()
        assert backup_path.read_text() == "original content"
        assert version in backup_path.name
        assert ".bak" in backup_path.name

    @pytest.mark.asyncio
    async def test_backup_file_creates_backup_dir(self, deploy_service, tmp_path):
        """Test backup_file creates backup directory if it doesn't exist."""
        # Arrange
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        deploy_service.backup_dir = tmp_path / "new_backups"
        assert not deploy_service.backup_dir.exists()

        # Act
        backup_path = await deploy_service._backup_file(test_file, "1.0.0")

        # Assert
        assert deploy_service.backup_dir.exists()
        assert backup_path.exists()

    @pytest.mark.asyncio
    async def test_verify_deployment_success(self, deploy_service, sample_manifest, tmp_path):
        """Test successful deployment verification."""
        # Arrange - create all destination files
        for module in sample_manifest.modules:
            dst_path = Path(module.dst)
            # Use tmp_path for testing
            test_dst = tmp_path / dst_path.name
            test_dst.write_text("deployed content")
            module.dst = str(test_dst)

        # Act - should not raise
        await deploy_service._verify_deployment(sample_manifest)

    @pytest.mark.asyncio
    async def test_verify_deployment_missing_file(self, deploy_service, sample_manifest):
        """Test deployment verification fails when file is missing."""
        # Arrange - don't create the files
        # Act & Assert
        with pytest.raises(FileNotFoundError, match="does not exist"):
            await deploy_service._verify_deployment(sample_manifest)

    @pytest.mark.asyncio
    async def test_verify_deployment_not_a_file(self, deploy_service, sample_manifest, tmp_path):
        """Test deployment verification fails when destination is not a file."""
        # Arrange - create directory instead of file
        for idx, module in enumerate(sample_manifest.modules):
            test_dst = tmp_path / f"test_dir_{idx}"
            test_dst.mkdir()
            module.dst = str(test_dst)

        # Act & Assert
        with pytest.raises(ValueError, match="is not a file"):
            await deploy_service._verify_deployment(sample_manifest)

    @pytest.mark.asyncio
    async def test_stop_services_success(self, deploy_service, mock_process_manager):
        """Test successful service stopping."""
        # Arrange
        modules = [
            MagicMock(process_name="service1.service"),
            MagicMock(process_name="service2.service"),
        ]

        # Act
        await deploy_service._stop_services(modules)

        # Assert
        assert mock_process_manager.stop_service.call_count == 2
        mock_process_manager.stop_service.assert_any_call("service1.service")
        mock_process_manager.stop_service.assert_any_call("service2.service")

    @pytest.mark.asyncio
    async def test_stop_services_deduplicates(self, deploy_service, mock_process_manager):
        """Test stop_services deduplicates service names."""
        # Arrange - multiple modules with same service
        modules = [
            MagicMock(process_name="service1.service"),
            MagicMock(process_name="service1.service"),
            MagicMock(process_name="service2.service"),
        ]

        # Act
        await deploy_service._stop_services(modules)

        # Assert - should only stop each service once
        assert mock_process_manager.stop_service.call_count == 2

    @pytest.mark.asyncio
    async def test_stop_services_failure_raises(self, deploy_service, mock_process_manager):
        """Test stop_services raises RuntimeError on failure."""
        # Arrange
        modules = [MagicMock(process_name="service1.service")]
        mock_process_manager.stop_service.side_effect = RuntimeError("Stop failed")

        # Act & Assert
        with pytest.raises(RuntimeError, match="SERVICE_STOP_FAILED"):
            await deploy_service._stop_services(modules)

    @pytest.mark.asyncio
    async def test_start_services_success(self, deploy_service, mock_process_manager):
        """Test successful service starting."""
        # Arrange
        modules = [
            MagicMock(process_name="service1.service"),
            MagicMock(process_name="service2.service"),
        ]

        # Act
        await deploy_service._start_services(modules)

        # Assert
        assert mock_process_manager.start_service.call_count == 2
        mock_process_manager.start_service.assert_any_call("service1.service")
        mock_process_manager.start_service.assert_any_call("service2.service")

    @pytest.mark.asyncio
    async def test_start_services_failure_logs_but_continues(self, deploy_service, mock_process_manager):
        """Test start_services logs error but doesn't raise on failure."""
        # Arrange
        modules = [MagicMock(process_name="service1.service")]
        mock_process_manager.start_service.side_effect = RuntimeError("Start failed")

        # Act - should not raise
        await deploy_service._start_services(modules)

        # Assert - service start was attempted
        mock_process_manager.start_service.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_deployment_success(self, deploy_service, tmp_path):
        """Test successful rollback from backups."""
        # Arrange
        dst_file = tmp_path / "deployed.txt"
        dst_file.write_text("new content")

        backup_file = tmp_path / "deployed.txt.bak"
        backup_file.write_text("original content")

        deploy_service.backup_paths = {str(dst_file): backup_file}

        # Act
        await deploy_service._rollback_deployment()

        # Assert
        assert dst_file.read_text() == "original content"
        assert len(deploy_service.backup_paths) == 0

    @pytest.mark.asyncio
    async def test_rollback_deployment_no_backups(self, deploy_service):
        """Test rollback with no backups logs warning."""
        # Arrange
        deploy_service.backup_paths = {}

        # Act - should not raise
        await deploy_service._rollback_deployment()

        # Assert - backup_paths still empty
        assert len(deploy_service.backup_paths) == 0

    @pytest.mark.asyncio
    async def test_rollback_deployment_missing_backup(self, deploy_service, tmp_path):
        """Test rollback raises error when backup file is missing."""
        # Arrange
        dst_file = tmp_path / "deployed.txt"
        backup_file = tmp_path / "nonexistent.bak"

        deploy_service.backup_paths = {str(dst_file): backup_file}

        # Act & Assert
        with pytest.raises(RuntimeError, match="Rollback completed with .* errors"):
            await deploy_service._rollback_deployment()

    @pytest.mark.asyncio
    async def test_rollback_deployment_restore_failure(self, deploy_service, tmp_path):
        """Test rollback handles restore failures."""
        # Arrange
        dst_file = tmp_path / "deployed.txt"
        backup_file = tmp_path / "backup.bak"
        backup_file.write_text("backup content")

        deploy_service.backup_paths = {str(dst_file): backup_file}

        # Mock shutil.copy2 to fail
        with patch('shutil.copy2', side_effect=IOError("Copy failed")):
            # Act & Assert
            with pytest.raises(RuntimeError, match="Rollback completed with .* errors"):
                await deploy_service._rollback_deployment()

    @pytest.mark.asyncio
    async def test_deploy_module_success(self, deploy_service, tmp_path):
        """Test successful module deployment."""
        # Arrange
        package_path = tmp_path / "test.zip"
        module = ManifestModule(
            name="test-module",
            src="test.txt",
            dst=str(tmp_path / "deployed" / "test.txt"),
            process_name=None
        )

        # Create ZIP with source file
        with zipfile.ZipFile(package_path, 'w') as zf:
            zf.writestr("test.txt", "test content")

        # Act
        await deploy_service._deploy_module(package_path, module, "1.0.0")

        # Assert
        deployed_file = Path(module.dst)
        assert deployed_file.exists()
        assert deployed_file.read_text() == "test content"

    @pytest.mark.asyncio
    async def test_deploy_module_with_backup(self, deploy_service, tmp_path):
        """Test module deployment creates backup of existing file."""
        # Arrange
        dst_path = tmp_path / "deployed" / "test.txt"
        dst_path.parent.mkdir(parents=True)
        dst_path.write_text("old content")

        package_path = tmp_path / "test.zip"
        module = ManifestModule(
            name="test-module",
            src="test.txt",
            dst=str(dst_path),
            process_name=None
        )

        deploy_service.backup_dir = tmp_path / "backups"

        # Create ZIP with new content
        with zipfile.ZipFile(package_path, 'w') as zf:
            zf.writestr("test.txt", "new content")

        # Act
        await deploy_service._deploy_module(package_path, module, "1.0.0")

        # Assert
        assert dst_path.read_text() == "new content"
        assert str(dst_path) in deploy_service.backup_paths
        backup_path = deploy_service.backup_paths[str(dst_path)]
        assert backup_path.exists()
        assert backup_path.read_text() == "old content"

    @pytest.mark.asyncio
    async def test_deploy_module_source_not_found(self, deploy_service, tmp_path):
        """Test deploy_module raises error when source file not in ZIP."""
        # Arrange
        package_path = tmp_path / "test.zip"
        module = ManifestModule(
            name="test-module",
            src="missing.txt",
            dst=str(tmp_path / "deployed" / "test.txt"),
            process_name=None
        )

        # Create empty ZIP
        with zipfile.ZipFile(package_path, 'w') as zf:
            pass

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="not found in package"):
            await deploy_service._deploy_module(package_path, module, "1.0.0")

    @pytest.mark.asyncio
    async def test_deploy_module_relative_path_rejected(self, deploy_service, tmp_path):
        """Test deploy_module rejects relative destination paths."""
        # Arrange
        package_path = tmp_path / "test.zip"

        # Create ZIP
        with zipfile.ZipFile(package_path, 'w') as zf:
            zf.writestr("test.txt", "content")

        # Create module with relative path (bypassing Pydantic validation)
        module = MagicMock()
        module.name = "test-module"
        module.src = "test.txt"
        module.dst = "relative/path/test.txt"  # Relative path
        module.process_name = None

        # Act & Assert
        with pytest.raises(ValueError, match="must be absolute"):
            await deploy_service._deploy_module(package_path, module, "1.0.0")

    @pytest.mark.asyncio
    async def test_deploy_module_cleanup_on_error(self, deploy_service, tmp_path):
        """Test deploy_module cleans up temp file on error."""
        # Arrange
        dst_path = tmp_path / "deployed" / "test.txt"
        package_path = tmp_path / "test.zip"
        module = ManifestModule(
            name="test-module",
            src="test.txt",
            dst=str(dst_path),
            process_name=None
        )

        # Create ZIP
        with zipfile.ZipFile(package_path, 'w') as zf:
            zf.writestr("test.txt", "content")

        # Mock rename to fail
        with patch('pathlib.Path.rename', side_effect=IOError("Rename failed")):
            # Act & Assert
            with pytest.raises(IOError):
                await deploy_service._deploy_module(package_path, module, "1.0.0")

            # Assert temp file was cleaned up
            tmp_file = dst_path.parent / f"{dst_path.name}.tmp"
            assert not tmp_file.exists()

    @pytest.mark.asyncio
    async def test_deploy_package_version_mismatch(self, deploy_service, tmp_path):
        """Test deploy_package raises error on version mismatch."""
        # Arrange
        manifest = Manifest(
            version="1.0.0",
            modules=[
                ManifestModule(
                    name="test-module",
                    src="test.txt",
                    dst=str(tmp_path / "test.txt"),
                    process_name=None
                )
            ]
        )

        package_path = tmp_path / "test.zip"
        manifest_json = manifest.model_dump_json()

        with zipfile.ZipFile(package_path, 'w') as zf:
            zf.writestr("manifest.json", manifest_json)

        # Act & Assert - request version 2.0.0 but manifest has 1.0.0
        with pytest.raises(RuntimeError, match="Version mismatch"):
            await deploy_service.deploy_package(package_path, "2.0.0")

    @pytest.mark.asyncio
    async def test_deploy_package_triggers_rollback_on_failure(self, deploy_service, tmp_path):
        """Test deploy_package triggers rollback when deployment fails."""
        # Arrange
        manifest = Manifest(
            version="1.0.0",
            modules=[
                ManifestModule(
                    name="test-module",
                    src="test.txt",
                    dst=str(tmp_path / "test.txt"),
                    process_name=None
                )
            ]
        )

        package_path = tmp_path / "test.zip"
        manifest_json = manifest.model_dump_json()

        with zipfile.ZipFile(package_path, 'w') as zf:
            zf.writestr("manifest.json", manifest_json)
            zf.writestr("test.txt", "content")

        # Mock _verify_deployment to fail
        with patch.object(deploy_service, '_verify_deployment', side_effect=FileNotFoundError("File missing")):
            with patch.object(deploy_service, '_rollback_deployment', new_callable=AsyncMock) as mock_rollback:
                # Act & Assert
                with pytest.raises(RuntimeError) as exc_info:
                    await deploy_service.deploy_package(package_path, "1.0.0")

                # Assert error message contains both parts
                error_msg = str(exc_info.value)
                assert "DEPLOYMENT_FAILED" in error_msg
                assert "Rollback completed successfully" in error_msg

                # Assert rollback was called
                mock_rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_deploy_package_rollback_failure(self, deploy_service, tmp_path):
        """Test deploy_package reports both deployment and rollback failures."""
        # Arrange
        manifest = Manifest(
            version="1.0.0",
            modules=[
                ManifestModule(
                    name="test-module",
                    src="test.txt",
                    dst=str(tmp_path / "test.txt"),
                    process_name=None
                )
            ]
        )

        package_path = tmp_path / "test.zip"
        manifest_json = manifest.model_dump_json()

        with zipfile.ZipFile(package_path, 'w') as zf:
            zf.writestr("manifest.json", manifest_json)

        # Mock both deployment and rollback to fail
        with patch.object(deploy_service, '_verify_deployment', side_effect=FileNotFoundError("Deploy failed")):
            with patch.object(deploy_service, '_rollback_deployment', side_effect=RuntimeError("Rollback failed")):
                # Act & Assert
                with pytest.raises(RuntimeError) as exc_info:
                    await deploy_service.deploy_package(package_path, "1.0.0")

                # Assert error message contains both parts
                error_msg = str(exc_info.value)
                assert "DEPLOYMENT_FAILED" in error_msg
                assert "ROLLBACK_FAILED" in error_msg
                assert "Manual intervention may be required" in error_msg

    @pytest.mark.asyncio
    async def test_deploy_package_clears_backup_paths(self, deploy_service, sample_manifest, tmp_path):
        """Test deploy_package clears backup_paths at start."""
        # Arrange
        deploy_service.backup_paths = {"old": Path("old.bak")}

        package_path = tmp_path / "test.zip"
        manifest_json = sample_manifest.model_dump_json()

        with zipfile.ZipFile(package_path, 'w') as zf:
            zf.writestr("manifest.json", manifest_json)

        # Mock to fail early
        with patch.object(deploy_service, '_extract_and_parse_manifest', side_effect=ValueError("Parse error")):
            # Act
            try:
                await deploy_service.deploy_package(package_path, "1.0.0")
            except:
                pass

            # Assert - backup_paths was cleared
            # (It gets cleared at the start, then rollback clears it again)
            assert len(deploy_service.backup_paths) == 0

    @pytest.mark.asyncio
    async def test_deploy_package_updates_state_manager(self, deploy_service, mock_state_manager, sample_manifest, tmp_path):
        """Test deploy_package updates state manager throughout deployment."""
        # Arrange
        package_path = tmp_path / "test.zip"
        manifest_json = sample_manifest.model_dump_json()

        # Create complete package
        with zipfile.ZipFile(package_path, 'w') as zf:
            zf.writestr("manifest.json", manifest_json)
            zf.writestr("device-api/main.py", "content")
            zf.writestr("config/settings.json", "content")

        # Mock file operations to avoid actual file system changes
        with patch.object(deploy_service, '_deploy_module', new_callable=AsyncMock):
            with patch.object(deploy_service, '_verify_deployment', new_callable=AsyncMock):
                with patch.object(deploy_service, '_stop_services', new_callable=AsyncMock):
                    with patch.object(deploy_service, '_start_services', new_callable=AsyncMock):
                        # Act
                        await deploy_service.deploy_package(package_path, "1.0.0")

        # Assert - state manager was updated multiple times
        assert mock_state_manager.update_status.call_count >= 5

        # Check final status is SUCCESS
        final_call = mock_state_manager.update_status.call_args_list[-1]
        assert final_call[1]['stage'] == StageEnum.SUCCESS
        assert final_call[1]['progress'] == 100
