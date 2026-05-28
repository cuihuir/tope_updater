"""Display ownership switching through the systemd display switcher."""

import asyncio
import logging


class DisplaySwitchService:
    """Thin async wrapper around tope-display-switcher."""

    def __init__(
        self,
        command: str = "/usr/local/bin/tope-display-switcher",
        timeout: float = 15.0,
    ):
        self.command = command
        self.timeout = timeout
        self.logger = logging.getLogger("updater.display")

    async def show_updater(self) -> bool:
        """Switch the display to the updater GUI."""
        return await self._run("show", "updater")

    async def show_printer(self) -> bool:
        """Switch the display back to the printer GUI."""
        return await self._run("show", "printer")

    async def blank(self) -> bool:
        """Stop display-owning GUI services."""
        return await self._run("blank")

    async def _run(self, *args: str) -> bool:
        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                self.command,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            self.logger.error("Display switch timed out: %s", " ".join(args))
            if process is not None:
                try:
                    process.kill()
                except Exception:
                    pass
            return False
        except Exception as exc:
            self.logger.warning("Display switch failed to start: %s", exc)
            return False

        if stdout:
            self.logger.info(stdout.decode(errors="replace").strip())
        if stderr:
            self.logger.warning(stderr.decode(errors="replace").strip())

        return process.returncode == 0
