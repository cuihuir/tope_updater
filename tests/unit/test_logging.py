"""Unit tests for utils/logging.py."""

import logging
import pytest
from logging.handlers import RotatingFileHandler

from updater.utils.logging import setup_logger


@pytest.mark.unit
class TestSetupLogger:
    """Test setup_logger function."""

    @pytest.fixture(autouse=True)
    def cleanup_loggers(self):
        """每个测试后清理创建的 logger，避免 handler 泄漏。"""
        created = []
        yield created
        for name in created:
            lg = logging.getLogger(name)
            for h in list(lg.handlers):
                h.close()
                lg.removeHandler(h)

    def _unique_name(self, suffix: str) -> str:
        return f"test_updater_logger_{suffix}"

    def test_creates_log_directory(self, tmp_path, cleanup_loggers):
        """不存在的日志目录应被自动创建。"""
        log_dir = tmp_path / "new_logs" / "subdir"
        log_file = str(log_dir / "test.log")
        name = self._unique_name("dir")
        cleanup_loggers.append(name)

        setup_logger(name, log_file)

        assert log_dir.exists()

    def test_returns_logger_with_correct_name(self, tmp_path, cleanup_loggers):
        """返回的 logger 名称应与传入参数一致。"""
        log_file = str(tmp_path / "test.log")
        name = self._unique_name("name")
        cleanup_loggers.append(name)

        logger = setup_logger(name, log_file)

        assert logger.name == name

    def test_logger_level_info_by_default(self, tmp_path, cleanup_loggers):
        """默认日志级别为 INFO。"""
        log_file = str(tmp_path / "test.log")
        name = self._unique_name("level_default")
        cleanup_loggers.append(name)

        logger = setup_logger(name, log_file)

        assert logger.level == logging.INFO

    def test_logger_level_custom(self, tmp_path, cleanup_loggers):
        """自定义 level 参数应被正确设置。"""
        log_file = str(tmp_path / "test.log")
        name = self._unique_name("level_debug")
        cleanup_loggers.append(name)

        logger = setup_logger(name, log_file, level=logging.DEBUG)

        assert logger.level == logging.DEBUG

    def test_adds_rotating_file_handler(self, tmp_path, cleanup_loggers):
        """应添加 RotatingFileHandler。"""
        log_file = str(tmp_path / "test.log")
        name = self._unique_name("file_handler")
        cleanup_loggers.append(name)

        logger = setup_logger(name, log_file)

        file_handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
        assert len(file_handlers) == 1

    def test_adds_console_handler(self, tmp_path, cleanup_loggers):
        """应添加 StreamHandler（控制台输出）。"""
        log_file = str(tmp_path / "test.log")
        name = self._unique_name("console_handler")
        cleanup_loggers.append(name)

        logger = setup_logger(name, log_file)

        stream_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
        ]
        assert len(stream_handlers) == 1

    def test_no_duplicate_handlers_on_second_call(self, tmp_path, cleanup_loggers):
        """重复调用不应添加重复 handler。"""
        log_file = str(tmp_path / "test.log")
        name = self._unique_name("no_dup")
        cleanup_loggers.append(name)

        logger1 = setup_logger(name, log_file)
        handler_count = len(logger1.handlers)

        logger2 = setup_logger(name, log_file)

        assert logger1 is logger2
        assert len(logger2.handlers) == handler_count

    def test_rotating_file_max_bytes(self, tmp_path, cleanup_loggers):
        """RotatingFileHandler 的 maxBytes 应与传入参数一致。"""
        log_file = str(tmp_path / "test.log")
        name = self._unique_name("max_bytes")
        cleanup_loggers.append(name)
        custom_max = 5 * 1024 * 1024  # 5MB

        logger = setup_logger(name, log_file, max_bytes=custom_max)

        file_handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
        assert file_handlers[0].maxBytes == custom_max

    def test_rotating_file_backup_count(self, tmp_path, cleanup_loggers):
        """RotatingFileHandler 的 backupCount 应与传入参数一致。"""
        log_file = str(tmp_path / "test.log")
        name = self._unique_name("backup_count")
        cleanup_loggers.append(name)

        logger = setup_logger(name, log_file, backup_count=5)

        file_handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
        assert file_handlers[0].backupCount == 5

    def test_logger_can_write_to_file(self, tmp_path, cleanup_loggers):
        """Logger 应能成功写入文件。"""
        log_file = str(tmp_path / "test.log")
        name = self._unique_name("write")
        cleanup_loggers.append(name)

        logger = setup_logger(name, log_file)
        logger.info("test message")

        # 强制 flush
        for h in logger.handlers:
            h.flush()

        assert (tmp_path / "test.log").exists()
        content = (tmp_path / "test.log").read_text()
        assert "test message" in content
