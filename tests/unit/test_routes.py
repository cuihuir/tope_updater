"""Integration tests for API routes (routes.py + main.py)."""

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
from fastapi.testclient import TestClient

from updater.models.status import StageEnum
from updater.api.models import ProgressData
from updater.services.state_manager import StateManager
from updater.services.reporter import ReportService


# -----------------------------------------------------------------------
# 辅助工厂函数
# -----------------------------------------------------------------------

def _make_status(stage=StageEnum.IDLE, progress=0, message="Idle", error=None):
    """构造一个 ProgressData 对象（routes 返回时需通过 Pydantic 验证）。"""
    return ProgressData(stage=stage, progress=progress, message=message, error=error)


def _make_persistent_state(version="1.0.0", expired=False):
    """构造一个 MagicMock 持久化状态对象。"""
    ps = MagicMock()
    ps.version = version
    ps.package_name = f"test-update-{version}.zip"
    ps.package_size = 1000
    ps.bytes_downloaded = 1000
    ps.stage = StageEnum.TO_INSTALL
    ps.is_package_expired.return_value = expired
    return ps


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_singletons():
    """每个测试前重置所有单例，避免状态污染。"""
    StateManager._instance = None
    ReportService._instance = None
    yield
    StateManager._instance = None
    ReportService._instance = None


@pytest.fixture
def mock_workflows():
    """将后台工作流替换成 no-op async 函数，避免测试中发起真实网络/部署操作。"""
    async def noop(*args, **kwargs):
        pass

    with patch("updater.api.routes._download_workflow", noop):
        with patch("updater.api.routes._update_workflow", noop):
            yield


@pytest.fixture
def client(mock_workflows):
    """创建 TestClient（跳过 lifespan 以避免文件系统副作用）。"""
    # 直接使用 app，但 mock 掉 lifespan 相关的副作用
    from updater.main import app

    with patch("updater.main.setup_logger") as mock_log:
        mock_log.return_value = MagicMock()
        with patch("updater.main.StateManager") as MockSM:
            mock_sm = MagicMock()
            mock_sm.load_state.return_value = None
            MockSM.return_value = mock_sm

            with TestClient(app, raise_server_exceptions=True) as c:
                yield c


# -----------------------------------------------------------------------
# GET /api/v1.0/progress
# -----------------------------------------------------------------------

@pytest.mark.unit
class TestGetProgress:
    """GET /api/v1.0/progress"""

    def test_idle_state_returns_200_code(self, client):
        """空闲状态应返回 code=200。"""
        with patch("updater.api.routes.StateManager") as MockSM:
            MockSM.return_value.get_status.return_value = _make_status(StageEnum.IDLE)

            resp = client.get("/api/v1.0/progress")

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["msg"] == "success"

    def test_failed_state_returns_code_500(self, client):
        """失败状态应返回 code=500。"""
        with patch("updater.api.routes.StateManager") as MockSM:
            MockSM.return_value.get_status.return_value = _make_status(
                StageEnum.FAILED, error="MD5_MISMATCH"
            )

            resp = client.get("/api/v1.0/progress")

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 500
        assert "MD5_MISMATCH" in body["msg"]
        assert body["stage"] == "failed"

    def test_failed_state_no_error_field(self, client):
        """失败状态但无 error 字段时，msg 应为通用错误消息。"""
        with patch("updater.api.routes.StateManager") as MockSM:
            MockSM.return_value.get_status.return_value = _make_status(
                StageEnum.FAILED, error=None
            )

            resp = client.get("/api/v1.0/progress")

        body = resp.json()
        assert body["code"] == 500
        assert body["msg"] == "Update failed"

    def test_downloading_state_returns_code_200(self, client):
        """下载中状态应返回 code=200。"""
        with patch("updater.api.routes.StateManager") as MockSM:
            MockSM.return_value.get_status.return_value = _make_status(
                StageEnum.DOWNLOADING, progress=45, message="Downloading..."
            )

            resp = client.get("/api/v1.0/progress")

        body = resp.json()
        assert body["code"] == 200


# -----------------------------------------------------------------------
# POST /api/v1.0/download
# -----------------------------------------------------------------------

