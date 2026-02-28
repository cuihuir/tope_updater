"""Unit tests for main.py lifespan startup logic."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

from updater.models.status import StageEnum
from updater.services.state_manager import StateManager
from updater.services.reporter import ReportService


# -----------------------------------------------------------------------
# 辅助工厂
# -----------------------------------------------------------------------

def _make_state(
    version="1.0.0",
    stage=StageEnum.TO_INSTALL,
    bytes_downloaded=500,
    package_size=1000,
    package_name="pkg.zip",
    expired=False,
):
    """构造 mock 持久化状态对象。"""
    s = MagicMock()
    s.version = version
    s.stage = stage
    s.bytes_downloaded = bytes_downloaded
    s.package_size = package_size
    s.package_name = package_name
    s.is_package_expired.return_value = expired
    return s


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_singletons():
    StateManager._instance = None
    ReportService._instance = None
    yield
    StateManager._instance = None
    ReportService._instance = None


def _make_client(load_state_return):
    """创建 TestClient，以指定的 load_state 返回值运行 lifespan。"""
    from updater.main import app

    mock_sm = MagicMock()
    mock_sm.load_state.return_value = load_state_return

    with patch("updater.main.setup_logger") as mock_log:
        mock_log.return_value = MagicMock()
        with patch("updater.main.StateManager", return_value=mock_sm):
            with patch("updater.main.Path") as MockPath:
                # 让 Path(...).mkdir(...) 不操作真实文件系统
                MockPath.return_value.mkdir = MagicMock()
                with TestClient(app, raise_server_exceptions=True) as c:
                    yield c, mock_sm


# -----------------------------------------------------------------------
# lifespan: 无持久化状态
# -----------------------------------------------------------------------

@pytest.mark.unit
class TestLifespanNoState:
    """lifespan 启动：无持久化状态时的行为。"""

    def test_no_state_starts_fresh(self):
        """无 persistent state 时服务应正常启动。"""
        for c, mock_sm in _make_client(load_state_return=None):
            resp = c.get("/")
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"


# -----------------------------------------------------------------------
# lifespan: 包已过期
# -----------------------------------------------------------------------

@pytest.mark.unit
class TestLifespanExpiredPackage:
    """lifespan 启动：包已过期时应清理并重置。"""

    def test_expired_package_cleans_up(self):
        """过期包应被删除，状态应重置。"""
        state = _make_state(expired=True)

        for c, mock_sm in _make_client(load_state_return=state):
            resp = c.get("/")
            assert resp.status_code == 200

        mock_sm.delete_state.assert_called_once()
        mock_sm.reset.assert_called_once()


# -----------------------------------------------------------------------
# lifespan: 上次操作失败（FAILED 状态）
# -----------------------------------------------------------------------

@pytest.mark.unit
class TestLifespanFailedState:
    """lifespan 启动：上次操作失败时应更新状态保留错误信息。"""

    def test_failed_state_updates_status(self):
        """FAILED 状态应调用 update_status 设置 FAILED 阶段。"""
        state = _make_state(stage=StageEnum.FAILED, expired=False)

        for c, mock_sm in _make_client(load_state_return=state):
            resp = c.get("/")
            assert resp.status_code == 200

        mock_sm.update_status.assert_called_once()
        call_kwargs = mock_sm.update_status.call_args[1]
        assert call_kwargs["stage"] == StageEnum.FAILED


# -----------------------------------------------------------------------
# lifespan: 下载被中断（DOWNLOADING 状态）
# -----------------------------------------------------------------------

@pytest.mark.unit
class TestLifespanDownloadingInterrupted:
    """lifespan 启动：下载被中断时应清理并重置。"""

    def test_downloading_interrupted_cleans_up(self):
        """中断的下载应被清理，状态重置。"""
        state = _make_state(stage=StageEnum.DOWNLOADING, expired=False)

        for c, mock_sm in _make_client(load_state_return=state):
            resp = c.get("/")
            assert resp.status_code == 200

        mock_sm.delete_state.assert_called_once()
        mock_sm.reset.assert_called_once()


# -----------------------------------------------------------------------
# lifespan: 验证被中断（VERIFYING 状态）
# -----------------------------------------------------------------------

@pytest.mark.unit
class TestLifespanVerifyingInterrupted:
    """lifespan 启动：验证被中断时应清理并重置。"""

    def test_verifying_interrupted_cleans_up(self):
        """中断的验证应被清理，状态重置。"""
        state = _make_state(stage=StageEnum.VERIFYING, expired=False)

        for c, mock_sm in _make_client(load_state_return=state):
            resp = c.get("/")
            assert resp.status_code == 200

        mock_sm.delete_state.assert_called_once()
        mock_sm.reset.assert_called_once()


# -----------------------------------------------------------------------
# lifespan: 损坏状态（bytes_downloaded > package_size）
# -----------------------------------------------------------------------

@pytest.mark.unit
class TestLifespanCorruptedState:
    """lifespan 启动：损坏状态（字节数超出包大小）应清理并重置。"""

    def test_corrupted_state_cleans_up(self):
        """损坏状态应被清理，状态重置。"""
        state = _make_state(
            stage=StageEnum.TO_INSTALL,
            bytes_downloaded=9999,
            package_size=1000,
            expired=False,
        )

        for c, mock_sm in _make_client(load_state_return=state):
            resp = c.get("/")
            assert resp.status_code == 200

        mock_sm.delete_state.assert_called_once()
        mock_sm.reset.assert_called_once()


# -----------------------------------------------------------------------
# lifespan: 有效状态恢复（TO_INSTALL，无损坏）
# -----------------------------------------------------------------------

@pytest.mark.unit
class TestLifespanValidStateResume:
    """lifespan 启动：有效持久化状态应恢复（调用 update_status）。"""

    def test_valid_state_resumes(self):
        """有效状态下应调用 update_status 恢复阶段。"""
        state = _make_state(
            stage=StageEnum.TO_INSTALL,
            bytes_downloaded=500,
            package_size=1000,
            expired=False,
        )

        for c, mock_sm in _make_client(load_state_return=state):
            resp = c.get("/")
            assert resp.status_code == 200

        mock_sm.update_status.assert_called_once()
        call_kwargs = mock_sm.update_status.call_args[1]
        assert call_kwargs["stage"] == StageEnum.TO_INSTALL


# -----------------------------------------------------------------------
# main() 函数
# -----------------------------------------------------------------------

@pytest.mark.unit
class TestMainFunction:
    """测试 main() 入口函数。"""

    def test_main_calls_uvicorn_run(self):
        """main() 应调用 uvicorn.run。"""
        from updater.main import main

        with patch("updater.main.uvicorn.run") as mock_run:
            main()

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[1]["port"] == 12315
        assert call_args[1]["host"] == "0.0.0.0"
