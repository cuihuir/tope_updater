"""
GUI Launcher

管理 GUI 子进程生命周期
"""

import subprocess
import sys
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class GUILauncher:
    """
    GUI 启动器

    管理 GUI 子进程的启动、停止和状态检查
    """

    def __init__(self):
        """初始化 GUI 启动器"""
        self.process: Optional[subprocess.Popen] = None

    def start(self) -> bool:
        """
        启动 GUI 子进程

        Returns:
            成功返回 True，否则返回 False
        """
        if self.process is not None:
            logger.warning("GUI process already running")
            return False

        try:
            # 启动 GUI 作为子进程
            self.process = subprocess.Popen(
                [sys.executable, "-m", "updater.gui.progress_window"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=Path(__file__).parent.parent.parent
            )

            logger.info(f"GUI process started (PID: {self.process.pid})")
            return True

        except Exception as e:
            logger.error(f"Failed to start GUI: {e}")
            self.process = None
            return False

    def stop(self, timeout: int = 5) -> bool:
        """
        停止 GUI 子进程

        Args:
            timeout: 等待优雅终止的秒数

        Returns:
            成功返回 True，否则返回 False
        """
        if self.process is None:
            logger.warning("No GUI process to stop")
            return False

        try:
            # 尝试优雅终止
            self.process.terminate()

            try:
                self.process.wait(timeout=timeout)
                logger.info("GUI process terminated gracefully")
            except subprocess.TimeoutExpired:
                # 超时则强制杀死
                logger.warning("GUI process did not terminate, forcing kill")
                self.process.kill()
                self.process.wait()

            # 记录输出
            try:
                stdout, stderr = self.process.communicate(timeout=1)
                if stdout:
                    logger.debug(f"GUI stdout: {stdout.decode()}")
                if stderr:
                    logger.warning(f"GUI stderr: {stderr.decode()}")
            except subprocess.TimeoutExpired:
                pass

            self.process = None
            return True

        except Exception as e:
            logger.error(f"Failed to stop GUI: {e}")
            return False

    def is_running(self) -> bool:
        """
        检查 GUI 进程是否运行

        Returns:
            运行中返回 True，否则返回 False
        """
        if self.process is None:
            return False
        return self.process.poll() is None

    def __del__(self):
        """确保进程被清理"""
        if self.process and self.is_running():
            self.stop()
