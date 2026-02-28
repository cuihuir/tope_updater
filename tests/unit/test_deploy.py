"""Unit tests for DeployService."""

import asyncio
import pytest
import json
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from updater.services.deploy import DeployService
from updater.models.manifest import Manifest, ManifestModule
from updater.models.status import StageEnum


@pytest.mark.unit
class TestDeployService:
    """Test DeployService in isolation."""

    @pytest.fixture
    def mock_state_manager(self):
        manager = MagicMock()
        manager.update_status = MagicMock()
        return manager

    @pytest.fixture
    def mock_process_manager(self):
        manager = AsyncMock()
        return manager

    @pytest.fixture
    def mock_version_manager(self):
        manager = MagicMock()
        manager.create_version_dir = MagicMock(return_value=Path("/tmp/versions/v1.0.0"))
        manager.promote_version = MagicMock()
        manager.rollback_to_previous = MagicMock(return_value="0.9.0")
        manager.rollback_to_factory = MagicMock(return_value="0.0.1")
        return manager

    @pytest.fixture
    def deploy_service(self, mock_state_manager, mock_process_manager, mock_version_manager):
        return DeployService(
            state_manager=mock_state_manager,
            process_manager=mock_process_manager,
            version_manager=mock_version_manager,
        )

    @pytest.fixture
    def sample_manifest(self):
        """使用 /opt/tope/ 路径的 manifest，避免测试中写入系统目录。"""
        return Manifest(
            version="1.0.0",
            modules=[
                ManifestModule(
                    name="device-api",
                    src="device-api/main.py",
                    dst="/opt/tope/services/device-api/main.py",
                    process_name="device-api.service",
                ),
                ManifestModule(
                    name="config",
                    src="config/settings.json",
                    dst="/opt/tope/config/settings.json",
                    process_name=None,
                ),
            ],
        )

    # --- _extract_and_parse_manifest ---

    @pytest.mark.asyncio
    async def test_extract_and_parse_manifest_success(self, deploy_service, sample_manifest, tmp_path):
        """成功从 ZIP 提取并解析 manifest。"""
        package_path = tmp_path / "test.zip"
        with zipfile.ZipFile(package_path, "w") as zf:
            zf.writestr("manifest.json", sample_manifest.model_dump_json())

        result = await deploy_service._extract_and_parse_manifest(package_path)

        assert result.version == "1.0.0"
        assert len(result.modules) == 2
        assert result.modules[0].name == "device-api"

    @pytest.mark.asyncio
    async def test_extract_and_parse_manifest_missing(self, deploy_service, tmp_path):
        """manifest.json 不存在时应抛出 FileNotFoundError。"""
        package_path = tmp_path / "test.zip"
        with zipfile.ZipFile(package_path, "w") as zf:
            zf.writestr("other.txt", "content")

        with pytest.raises(FileNotFoundError, match="manifest.json not found"):
            await deploy_service._extract_and_parse_manifest(package_path)

    @pytest.mark.asyncio
    async def test_extract_and_parse_manifest_invalid_json(self, deploy_service, tmp_path):
        """JSON 格式错误时应抛出 ValueError。"""
        package_path = tmp_path / "test.zip"
        with zipfile.ZipFile(package_path, "w") as zf:
            zf.writestr("manifest.json", "{ invalid json }")

        with pytest.raises(ValueError, match="Invalid manifest.json"):
            await deploy_service._extract_and_parse_manifest(package_path)

    @pytest.mark.asyncio
    async def test_extract_and_parse_manifest_bad_zip(self, deploy_service, tmp_path):
        """ZIP 文件损坏时应抛出 ValueError。"""
        package_path = tmp_path / "test.zip"
        package_path.write_bytes(b"not a zip file")

        with pytest.raises(ValueError, match="Invalid ZIP package"):
            await deploy_service._extract_and_parse_manifest(package_path)

    # --- _get_relative_destination ---

    def test_get_relative_destination_opt_tope(self, deploy_service):
        """/opt/tope/ 前缀应被剥离。"""
        result = deploy_service._get_relative_destination(Path("/opt/tope/services/device-api"))
        assert result == Path("services/device-api")

    def test_get_relative_destination_nested(self, deploy_service):
        """多级 /opt/tope/ 路径应正确剥离。"""
        result = deploy_service._get_relative_destination(Path("/opt/tope/bin/myapp"))
        assert result == Path("bin/myapp")

    def test_get_relative_destination_non_tope_path(self, deploy_service):
        """非 /opt/tope/ 路径应剥掉开头的 /。"""
        result = deploy_service._get_relative_destination(Path("/etc/myapp/config.json"))
        assert result == Path("etc/myapp/config.json")

    # --- _verify_deployment ---

    @pytest.mark.asyncio
    async def test_verify_deployment_success(self, deploy_service, sample_manifest, tmp_path):
        """所有文件存在时验证应通过。"""
        version_dir = tmp_path / "versions" / "v1.0.0"
        for module in sample_manifest.modules:
            dst_in_version = deploy_service._get_relative_destination(Path(module.dst))
            deployed = version_dir / dst_in_version
            deployed.parent.mkdir(parents=True, exist_ok=True)
            deployed.write_text("deployed content")

        # 不应抛出异常
        await deploy_service._verify_deployment(sample_manifest, version_dir)

    @pytest.mark.asyncio
    async def test_verify_deployment_missing_file(self, deploy_service, sample_manifest, tmp_path):
        """文件缺失时应抛出 FileNotFoundError。"""
        version_dir = tmp_path / "versions" / "v1.0.0"
        version_dir.mkdir(parents=True)

        with pytest.raises(FileNotFoundError, match="does not exist"):
            await deploy_service._verify_deployment(sample_manifest, version_dir)

    @pytest.mark.asyncio
    async def test_verify_deployment_not_a_file(self, deploy_service, sample_manifest, tmp_path):
        """目标路径是目录时应抛出 ValueError。"""
        version_dir = tmp_path / "versions" / "v1.0.0"
        for module in sample_manifest.modules:
            dst_in_version = deploy_service._get_relative_destination(Path(module.dst))
            deployed_dir = version_dir / dst_in_version
            deployed_dir.mkdir(parents=True, exist_ok=True)  # 创建目录而非文件

        with pytest.raises(ValueError, match="is not a file"):
            await deploy_service._verify_deployment(sample_manifest, version_dir)

    # --- _stop_services ---

    @pytest.mark.asyncio
    async def test_stop_services_success(self, deploy_service, mock_process_manager):
        """成功停止所有服务。"""
        modules = [
            MagicMock(process_name="service1.service"),
            MagicMock(process_name="service2.service"),
        ]

        await deploy_service._stop_services(modules)

        assert mock_process_manager.stop_service.call_count == 2
        mock_process_manager.stop_service.assert_any_call("service1.service")
        mock_process_manager.stop_service.assert_any_call("service2.service")

    @pytest.mark.asyncio
    async def test_stop_services_deduplicates(self, deploy_service, mock_process_manager):
        """相同服务名只停止一次。"""
        modules = [
            MagicMock(process_name="service1.service"),
            MagicMock(process_name="service1.service"),
            MagicMock(process_name="service2.service"),
        ]

        await deploy_service._stop_services(modules)

        assert mock_process_manager.stop_service.call_count == 2

    @pytest.mark.asyncio
    async def test_stop_services_failure_raises(self, deploy_service, mock_process_manager):
        """停止服务失败时应抛出 RuntimeError。"""
        modules = [MagicMock(process_name="service1.service")]
        mock_process_manager.stop_service.side_effect = RuntimeError("Stop failed")

        with pytest.raises(RuntimeError, match="SERVICE_STOP_FAILED"):
            await deploy_service._stop_services(modules)

    # --- _start_services ---

    @pytest.mark.asyncio
    async def test_start_services_success(self, deploy_service, mock_process_manager):
        """成功启动所有服务。"""
        modules = [
            MagicMock(process_name="service1.service"),
            MagicMock(process_name="service2.service"),
        ]

        await deploy_service._start_services(modules)

        assert mock_process_manager.start_service.call_count == 2
        mock_process_manager.start_service.assert_any_call("service1.service")
        mock_process_manager.start_service.assert_any_call("service2.service")

    @pytest.mark.asyncio
    async def test_start_services_failure_logs_but_continues(self, deploy_service, mock_process_manager):
        """启动失败时只记录日志，不抛出异常。"""
        modules = [MagicMock(process_name="service1.service")]
        mock_process_manager.start_service.side_effect = RuntimeError("Start failed")

        # 不应抛出异常
        await deploy_service._start_services(modules)

        mock_process_manager.start_service.assert_called_once()

    # --- rollback_to_previous ---

    @pytest.mark.asyncio
    async def test_rollback_to_previous_success(self, deploy_service, sample_manifest, mock_version_manager):
        """成功回滚到上一个版本。"""
        mock_version_manager.rollback_to_previous = MagicMock(return_value="0.9.0")

        with patch.object(deploy_service, "verify_services_healthy", new_callable=AsyncMock, return_value=True):
            result = await deploy_service.rollback_to_previous(sample_manifest)

        assert result == "0.9.0"
        mock_version_manager.rollback_to_previous.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_to_previous_no_previous_raises(self, deploy_service, sample_manifest, mock_version_manager):
        """没有上一个版本时应抛出 RuntimeError。"""
        mock_version_manager.rollback_to_previous = MagicMock(
            side_effect=RuntimeError("No previous version")
        )

        with pytest.raises(RuntimeError, match="ROLLBACK_LEVEL_1_FAILED"):
            await deploy_service.rollback_to_previous(sample_manifest)

    @pytest.mark.asyncio
    async def test_rollback_to_previous_unhealthy_raises(self, deploy_service, sample_manifest, mock_version_manager):
        """回滚后服务不健康时应抛出 RuntimeError。"""
        mock_version_manager.rollback_to_previous = MagicMock(return_value="0.9.0")

        with patch.object(deploy_service, "verify_services_healthy", new_callable=AsyncMock, return_value=False):
            with pytest.raises(RuntimeError, match="ROLLBACK_LEVEL_1_FAILED"):
                await deploy_service.rollback_to_previous(sample_manifest)

    # --- rollback_to_factory ---

    @pytest.mark.asyncio
    async def test_rollback_to_factory_success(self, deploy_service, sample_manifest, mock_version_manager):
        """成功回滚到出厂版本。"""
        mock_version_manager.rollback_to_factory = MagicMock(return_value="0.0.1")

        with patch.object(deploy_service, "verify_services_healthy", new_callable=AsyncMock, return_value=True):
            result = await deploy_service.rollback_to_factory(sample_manifest)

        assert result == "0.0.1"
        mock_version_manager.rollback_to_factory.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_to_factory_no_factory_raises(self, deploy_service, sample_manifest, mock_version_manager):
        """没有出厂版本时应抛出 RuntimeError。"""
        mock_version_manager.rollback_to_factory = MagicMock(
            side_effect=RuntimeError("No factory version")
        )

        with pytest.raises(RuntimeError, match="ROLLBACK_LEVEL_2_FAILED"):
            await deploy_service.rollback_to_factory(sample_manifest)

    # --- _deploy_module_to_version ---

    @pytest.mark.asyncio
    async def test_deploy_module_to_version_success(self, deploy_service, tmp_path):
        """成功将模块部署到版本目录。"""
        package_path = tmp_path / "test.zip"
        version_dir = tmp_path / "versions" / "v1.0.0"
        version_dir.mkdir(parents=True)

        module = ManifestModule(
            name="test-module",
            src="test.txt",
            dst="/opt/tope/bin/test.txt",
            process_name=None,
        )

        with zipfile.ZipFile(package_path, "w") as zf:
            zf.writestr("test.txt", "test content")

        await deploy_service._deploy_module_to_version(package_path, module, version_dir)

        deployed = version_dir / "bin" / "test.txt"
        assert deployed.exists()
        assert deployed.read_text() == "test content"

    @pytest.mark.asyncio
    async def test_deploy_module_to_version_source_not_found(self, deploy_service, tmp_path):
        """ZIP 中不含源文件时应抛出 FileNotFoundError。"""
        package_path = tmp_path / "test.zip"
        version_dir = tmp_path / "versions" / "v1.0.0"
        version_dir.mkdir(parents=True)

        module = ManifestModule(
            name="test-module",
            src="missing.txt",
            dst="/opt/tope/bin/missing.txt",
            process_name=None,
        )

        with zipfile.ZipFile(package_path, "w") as zf:
            pass  # 空 ZIP

        with pytest.raises(FileNotFoundError, match="not found in package"):
            await deploy_service._deploy_module_to_version(package_path, module, version_dir)

    @pytest.mark.asyncio
    async def test_deploy_module_to_version_cleanup_on_error(self, deploy_service, tmp_path):
        """部署出错时应清理临时文件。"""
        package_path = tmp_path / "test.zip"
        version_dir = tmp_path / "versions" / "v1.0.0"
        version_dir.mkdir(parents=True)

        module = ManifestModule(
            name="test-module",
            src="test.txt",
            dst="/opt/tope/bin/test.txt",
            process_name=None,
        )

        with zipfile.ZipFile(package_path, "w") as zf:
            zf.writestr("test.txt", "content")

        with patch("pathlib.Path.rename", side_effect=IOError("Rename failed")):
            with pytest.raises(IOError):
                await deploy_service._deploy_module_to_version(package_path, module, version_dir)

            tmp_file = version_dir / "bin" / "test.txt.tmp"
            assert not tmp_file.exists()

    # --- deploy_package ---

    @pytest.mark.asyncio
    async def test_deploy_package_version_mismatch(self, deploy_service, tmp_path):
        """manifest 版本与请求版本不符时应抛出 RuntimeError。"""
        manifest = Manifest(
            version="1.0.0",
            modules=[
                ManifestModule(
                    name="test-module",
                    src="test.txt",
                    dst="/opt/tope/bin/test.txt",
                    process_name=None,
                )
            ],
        )

        package_path = tmp_path / "test.zip"
        with zipfile.ZipFile(package_path, "w") as zf:
            zf.writestr("manifest.json", manifest.model_dump_json())

        with pytest.raises(RuntimeError, match="Version mismatch"):
            await deploy_service.deploy_package(package_path, "2.0.0")

    @pytest.mark.asyncio
    async def test_deploy_package_triggers_rollback_on_failure(
        self, deploy_service, tmp_path, mock_version_manager
    ):
        """部署失败时应触发两级回滚。"""
        manifest = Manifest(
            version="1.0.0",
            modules=[
                ManifestModule(
                    name="test-module",
                    src="test.txt",
                    dst="/opt/tope/bin/test.txt",
                    process_name=None,
                )
            ],
        )

        package_path = tmp_path / "test.zip"
        with zipfile.ZipFile(package_path, "w") as zf:
            zf.writestr("manifest.json", manifest.model_dump_json())
            zf.writestr("test.txt", "content")

        mock_version_manager.create_version_dir = MagicMock(return_value=tmp_path / "v1.0.0")

        with patch.object(deploy_service, "_verify_deployment", side_effect=FileNotFoundError("File missing")):
            with patch.object(
                deploy_service, "perform_two_level_rollback", new_callable=AsyncMock
            ) as mock_rollback:
                mock_rollback.return_value = "0.9.0"

                with pytest.raises(RuntimeError) as exc_info:
                    await deploy_service.deploy_package(package_path, "1.0.0")

                error_msg = str(exc_info.value)
                assert "DEPLOYMENT_FAILED" in error_msg
                assert "Rollback completed" in error_msg
                mock_rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_deploy_package_rollback_failure(
        self, deploy_service, tmp_path, mock_version_manager
    ):
        """两级回滚均失败时应上抛回滚错误。"""
        manifest = Manifest(
            version="1.0.0",
            modules=[
                ManifestModule(
                    name="test-module",
                    src="test.txt",
                    dst="/opt/tope/bin/test.txt",
                    process_name=None,
                )
            ],
        )

        package_path = tmp_path / "test.zip"
        with zipfile.ZipFile(package_path, "w") as zf:
            zf.writestr("manifest.json", manifest.model_dump_json())
            zf.writestr("test.txt", "content")

        mock_version_manager.create_version_dir = MagicMock(return_value=tmp_path / "v1.0.0")

        with patch.object(deploy_service, "_verify_deployment", side_effect=FileNotFoundError("Deploy failed")):
            with patch.object(
                deploy_service,
                "perform_two_level_rollback",
                new_callable=AsyncMock,
                side_effect=RuntimeError("ROLLBACK_LEVEL_2_FAILED: both levels failed"),
            ):
                with pytest.raises(RuntimeError) as exc_info:
                    await deploy_service.deploy_package(package_path, "1.0.0")

                assert "ROLLBACK_LEVEL_2_FAILED" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_deploy_package_cleans_up_version_dir_on_failure(
        self, deploy_service, tmp_path, mock_version_manager
    ):
        """部署失败时应清理版本目录。"""
        version_dir = tmp_path / "v1.0.0"
        version_dir.mkdir()
        mock_version_manager.create_version_dir = MagicMock(return_value=version_dir)

        package_path = tmp_path / "test.zip"
        with zipfile.ZipFile(package_path, "w") as zf:
            zf.writestr("manifest.json", "bad json")

        try:
            await deploy_service.deploy_package(package_path, "1.0.0")
        except Exception:
            pass

        assert not version_dir.exists()

    @pytest.mark.asyncio
    async def test_deploy_package_updates_state_manager(
        self, deploy_service, mock_state_manager, sample_manifest, tmp_path, mock_version_manager
    ):
        """deploy_package 全程应更新 state_manager。"""
        version_dir = tmp_path / "v1.0.0"
        version_dir.mkdir()
        mock_version_manager.create_version_dir = MagicMock(return_value=version_dir)

        package_path = tmp_path / "test.zip"
        with zipfile.ZipFile(package_path, "w") as zf:
            zf.writestr("manifest.json", sample_manifest.model_dump_json())
            zf.writestr("device-api/main.py", "content")
            zf.writestr("config/settings.json", "content")

        with patch.object(deploy_service, "_deploy_module_to_version", new_callable=AsyncMock):
            with patch.object(deploy_service, "_run_post_cmds", new_callable=AsyncMock):
                with patch.object(deploy_service, "_verify_deployment", new_callable=AsyncMock):
                    with patch.object(deploy_service, "_stop_services", new_callable=AsyncMock):
                        with patch.object(deploy_service, "_start_services", new_callable=AsyncMock):
                            await deploy_service.deploy_package(package_path, "1.0.0")

        assert mock_state_manager.update_status.call_count >= 4

        final_call = mock_state_manager.update_status.call_args_list[-1]
        assert final_call[1]["stage"] == StageEnum.SUCCESS
        assert final_call[1]["progress"] == 100


