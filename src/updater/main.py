"""FastAPI application for TOPE OTA Updater."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
import uvicorn

from updater.utils.logging import setup_logger
from updater.services.state_manager import StateManager
from updater.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown hooks.

    Startup:
    - Initialize logger
    - Create required directories (./tmp/, ./logs/, ./backups/)
    - Initialize StateManager singleton
    - Load persistent state if exists

    Shutdown:
    - Log shutdown message
    """
    # Startup
    logger = setup_logger("updater", "./logs/updater.log", level=logging.INFO)
    logger.info("TOPE Updater starting up...")

    # Create required directories
    directories = ["./tmp", "./logs", "./backups"]
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured directory exists: {directory}")

    # Initialize StateManager singleton
    state_manager = StateManager()

    # Startup self-healing: attempt to load and validate persistent state
    state = state_manager.load_state()
    if state:
        logger.info(
            f"Found persistent state: version={state.version}, "
            f"stage={state.stage.value}, bytes={state.bytes_downloaded}"
        )

        # Check if package expired (>24h after verification)
        if state.is_package_expired():
            logger.warning(
                f"Package {state.version} expired (>24h after verification), "
                f"cleaning up..."
            )
            # Delete expired package and state file
            package_path = Path("./tmp") / state.package_name
            package_path.unlink(missing_ok=True)
            state_manager.delete_state()
            state_manager.reset()
            logger.info("Expired package cleaned up, reset to idle")
        else:
            # Resume from valid persistent state
            logger.info(f"Resuming from valid state: {state.stage.value}")
            state_manager.update_status(
                stage=state.stage,
                progress=int((state.bytes_downloaded / state.package_size) * 100),
                message=f"Resumed {state.stage.value} for version {state.version}",
            )
    else:
        logger.info("No persistent state found, starting fresh")

    logger.info("TOPE Updater ready on port 12315")

    yield

    # Shutdown
    logger.info("TOPE Updater shutting down...")


# Create FastAPI application
app = FastAPI(
    title="TOPE OTA Updater",
    description="OTA Update Service for Embedded 3D Printer Devices",
    version="1.0.0",
    lifespan=lifespan,
)

# Register API routes
app.include_router(router)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "tope-updater", "version": "1.0.0"}


def main():
    """Main entry point for running the server."""
    uvicorn.run(
        "updater.main:app",
        host="0.0.0.0",
        port=12315,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    main()
