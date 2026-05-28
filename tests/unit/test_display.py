"""Unit tests for DisplaySwitchService."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from updater.services.display import DisplaySwitchService


@pytest.mark.unit
class TestDisplaySwitchService:
    """Display switch wrapper behavior."""

    @pytest.mark.asyncio
    async def test_show_updater_returns_true_on_success(self):
        service = DisplaySwitchService(command="/usr/local/bin/tope-display-switcher")

        process = AsyncMock()
        process.communicate = AsyncMock(return_value=(b"ok\n", b""))
        process.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=process) as create:
            result = await service.show_updater()

        assert result is True
        create.assert_called_once_with(
            "/usr/local/bin/tope-display-switcher",
            "show",
            "updater",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    @pytest.mark.asyncio
    async def test_show_printer_returns_false_on_nonzero(self):
        service = DisplaySwitchService()

        process = AsyncMock()
        process.communicate = AsyncMock(return_value=(b"", b"failed\n"))
        process.returncode = 1

        with patch("asyncio.create_subprocess_exec", return_value=process):
            result = await service.show_printer()

        assert result is False

    @pytest.mark.asyncio
    async def test_show_updater_returns_false_on_timeout(self):
        service = DisplaySwitchService(timeout=0.01)

        process = AsyncMock()
        process.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
        process.kill = MagicMock()

        with patch("asyncio.create_subprocess_exec", return_value=process):
            result = await service.show_updater()

        assert result is False