@pytest.mark.unit
class TestPostCmds:
    """Unit tests for post_cmds execution in DeployService."""

    @pytest.fixture
    def deploy_service(self):
        """Create DeployService with mocked dependencies."""
        return DeployService(
            state_manager=MagicMock(),
            process_manager=AsyncMock(),
            version_manager=MagicMock(),
        )

    @pytest.fixture
    def module_no_cmds(self):
        return ManifestModule(
            name="plain-file",
            src="bin/plain",
            dst="/opt/tope/bin/plain",
        )

    @pytest.fixture
    def module_with_cmds(self):
        return ManifestModule(
            name="config",
            src="etc/config.txt",
            dst="/etc/myapp/config.txt",
            post_cmds=["echo ok", "true"],
        )

    # --- ManifestModule schema tests ---

    def test_post_cmds_defaults_to_none(self, module_no_cmds):
        assert module_no_cmds.post_cmds is None

    def test_post_cmds_accepts_list_of_strings(self, module_with_cmds):
        assert module_with_cmds.post_cmds == ["echo ok", "true"]

    def test_post_cmds_accepts_empty_list(self):
        m = ManifestModule(
            name="m", src="a/b", dst="/opt/tope/b", post_cmds=[]
        )
        assert m.post_cmds == []

    # --- _run_post_cmds tests ---

    @pytest.mark.asyncio
    async def test_run_post_cmds_skips_when_none(self, deploy_service, module_no_cmds):
        """post_cmds 为 None 时不执行任何操作。"""
        await deploy_service._run_post_cmds(module_no_cmds)

    @pytest.mark.asyncio
    async def test_run_post_cmds_skips_when_empty(self, deploy_service):
        module = ManifestModule(
            name="m", src="a/b", dst="/opt/tope/b", post_cmds=[]
        )
        await deploy_service._run_post_cmds(module)

    @pytest.mark.asyncio
    async def test_run_post_cmds_success(self, deploy_service, tmp_path):
        """命令成功执行不抛异常。"""
        sentinel = tmp_path / "post_cmd_ran.txt"
        module = ManifestModule(
            name="m",
            src="a/b",
            dst="/opt/tope/b",
            post_cmds=[f"touch {sentinel}"],
        )
        await deploy_service._run_post_cmds(module)
        assert sentinel.exists()

    @pytest.mark.asyncio
    async def test_run_post_cmds_multiple_in_order(self, deploy_service, tmp_path):
        """多条命令按声明顺序依次执行。"""
        log = tmp_path / "order.log"
        module = ManifestModule(
            name="m",
            src="a/b",
            dst="/opt/tope/b",
            post_cmds=[
                f"echo first >> {log}",
                f"echo second >> {log}",
                f"echo third >> {log}",
            ],
        )
        await deploy_service._run_post_cmds(module)
        lines = log.read_text().splitlines()
        assert lines == ["first", "second", "third"]

    @pytest.mark.asyncio
    async def test_run_post_cmds_failure_raises(self, deploy_service):
        """命令返回非零退出码时应抛出 POST_CMD_FAILED。"""
        module = ManifestModule(
            name="m",
            src="a/b",
            dst="/opt/tope/b",
            post_cmds=["false"],
        )
        with pytest.raises(RuntimeError, match="POST_CMD_FAILED"):
            await deploy_service._run_post_cmds(module)

    @pytest.mark.asyncio
    async def test_run_post_cmds_failure_stops_at_first_error(self, deploy_service, tmp_path):
        """第一条命令失败后，后续命令不再执行。"""
        sentinel = tmp_path / "should_not_exist.txt"
        module = ManifestModule(
            name="m",
            src="a/b",
            dst="/opt/tope/b",
            post_cmds=["false", f"touch {sentinel}"],
        )
        with pytest.raises(RuntimeError, match="POST_CMD_FAILED"):
            await deploy_service._run_post_cmds(module)
        assert not sentinel.exists()

    @pytest.mark.asyncio
    async def test_run_post_cmds_timeout_raises(self, deploy_service):
        """命令超时应抛出 POST_CMD_TIMEOUT。"""
        module = ManifestModule(
            name="m",
            src="a/b",
            dst="/opt/tope/b",
            post_cmds=["sleep 100"],
        )

        mock_communicate = AsyncMock(return_value=(b"", b""))
        mock_proc = MagicMock()
        mock_proc.communicate = mock_communicate
        mock_proc.kill = MagicMock()

        async def _fake_wait_for(coro, timeout=None):
            # 关闭协程避免 RuntimeWarning（coroutine never awaited）
            if hasattr(coro, "close"):
                coro.close()
            raise asyncio.TimeoutError()

        with patch(
            "updater.services.deploy.asyncio.create_subprocess_shell",
            new_callable=AsyncMock,
            return_value=mock_proc,
        ):
            with patch("updater.services.deploy.asyncio.wait_for", side_effect=_fake_wait_for):
                with pytest.raises(RuntimeError, match="POST_CMD_TIMEOUT"):
                    await deploy_service._run_post_cmds(module)

        mock_proc.kill.assert_called_once()
