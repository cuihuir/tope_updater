"""FastAPI application for TOPE OTA Updater."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
import uvicorn

from updater.utils.logging import setup_logger
from updater.services.state_manager import StateManager
from updater.models.status import StageEnum
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
        elif state.stage == StageEnum.FAILED:
            # Previous operation failed, keep state for investigation but allow retry
            logger.warning(f"Previous operation failed: {state.version}")
            state_manager.update_status(
                stage=StageEnum.FAILED,
                progress=0,
                message=f"Previous operation failed, ready for retry",
                error="See logs for details",
            )
        elif state.stage == StageEnum.DOWNLOADING:
            # Service restarted during download - background task was lost
            # Clean up partial download and reset to idle (no auto-resume for now)
            logger.warning(
                f"Found interrupted download: version={state.version}, "
                f"bytes={state.bytes_downloaded}, cleaning up..."
            )
            package_path = Path("./tmp") / state.package_name
            package_path.unlink(missing_ok=True)
            state_manager.delete_state()
            state_manager.reset()
            logger.info("Interrupted download cleaned up, reset to idle")
        elif state.stage == StageEnum.VERIFYING:
            # Service restarted during verification - verification task was lost
            # Clean up and reset to idle, client can retry download
            logger.warning(
                f"Found interrupted verification: version={state.version}, "
                f"cleaning up..."
            )
            package_path = Path("./tmp") / state.package_name
            package_path.unlink(missing_ok=True)
            state_manager.delete_state()
            state_manager.reset()
            logger.info("Interrupted verification cleaned up, reset to idle")
        else:
            # Validate state integrity for other stages (TO_INSTALL, etc.)
            if state.bytes_downloaded > state.package_size:
                logger.error(
                    f"Corrupted state: bytes_downloaded ({state.bytes_downloaded}) > "
                    f"package_size ({state.package_size}), cleaning up"
                )
                package_path = Path("./tmp") / state.package_name
                package_path.unlink(missing_ok=True)
                state_manager.delete_state()
                state_manager.reset()
                logger.info("Corrupted state cleaned up, reset to idle")
            else:
                # Resume from valid persistent state (TO_INSTALL, SUCCESS, etc.)
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
    description="""
## TOP.E OTA 更新服务

用于嵌入式 3D 打印机设备的 OTA (Over-The-Air) 固件/软件更新服务。

### 核心特性

✅ 版本快照架构 | ✅ 两级回滚 | ✅ 三层验证 | ✅ 进度上报 | ✅ systemd 集成

### 快速开始

```bash
# 1. 下载
curl -X POST http://localhost:12315/api/v1.0/download -H "Content-Type: application/json" \\
  -d '{"version":"1.0.0","package_url":"http://localhost:8888/test.zip","package_name":"test.zip","package_size":468,"package_md5":"abc123..."}'

# 2. 查询进度
curl http://localhost:12315/api/v1.0/progress

# 3. 安装
curl -X POST http://localhost:12315/api/v1.0/update -H "Content-Type: application/json" -d '{"version":"1.0.0"}'
```

📖 **文档**: `docs/DEPLOYMENT.md` | `docs/ROLLBACK.md` | `tests/reports/version_snapshot_test_report.md`
    """,
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "OTA Operations",
            "description": "OTA 更新操作：下载、安装、查询进度"
        },
        {
            "name": "Health",
            "description": "健康检查和服务状态"
        }
    ]
)

# Register API routes
app.include_router(router)


@app.get(
    "/",
    tags=["Health"],
    summary="健康检查",
    description="检查服务是否正常运行",
)
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "tope-updater",
        "version": "2.0.0",
        "features": [
            "Version Snapshot Architecture",
            "Two-Level Rollback",
            "Progress Reporting",
            "systemd Integration"
        ]
    }


def main():
    """Main entry point for running the server."""
    uvicorn.run(
        app,  # Pass app object directly for debug support
        host="0.0.0.0",
        port=12315,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    main()
