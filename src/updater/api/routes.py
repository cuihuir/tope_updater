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
from updater.services.reporter import ReportService

router = APIRouter(prefix="/api/v1.0")


@router.get(
    "/progress",
    response_model=ProgressResponse,
    tags=["OTA Operations"],
    summary="查询 OTA 操作进度",
    description="""
查询当前 OTA 操作的状态和进度。

### 返回的状态 (stage)

- **idle** - 空闲，等待操作
- **downloading** - 正在下载
- **verifying** - 正在验证 MD5
- **toInstall** - 已下载，等待安装
- **installing** - 正在安装
- **success** - 操作成功
- **failed** - 操作失败

### 示例响应

**下载中**:
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "stage": "downloading",
    "progress": 45,
    "message": "Downloading package... 47.2 MB / 104.9 MB",
    "error": null
  }
}
```

**失败**:
```json
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
```
    """,
)
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


@router.post(
    "/download",
    response_model=SuccessResponse,
    tags=["OTA Operations"],
    summary="触发 OTA 包下载",
    description="""
触发异步下载 OTA 更新包。

### 下载流程

1. 验证请求参数（版本号、URL、大小、MD5）
2. 检查当前状态（必须是 idle/failed/success）
3. 启动后台下载任务
4. 下载过程中验证：
   - HTTP Content-Length
   - 业务层 package_size
   - MD5 完整性
5. 下载完成后状态变为 `toInstall`

### 示例请求

```bash
curl -X POST http://localhost:12315/api/v1.0/download \\
  -H "Content-Type: application/json" \\
  -d '{
    "version": "1.0.0",
    "package_url": "http://localhost:8888/test-update-1.0.0.zip",
    "package_name": "test-update-1.0.0.zip",
    "package_size": 468,
    "package_md5": "600aff0f78265dd25bb6907828f916dd"
  }'
```

### 错误码

- **409** - 操作已在进行中
- **410** - 包已过期（验证后超过 24 小时）
    """,
)
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


@router.post(
    "/update",
    response_model=SuccessResponse,
    tags=["OTA Operations"],
    summary="触发 OTA 包安装",
    description="""
触发异步安装已下载的 OTA 更新包。

### 安装流程

1. 验证当前状态（必须是 `toInstall`）
2. 解压 ZIP 包并解析 manifest.json
3. 创建版本快照目录（/opt/tope/versions/vX.Y.Z/）
4. 停止相关服务（systemd）
5. 部署文件到版本目录
6. 更新符号链接（current → 新版本，previous → 旧版本）
7. 启动服务
8. 验证服务健康

### 自动回滚

如果部署失败，系统会自动执行两级回滚：

1. **Level 1**: 回滚到 previous 版本
2. **Level 2**: 如果 Level 1 失败，回滚到 factory 版本
3. **手动干预**: 如果两级回滚都失败，需要人工介入

### 示例请求

```bash
# 1. 先下载包
curl -X POST http://localhost:12315/api/v1.0/download \\
  -H "Content-Type: application/json" \\
  -d '{
    "version": "1.0.0",
    "package_url": "http://localhost:8888/test-update-1.0.0.zip",
    "package_name": "test-update-1.0.0.zip",
    "package_size": 468,
    "package_md5": "600aff0f78265dd25bb6907828f916dd"
  }'

# 2. 等待下载完成（查询进度直到 stage=toInstall）
curl http://localhost:12315/api/v1.0/progress

# 3. 触发安装
curl -X POST http://localhost:12315/api/v1.0/update \\
  -H "Content-Type: application/json" \\
  -d '{"version": "1.0.0"}'

# 4. 查询安装进度
curl http://localhost:12315/api/v1.0/progress
```

### 错误码

- **400** - 版本号不匹配
- **404** - 包文件不存在
- **409** - 操作已在进行中或状态不正确
- **410** - 包已过期（验证后超过 24 小时）
    """,
)
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
    reporter = ReportService()
    download_service = DownloadService(reporter=reporter)
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
    reporter = ReportService()
    deploy_service = DeployService(reporter=reporter)

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