@pytest.mark.unit
class TestPostDownload:
    """POST /api/v1.0/download"""

    _valid_payload = {
        "version": "1.0.0",
        "package_url": "http://localhost:8888/pkg.zip",
        "package_name": "pkg.zip",
        "package_size": 1024,
        "package_md5": "d41d8cd98f00b204e9800998ecf8427e",
    }

    def test_idle_state_starts_download(self, client):
        """空闲状态下应接受下载请求，返回 code=200。"""
        with patch("updater.api.routes.StateManager") as MockSM:
            MockSM.return_value.get_status.return_value = _make_status(StageEnum.IDLE)
            MockSM.return_value.get_persistent_state.return_value = None

            resp = client.post("/api/v1.0/download", json=self._valid_payload)

        assert resp.status_code == 200
        assert resp.json()["code"] == 200

    def test_already_downloading_returns_409(self, client):
        """下载进行中时再次请求应返回 code=409。"""
        with patch("updater.api.routes.StateManager") as MockSM:
            MockSM.return_value.get_status.return_value = _make_status(
                StageEnum.DOWNLOADING
            )
            MockSM.return_value.get_persistent_state.return_value = None

            resp = client.post("/api/v1.0/download", json=self._valid_payload)

        assert resp.status_code == 200
        assert resp.json()["code"] == 409

    def test_installing_state_returns_409(self, client):
        """安装进行中时下载请求应返回 code=409。"""
        with patch("updater.api.routes.StateManager") as MockSM:
            MockSM.return_value.get_status.return_value = _make_status(
                StageEnum.INSTALLING
            )
            MockSM.return_value.get_persistent_state.return_value = None

            resp = client.post("/api/v1.0/download", json=self._valid_payload)

        assert resp.json()["code"] == 409

    def test_expired_package_returns_410(self, client):
        """包已过期时应返回 code=410。"""
        with patch("updater.api.routes.StateManager") as MockSM:
            MockSM.return_value.get_status.return_value = _make_status(StageEnum.IDLE)
            MockSM.return_value.get_persistent_state.return_value = _make_persistent_state(
                expired=True
            )

            resp = client.post("/api/v1.0/download", json=self._valid_payload)

        assert resp.json()["code"] == 410

    def test_success_state_allows_download(self, client):
        """success 状态下应允许新的下载请求。"""
        with patch("updater.api.routes.StateManager") as MockSM:
            MockSM.return_value.get_status.return_value = _make_status(StageEnum.SUCCESS)
            MockSM.return_value.get_persistent_state.return_value = None

            resp = client.post("/api/v1.0/download", json=self._valid_payload)

        assert resp.json()["code"] == 200

    def test_failed_state_allows_download(self, client):
        """failed 状态下应允许重新下载。"""
        with patch("updater.api.routes.StateManager") as MockSM:
            MockSM.return_value.get_status.return_value = _make_status(StageEnum.FAILED)
            MockSM.return_value.get_persistent_state.return_value = None

            resp = client.post("/api/v1.0/download", json=self._valid_payload)

        assert resp.json()["code"] == 200


# -----------------------------------------------------------------------
# POST /api/v1.0/update
# -----------------------------------------------------------------------

@pytest.mark.unit
class TestPostUpdate:
    """POST /api/v1.0/update"""

    _valid_payload = {"version": "1.0.0"}

    def test_to_install_state_starts_update(self, client):
        """toInstall 状态下应接受安装请求。"""
        with patch("updater.api.routes.StateManager") as MockSM:
            with patch("updater.api.routes.GUILauncher") as MockGUI:
                MockGUI.return_value.start.return_value = True
                MockSM.return_value.get_status.return_value = _make_status(
                    StageEnum.TO_INSTALL
                )
                MockSM.return_value.get_persistent_state.return_value = (
                    _make_persistent_state("1.0.0")
                )

                resp = client.post("/api/v1.0/update", json=self._valid_payload)

        assert resp.status_code == 200
        assert resp.json()["code"] == 200

    def test_downloading_state_returns_409(self, client):
        """下载进行中时安装请求应返回 code=409。"""
        with patch("updater.api.routes.StateManager") as MockSM:
            MockSM.return_value.get_status.return_value = _make_status(
                StageEnum.DOWNLOADING
            )
            MockSM.return_value.get_persistent_state.return_value = None

            resp = client.post("/api/v1.0/update", json=self._valid_payload)

        assert resp.json()["code"] == 409

    def test_installing_state_returns_409(self, client):
        """安装进行中时再次请求应返回 code=409。"""
        with patch("updater.api.routes.StateManager") as MockSM:
            MockSM.return_value.get_status.return_value = _make_status(
                StageEnum.INSTALLING
            )
            MockSM.return_value.get_persistent_state.return_value = None

            resp = client.post("/api/v1.0/update", json=self._valid_payload)

        assert resp.json()["code"] == 409

    def test_package_not_found_returns_404(self, client):
        """persistent_state 不存在时应返回 code=404。"""
        with patch("updater.api.routes.StateManager") as MockSM:
            MockSM.return_value.get_status.return_value = _make_status(
                StageEnum.TO_INSTALL
            )
            MockSM.return_value.get_persistent_state.return_value = None

            resp = client.post("/api/v1.0/update", json=self._valid_payload)

        assert resp.json()["code"] == 404

    def test_version_mismatch_returns_404(self, client):
        """版本号不匹配时应返回 code=404。"""
        with patch("updater.api.routes.StateManager") as MockSM:
            MockSM.return_value.get_status.return_value = _make_status(
                StageEnum.TO_INSTALL
            )
            # persistent state 版本不同
            MockSM.return_value.get_persistent_state.return_value = (
                _make_persistent_state("2.0.0")
            )

            resp = client.post("/api/v1.0/update", json=self._valid_payload)

        assert resp.json()["code"] == 404

    def test_expired_package_returns_410(self, client):
        """包已过期时安装应返回 code=410。"""
        with patch("updater.api.routes.StateManager") as MockSM:
            MockSM.return_value.get_status.return_value = _make_status(
                StageEnum.TO_INSTALL
            )
            MockSM.return_value.get_persistent_state.return_value = (
                _make_persistent_state("1.0.0", expired=True)
            )

            resp = client.post("/api/v1.0/update", json=self._valid_payload)

        assert resp.json()["code"] == 410

    def test_gui_start_failure_still_proceeds(self, client):
        """GUI 启动失败时更新仍应继续（code=200）。"""
        with patch("updater.api.routes.StateManager") as MockSM:
            with patch("updater.api.routes.GUILauncher") as MockGUI:
                MockGUI.return_value.start.return_value = False  # GUI 启动失败
                MockSM.return_value.get_status.return_value = _make_status(
                    StageEnum.TO_INSTALL
                )
                MockSM.return_value.get_persistent_state.return_value = (
                    _make_persistent_state("1.0.0")
                )

                resp = client.post("/api/v1.0/update", json=self._valid_payload)

        assert resp.json()["code"] == 200


