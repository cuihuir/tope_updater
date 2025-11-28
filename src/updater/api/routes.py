"""API route handlers for OTA updater endpoints."""

import asyncio
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse

from updater.api.models import (
    DownloadRequest,
    UpdateRequest,
    ProgressResponse,
    SuccessResponse,
    ErrorResponse,
)
from updater.models.status import StageEnum
from updater.services.state_manager import StateManager
from updater.services.download import DownloadService
from updater.services.deploy import DeployService
from updater.services.process import ProcessManager

router = APIRouter(prefix="/api/v1.0")


@router.get("/progress", response_model=ProgressResponse)
async def get_progress():
    """GET /api/v1.0/progress - Query current OTA operation status.

    Returns:
        ProgressResponse with current stage, progress, message, and error state

    Response format (success):
        {
            "code": 200,
            "msg": "success",
            "data": {
                "stage": "downloading",
                "progress": 45,
                "message": "Downloading package...",
                "error": null
            }
        }

    Response format (failed stage):
        {
            "code": 500,
            "msg": "Update failed: MD5_MISMATCH",
            "data": {
                "stage": "failed",
                "progress": 0,
                "message": "MD5 verification failed",
                "error": "MD5_MISMATCH: expected abc123, got def456"
            },
            "stage": "failed",
            "progress": 0
        }
    """
    state_manager = StateManager()
    status = state_manager.get_status()

    # Determine application-level status code
    if status.stage.value == "failed":
        code = 500
        msg = f"Update failed: {status.error}" if status.error else "Update failed"
        return ProgressResponse(
            code=code,
            msg=msg,
            data=status,
            stage=status.stage,
            progress=status.progress,
        )
    else:
        return ProgressResponse(code=200, msg="success", data=status)


@router.post("/download", response_model=SuccessResponse)
async def post_download(request: DownloadRequest, background_tasks: BackgroundTasks):
    """POST /api/v1.0/download - Trigger async package download.

    Args:
        request: DownloadRequest with version, package_url, package_name,
                 package_size, package_md5
        background_tasks: FastAPI background tasks

    Returns:
        SuccessResponse if operation starts successfully

    Raises:
        HTTPException 409 if already in progress
        HTTPException 410 if package expired (>24h after verification)
    """
    state_manager = StateManager()
    current_status = state_manager.get_status()

    # Check if operation already in progress
    if current_status.stage not in [StageEnum.IDLE, StageEnum.FAILED, StageEnum.SUCCESS]:
        return JSONResponse(
            status_code=200,
            content={
                "code": 409,
                "msg": f"Operation already in progress: {current_status.stage.value}",
                "stage": current_status.stage.value,
                "progress": current_status.progress,
            },
        )

    # Check for expired package
    persistent_state = state_manager.get_persistent_state()
    if persistent_state and persistent_state.is_package_expired():
        return JSONResponse(
            status_code=200,
            content={
                "code": 410,
                "msg": "Package expired (>24h after verification)",
                "stage": current_status.stage.value,
                "progress": current_status.progress,
            },
        )

    # Start download in background
    background_tasks.add_task(
        _download_workflow,
        request.version,
        request.package_url,
        request.package_name,
        request.package_size,
        request.package_md5,
    )

    return JSONResponse(
        status_code=200,
        content={"code": 200, "msg": "success", "data": None},
    )


@router.post("/update", response_model=SuccessResponse)
async def post_update(request: UpdateRequest, background_tasks: BackgroundTasks):
    """POST /api/v1.0/update - Trigger async package installation.

    Args:
        request: UpdateRequest with version to install
        background_tasks: FastAPI background tasks

    Returns:
        SuccessResponse if operation starts successfully

    Raises:
        HTTPException 404 if package not found
        HTTPException 409 if already in progress
        HTTPException 410 if package expired (>24h after verification)
    """
    state_manager = StateManager()
    current_status = state_manager.get_status()

    # Check if operation already in progress
    if current_status.stage not in [StageEnum.IDLE, StageEnum.TO_INSTALL, StageEnum.SUCCESS, StageEnum.FAILED]:
        return JSONResponse(
            status_code=200,
            content={
                "code": 409,
                "msg": f"Operation already in progress: {current_status.stage.value}",
                "stage": current_status.stage.value,
                "progress": current_status.progress,
            },
        )

    # Check for package existence
    persistent_state = state_manager.get_persistent_state()
    if not persistent_state or persistent_state.version != request.version:
        return JSONResponse(
            status_code=200,
            content={
                "code": 404,
                "msg": f"Package not found: {request.version}",
            },
        )

    # Check for expired package
    if persistent_state.is_package_expired():
        return JSONResponse(
            status_code=200,
            content={
                "code": 410,
                "msg": "Package expired (>24h after verification)",
                "stage": current_status.stage.value,
                "progress": current_status.progress,
            },
        )

    # Start update in background
    background_tasks.add_task(_update_workflow, request.version)

    return JSONResponse(
        status_code=200,
        content={"code": 200, "msg": "success", "data": None},
    )


async def _download_workflow(
    version: str,
    package_url: str,
    package_name: str,
    package_size: int,
    package_md5: str,
) -> None:
    """Background task for download workflow."""
    download_service = DownloadService()
    try:
        await download_service.download_package(
            version=version,
            package_url=package_url,
            package_name=package_name,
            package_size=package_size,
            package_md5=package_md5,
        )
    except Exception as e:
        # Errors already logged and state updated in DownloadService
        pass


async def _update_workflow(version: str) -> None:
    """Background task for update workflow."""
    state_manager = StateManager()
    deploy_service = DeployService()

    try:
        # Get package path
        persistent_state = state_manager.get_persistent_state()
        if not persistent_state:
            raise ValueError("No persistent state found")

        package_path = Path("./tmp") / persistent_state.package_name
        if not package_path.exists():
            raise FileNotFoundError(f"Package not found: {package_path}")

        # Deploy package
        await deploy_service.deploy_package(package_path, version)

        # TODO: Restart services based on manifest (will implement in future iterations)

        # Cleanup
        state_manager.delete_state()

    except Exception as e:
        state_manager.update_status(
            stage=StageEnum.FAILED,
            progress=0,
            message="Update failed",
            error=f"UPDATE_FAILED: {str(e)}",
        )