# -----------------------------------------------------------------------
# GET / (健康检查，定义在 main.py)
# -----------------------------------------------------------------------

@pytest.mark.unit
class TestHealthCheck:
    """GET / - 健康检查接口"""

    def test_root_returns_ok(self, client):
        """健康检查应返回 status=ok。"""
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["service"] == "tope-updater"

    def test_root_returns_features(self, client):
        """健康检查应包含 features 字段。"""
        resp = client.get("/")
        body = resp.json()
        assert "features" in body
        assert len(body["features"]) > 0


# -----------------------------------------------------------------------
# 后台工作流函数直接测试
# -----------------------------------------------------------------------

@pytest.mark.unit
class TestDownloadWorkflow:
    """直接测试 _download_workflow 后台任务函数。"""

    @pytest.mark.asyncio
    async def test_download_workflow_success(self):
        """_download_workflow 成功路径：调用 download_service.download_package。"""
        from updater.api.routes import _download_workflow

        with patch("updater.api.routes.ReportService") as MockRS:
            with patch("updater.api.routes.DownloadService") as MockDS:
                mock_ds = MagicMock()
                mock_ds.download_package = AsyncMock(return_value=None)
                MockDS.return_value = mock_ds

                await _download_workflow(
                    version="1.0.0",
                    package_url="http://example.com/pkg.zip",
                    package_name="pkg.zip",
                    package_size=1024,
                    package_md5="abc123",
                )

        mock_ds.download_package.assert_called_once_with(
            version="1.0.0",
            package_url="http://example.com/pkg.zip",
            package_name="pkg.zip",
            package_size=1024,
            package_md5="abc123",
        )

    @pytest.mark.asyncio
    async def test_download_workflow_exception_is_swallowed(self):
        """_download_workflow 内部异常应被吞掉，不向上传播。"""
        from updater.api.routes import _download_workflow

        with patch("updater.api.routes.ReportService"):
            with patch("updater.api.routes.DownloadService") as MockDS:
                mock_ds = MagicMock()
                mock_ds.download_package = AsyncMock(side_effect=RuntimeError("network error"))
                MockDS.return_value = mock_ds

                # 不应抛出异常
                await _download_workflow(
                    version="1.0.0",
                    package_url="http://example.com/pkg.zip",
                    package_name="pkg.zip",
                    package_size=1024,
                    package_md5="abc123",
                )


@pytest.mark.unit
class TestUpdateWorkflow:
    """直接测试 _update_workflow 后台任务函数。"""

    @pytest.fixture(autouse=True)
    def reset_singletons(self):
        StateManager._instance = None
        ReportService._instance = None
        yield
        StateManager._instance = None
        ReportService._instance = None

    @pytest.mark.asyncio
    async def test_update_workflow_no_persistent_state(self):
        """_update_workflow 在没有持久化状态时应设置 FAILED。"""
        from updater.api.routes import _update_workflow

        mock_gui = MagicMock()

        with patch("updater.api.routes.StateManager") as MockSM:
            with patch("updater.api.routes.ReportService"):
                with patch("updater.api.routes.DeployService"):
                    mock_sm = MagicMock()
                    mock_sm.get_persistent_state.return_value = None
                    MockSM.return_value = mock_sm

                    await _update_workflow("1.0.0", mock_gui)

        mock_sm.update_status.assert_called_once()
        call_kwargs = mock_sm.update_status.call_args[1]
        assert call_kwargs["stage"] == StageEnum.FAILED
        mock_gui.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_workflow_package_file_missing(self, tmp_path):
        """_update_workflow 在包文件不存在时应设置 FAILED。"""
        from updater.api.routes import _update_workflow

        mock_gui = MagicMock()

        with patch("updater.api.routes.StateManager") as MockSM:
            with patch("updater.api.routes.ReportService"):
                with patch("updater.api.routes.DeployService"):
                    mock_sm = MagicMock()
                    persistent = MagicMock()
                    persistent.package_name = "missing.zip"
                    mock_sm.get_persistent_state.return_value = persistent
                    MockSM.return_value = mock_sm

                    # 临时目录不含该文件
                    with patch("updater.api.routes.Path") as MockPath:
                        mock_path = MagicMock()
                        mock_path.__truediv__ = MagicMock(
                            return_value=MagicMock(exists=MagicMock(return_value=False))
                        )
                        MockPath.return_value = mock_path

                        await _update_workflow("1.0.0", mock_gui)

        mock_sm.update_status.assert_called_once()
        call_kwargs = mock_sm.update_status.call_args[1]
        assert call_kwargs["stage"] == StageEnum.FAILED
        mock_gui.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_workflow_deploy_failure(self, tmp_path):
        """_update_workflow 部署失败时应设置 FAILED 状态。"""
        from updater.api.routes import _update_workflow

        mock_gui = MagicMock()
        # 创建假包文件
        pkg_file = tmp_path / "pkg.zip"
        pkg_file.write_bytes(b"fake")

        with patch("updater.api.routes.StateManager") as MockSM:
            with patch("updater.api.routes.ReportService"):
                with patch("updater.api.routes.DeployService") as MockDS:
                    with patch("updater.api.routes.Path") as MockPath:
                        mock_sm = MagicMock()
                        persistent = MagicMock()
                        persistent.package_name = "pkg.zip"
                        mock_sm.get_persistent_state.return_value = persistent
                        MockSM.return_value = mock_sm

                        # 模拟文件存在
                        mock_path_instance = MagicMock()
                        mock_path_instance.exists.return_value = True
                        MockPath.return_value.__truediv__ = MagicMock(
                            return_value=mock_path_instance
                        )

                        mock_ds = MagicMock()
                        mock_ds.deploy_package = AsyncMock(
                            side_effect=RuntimeError("deploy failed")
                        )
                        MockDS.return_value = mock_ds

                        await _update_workflow("1.0.0", mock_gui)

        mock_sm.update_status.assert_called_once()
        call_kwargs = mock_sm.update_status.call_args[1]
        assert call_kwargs["stage"] == StageEnum.FAILED
        assert "UPDATE_FAILED" in call_kwargs["error"]
        mock_gui.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_workflow_success_deletes_state_and_resets(self, tmp_path):
        """_update_workflow 成功时应删除状态并等待后重置。"""
        from updater.api.routes import _update_workflow

        mock_gui = MagicMock()
        pkg_file = tmp_path / "pkg.zip"
        pkg_file.write_bytes(b"fake")

        with patch("updater.api.routes.StateManager") as MockSM:
            with patch("updater.api.routes.ReportService"):
                with patch("updater.api.routes.DeployService") as MockDS:
                    with patch("updater.api.routes.Path") as MockPath:
                        with patch("updater.api.routes.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                            mock_sm = MagicMock()
                            persistent = MagicMock()
                            persistent.package_name = "pkg.zip"
                            mock_sm.get_persistent_state.return_value = persistent
                            MockSM.return_value = mock_sm

                            mock_path_instance = MagicMock()
                            mock_path_instance.exists.return_value = True
                            MockPath.return_value.__truediv__ = MagicMock(
                                return_value=mock_path_instance
                            )

                            mock_ds = MagicMock()
                            mock_ds.deploy_package = AsyncMock(return_value=None)
                            MockDS.return_value = mock_ds

                            await _update_workflow("1.0.0", mock_gui)

        mock_sm.delete_state.assert_called_once()
        mock_sleep.assert_called_once_with(65)
        mock_sm.reset.assert_called_once()
        mock_gui.stop.assert_called_once()
