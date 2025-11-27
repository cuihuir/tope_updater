# FastAPI Production Best Practices for OTA Updater Service

**Branch**: `001-updater-core` | **Date**: 2025-11-26 | **Context**: Embedded device OTA updater
**Purpose**: Document production-ready patterns for building async HTTP server on port 12315

## Executive Summary

This document provides production-proven patterns for building the OTA updater service with FastAPI. Focus areas: async best practices to prevent blocking during concurrent operations (download + progress polling), error handling for embedded device reliability, testing with pytest-asyncio, and production deployment with uvicorn. All recommendations prioritize reliability over convenience (embedded device OTA cannot fail).

---

## 1. Project Structure

### Decision: Layered Architecture with Clear Separation of Concerns

**Structure**:
```text
src/updater/
├── main.py                    # FastAPI app + lifespan management
├── api/
│   ├── endpoints.py           # Route handlers (thin layer)
│   └── models.py              # Pydantic request/response schemas
├── services/
│   ├── download.py            # Business logic: async download
│   ├── verification.py        # Business logic: MD5 verification
│   ├── deployment.py          # Business logic: atomic file ops
│   ├── process_control.py     # Business logic: SIGTERM/SIGKILL
│   └── state_manager.py       # Shared state management
├── models/
│   ├── manifest.py            # Domain models (NOT Pydantic)
│   ├── state.py               # State file structure
│   └── status.py              # Status enum
└── utils/
    ├── logging.py             # Rotating logger
    └── callbacks.py           # HTTP callbacks to device-api
```

**Rationale**:
- **api/**: Endpoints are thin adapters that validate input (Pydantic) and delegate to services. This keeps routes testable without mocking business logic.
- **services/**: Core business logic lives here. Services are pure Python classes/functions, not FastAPI-aware, enabling unit testing without HTTP context.
- **models/**: Domain models separate from Pydantic schemas. Pydantic is for API validation; domain models are for business logic.
- **Separation of api/ and services/**: Critical for embedded reliability. You can test services independently (unit tests) and endpoints separately (integration tests with httpx AsyncClient).

**Anti-pattern to avoid**: Putting business logic directly in route handlers. This couples your logic to FastAPI and makes unit testing require spinning up the full HTTP server.

**Code Example**:
```python
# api/endpoints.py - THIN route handler
from fastapi import APIRouter, HTTPException, Depends
from .models import DownloadRequest, DownloadResponse
from ..services.state_manager import StateManager

router = APIRouter(prefix="/api/v1.0")

@router.post("/download", response_model=DownloadResponse)
async def trigger_download(
    request: DownloadRequest,
    state_mgr: StateManager = Depends(get_state_manager)
):
    """
    Trigger async download. Returns immediately; poll /progress for status.
    Idempotent: resumes existing download if package_url matches.
    """
    # Validation already done by Pydantic DownloadRequest

    # Delegate to service layer (testable without FastAPI)
    await state_mgr.start_download(
        version=request.version,
        url=request.package_url,
        md5=request.package_md5,
        size=request.package_size
    )

    return DownloadResponse(status="accepted", message="Download started")

# services/state_manager.py - BUSINESS LOGIC (no FastAPI dependency)
class StateManager:
    """Manages download state and background task orchestration."""

    async def start_download(self, version: str, url: str, md5: str, size: int):
        # Check idempotency: resume if same URL exists
        if self._state.package_url == url and self._state.stage == "downloading":
            logger.info(f"Resuming existing download for {url}")
            return  # Idempotent: do nothing

        # Create background task (don't await)
        asyncio.create_task(self._download_task(version, url, md5, size))
```

---

## 2. Async Best Practices - Avoiding Event Loop Blocking

### Decision: Use async/await for I/O, run_in_executor for CPU/blocking operations

**Critical Rule**: NEVER do blocking I/O or CPU work in `async def` functions.

**Blocking operations to watch out for**:
- `open()`, `read()`, `write()` (filesystem I/O) - Use `aiofiles` or `run_in_executor`
- `time.sleep()` - Use `asyncio.sleep()`
- `requests.get()` - Use `httpx.AsyncClient`
- `subprocess.run()` - Use `asyncio.create_subprocess_exec()`
- `hashlib.md5().update()` in large loops (CPU-bound) - Use `run_in_executor`

**Rationale**: This OTA updater must handle concurrent requests:
- Device-API POSTs download commands
- OTA-GUI polls `/progress` every 500ms
- Download runs in background

If you use blocking I/O in the download task, the `/progress` endpoint will hang during file writes, violating FR-001c (must respond within 100ms).

**Code Example - Correct Async Patterns**:

```python
# services/download.py - Async HTTP download with httpx
import asyncio
import aiofiles
import httpx
from pathlib import Path

class DownloadService:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def download_package(self, url: str, dest: Path, resume_from: int = 0):
        """
        Non-blocking async download with Range support.
        Streams to disk without buffering entire file in RAM (FR-021).
        """
        headers = {}
        if resume_from > 0:
            headers["Range"] = f"bytes={resume_from}-"

        # Async HTTP request - does NOT block event loop
        async with self.client.stream("GET", url, headers=headers) as response:
            response.raise_for_status()

            # Async file I/O - does NOT block event loop
            async with aiofiles.open(dest, "ab") as f:
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    await f.write(chunk)
                    # Update progress (non-blocking)
                    self._bytes_downloaded += len(chunk)

# services/verification.py - CPU-bound MD5 in executor
import hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

class VerificationService:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1)

    async def compute_md5(self, file_path: Path) -> str:
        """
        Offload CPU-intensive MD5 computation to thread pool.
        Prevents blocking event loop during large file hashing.
        """
        loop = asyncio.get_running_loop()
        # run_in_executor: runs sync function in thread, returns awaitable
        return await loop.run_in_executor(
            self.executor,
            self._compute_md5_blocking,  # Regular def function
            file_path
        )

    def _compute_md5_blocking(self, file_path: Path) -> str:
        """Blocking helper - runs in thread pool, not in event loop."""
        md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                md5.update(chunk)  # CPU-intensive
        return md5.hexdigest()

# services/process_control.py - Async subprocess control
import asyncio
import signal

class ProcessController:
    async def terminate_process(self, pid: int, timeout: int = 10) -> bool:
        """
        Graceful termination: SIGTERM -> wait -> SIGKILL if needed.
        Non-blocking wait using asyncio.create_subprocess_exec.
        """
        try:
            # Send SIGTERM
            os.kill(pid, signal.SIGTERM)
            logger.info(f"Sent SIGTERM to PID {pid}")

            # Non-blocking wait with timeout
            for _ in range(timeout):
                await asyncio.sleep(1)  # NOT time.sleep()
                if not self._is_process_alive(pid):
                    logger.info(f"Process {pid} terminated gracefully")
                    return True

            # Force kill if still alive
            os.kill(pid, signal.SIGKILL)
            logger.warning(f"Sent SIGKILL to PID {pid} after timeout")
            return False

        except ProcessLookupError:
            return True  # Already dead
```

**When to use `def` vs `async def` in FastAPI**:
- Use `async def` if function does I/O (network, disk via aiofiles) or calls other async functions
- Use `def` for pure computation (FastAPI runs it in thread pool automatically)
- For this OTA updater: All endpoints should be `async def` because they interact with async services

---

## 3. Error Handling Patterns

### Decision: Centralized Exception Handlers + Custom Error Responses

**Problem**: Embedded devices need predictable error formats for remote debugging. FastAPI's default error responses lack detail for OTA-specific failures (MD5_MISMATCH, DISK_FULL, etc.).

**Solution**: Custom exception classes + global exception handlers + structured error responses.

**Rationale**:
- Device-API receives error codes it can parse and report to cloud
- Logs contain full stack traces for debugging
- Clients get consistent JSON error format
- Errors never leak internal paths or stack traces to external systems

**Code Example**:

```python
# models/errors.py - Custom exception hierarchy
class UpdaterError(Exception):
    """Base exception for all updater errors."""
    def __init__(self, code: str, message: str, details: dict = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)

class MD5MismatchError(UpdaterError):
    def __init__(self, expected: str, actual: str):
        super().__init__(
            code="MD5_MISMATCH",
            message=f"Package integrity check failed",
            details={"expected": expected, "actual": actual}
        )

class DiskFullError(UpdaterError):
    def __init__(self, required_bytes: int, available_bytes: int):
        super().__init__(
            code="DISK_FULL",
            message="Insufficient disk space for update",
            details={"required": required_bytes, "available": available_bytes}
        )

# main.py - Global exception handlers
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from .models.errors import UpdaterError
import logging

logger = logging.getLogger("updater")

app = FastAPI(title="TOPE OTA Updater")

@app.exception_handler(UpdaterError)
async def updater_error_handler(request: Request, exc: UpdaterError):
    """
    Catch all updater-specific errors and return structured JSON.
    Logs full exception for debugging but returns sanitized response.
    """
    logger.error(
        f"Updater error: {exc.code} - {exc.message}",
        extra={"details": exc.details},
        exc_info=True  # Include stack trace in logs
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": exc.code,
            "message": exc.message,
            "details": exc.details
        }
    )

@app.exception_handler(Exception)
async def catch_all_handler(request: Request, exc: Exception):
    """
    Catch unexpected errors (bugs). Log full trace, return generic error.
    Never expose internal details to clients (security).
    """
    logger.critical(
        f"Unexpected error: {type(exc).__name__}",
        exc_info=True
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred. Check logs.",
            "details": {}
        }
    )

# services/verification.py - Using custom exceptions
async def verify_package(self, file_path: Path, expected_md5: str):
    """Verify downloaded package MD5. Raises MD5MismatchError on failure."""
    actual_md5 = await self.compute_md5(file_path)

    if actual_md5 != expected_md5:
        # Raise custom exception - caught by global handler
        raise MD5MismatchError(expected=expected_md5, actual=actual_md5)

    logger.info(f"MD5 verification passed: {actual_md5}")
```

**Additional Pattern - Validation Errors**:

```python
# Pydantic validation errors return 422 by default - override for consistency
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Return consistent format for request validation errors."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "INVALID_REQUEST",
            "message": "Request validation failed",
            "details": {"errors": exc.errors()}
        }
    )
```

---

## 4. Testing Strategies

### Decision: Layered Testing with pytest-asyncio + httpx AsyncClient

**Test Pyramid**:
1. **Unit tests**: Test services in isolation (no HTTP server)
2. **Integration tests**: Test API endpoints with AsyncClient (server runs in-memory)
3. **Contract tests**: Validate OpenAPI spec matches implementation

**Rationale**: Embedded devices are hard to debug remotely. Comprehensive tests prevent production bugs.

**Code Example - Unit Testing Services**:

```python
# tests/unit/test_verification.py
import pytest
from pathlib import Path
from updater.services.verification import VerificationService
from updater.models.errors import MD5MismatchError

@pytest.mark.asyncio
async def test_md5_verification_success(tmp_path):
    """Test MD5 verification passes for correct hash."""
    # Arrange
    service = VerificationService()
    test_file = tmp_path / "test.bin"
    test_file.write_bytes(b"test content")
    expected_md5 = "9a0364b9e99bb480dd25e1f0284c8555"  # md5 of "test content"

    # Act & Assert - should not raise
    await service.verify_package(test_file, expected_md5)

@pytest.mark.asyncio
async def test_md5_verification_failure(tmp_path):
    """Test MD5 verification raises MD5MismatchError for wrong hash."""
    service = VerificationService()
    test_file = tmp_path / "test.bin"
    test_file.write_bytes(b"test content")
    wrong_md5 = "0" * 32

    # Assert exception raised
    with pytest.raises(MD5MismatchError) as exc_info:
        await service.verify_package(test_file, wrong_md5)

    assert exc_info.value.code == "MD5_MISMATCH"
    assert "9a0364b9e99bb480dd25e1f0284c8555" in str(exc_info.value.details)
```

**Code Example - Integration Testing Endpoints**:

```python
# tests/integration/test_api_endpoints.py
import pytest
from httpx import AsyncClient, ASGITransport
from updater.main import app

@pytest.fixture
def anyio_backend():
    """Use asyncio for async tests."""
    return "asyncio"

@pytest.fixture
async def async_client():
    """Create async HTTP client for testing endpoints."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client

@pytest.mark.anyio
async def test_download_endpoint_success(async_client: AsyncClient):
    """Test POST /api/v1.0/download returns 200 and starts download."""
    response = await async_client.post(
        "/api/v1.0/download",
        json={
            "version": "1.0.0",
            "package_url": "https://s3.example.com/update.zip",
            "package_name": "update.zip",
            "package_size": 1024000,
            "package_md5": "abc123def456"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"

@pytest.mark.anyio
async def test_download_endpoint_validation_error(async_client: AsyncClient):
    """Test POST /download rejects missing fields."""
    response = await async_client.post(
        "/api/v1.0/download",
        json={"version": "1.0.0"}  # Missing required fields
    )

    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "INVALID_REQUEST"

@pytest.mark.anyio
async def test_progress_endpoint_response_time(async_client: AsyncClient):
    """Test GET /progress responds within 100ms (FR-001c)."""
    import time

    start = time.perf_counter()
    response = await async_client.get("/api/v1.0/progress")
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert response.status_code == 200
    assert elapsed_ms < 100, f"Progress endpoint took {elapsed_ms}ms (limit: 100ms)"
```

**Mocking External Dependencies**:

```python
# tests/integration/test_download_flow.py
import pytest
from unittest.mock import AsyncMock, patch
import httpx

@pytest.mark.anyio
async def test_download_with_mocked_http(async_client: AsyncClient):
    """Test download flow without actual HTTP requests."""

    # Mock httpx.AsyncClient to avoid real network calls
    with patch('updater.services.download.httpx.AsyncClient') as mock_client:
        # Setup mock response
        mock_response = AsyncMock()
        mock_response.aiter_bytes = AsyncMock(return_value=[b"chunk1", b"chunk2"])
        mock_response.raise_for_status = AsyncMock()

        mock_client.return_value.__aenter__.return_value.stream = AsyncMock(
            return_value=mock_response
        )

        # Trigger download
        response = await async_client.post("/api/v1.0/download", json={...})

        assert response.status_code == 200
        # Verify mock was called with correct URL
        mock_client.return_value.__aenter__.return_value.stream.assert_called_once()
```

---

## 5. Dependency Injection - Managing Shared State

### Decision: FastAPI Depends() with singleton StateManager

**Problem**: Multiple endpoints need access to shared state (current download status, progress, stage). Using global variables is error-prone and breaks testability.

**Solution**: Use FastAPI's `Depends()` to inject StateManager singleton.

**Rationale**:
- Testable: Can inject mock StateManager in tests
- Thread-safe: Single instance across all requests (important for concurrent /progress polling)
- Clean: No global variables polluting module namespace

**Code Example**:

```python
# services/state_manager.py - Singleton state manager
from typing import Optional
import asyncio

class StateManager:
    """
    Manages shared state across all requests.
    Singleton pattern: only one instance exists.
    """
    _instance: Optional["StateManager"] = None

    def __init__(self):
        if StateManager._instance is not None:
            raise RuntimeError("Use StateManager.get_instance()")

        self.stage = "idle"
        self.progress = 0
        self.message = ""
        self.error = None
        self._lock = asyncio.Lock()  # Protect concurrent access

    @classmethod
    def get_instance(cls) -> "StateManager":
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def update_progress(self, progress: int, message: str):
        """Thread-safe progress update."""
        async with self._lock:
            self.progress = progress
            self.message = message

# api/dependencies.py - Dependency provider
def get_state_manager() -> StateManager:
    """FastAPI dependency: provides singleton StateManager."""
    return StateManager.get_instance()

# api/endpoints.py - Using dependency injection
from fastapi import Depends
from ..services.state_manager import StateManager
from .dependencies import get_state_manager

@router.get("/api/v1.0/progress")
async def get_progress(
    state_mgr: StateManager = Depends(get_state_manager)
):
    """
    Query current OTA progress. Must respond within 100ms (FR-001c).
    Injected StateManager is singleton - same instance across all requests.
    """
    return {
        "stage": state_mgr.stage,
        "progress": state_mgr.progress,
        "message": state_mgr.message,
        "error": state_mgr.error
    }

# tests/integration/test_with_mock_state.py - Testing with mocked dependency
@pytest.mark.anyio
async def test_progress_endpoint_with_mock():
    """Test progress endpoint with mocked StateManager."""

    # Create mock state manager
    mock_state = StateManager()
    mock_state.stage = "downloading"
    mock_state.progress = 42

    # Override dependency
    app.dependency_overrides[get_state_manager] = lambda: mock_state

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1.0/progress")
        data = response.json()

        assert data["stage"] == "downloading"
        assert data["progress"] == 42

    # Cleanup override
    app.dependency_overrides.clear()
```

---

## 6. Background Tasks - asyncio.create_task() vs BackgroundTasks

### Decision: Use asyncio.create_task() for long-running operations

**Comparison**:

| Pattern | Use Case | Lifecycle | OTA Updater Use |
|---------|----------|-----------|-----------------|
| FastAPI BackgroundTasks | Short tasks after response sent (send email, log event) | Completes before worker shutdown | NO - downloads take minutes |
| asyncio.create_task() | Long-running background operations | Runs until done (even after response) | YES - download + install tasks |

**Rationale for OTA Updater**:
- Downloads can take 5+ minutes for 100MB packages
- BackgroundTasks are designed for quick fire-and-forget operations
- create_task() gives full control over task lifecycle and cancellation

**Code Example**:

```python
# services/state_manager.py - Managing long-running task
class StateManager:
    def __init__(self):
        self.download_task: Optional[asyncio.Task] = None

    async def start_download(self, version: str, url: str, md5: str, size: int):
        """Start download in background. Returns immediately."""

        # Check if already downloading (idempotency)
        if self.download_task and not self.download_task.done():
            logger.info("Download already in progress")
            return

        # Create background task - does NOT await
        self.download_task = asyncio.create_task(
            self._download_and_verify(url, md5, size)
        )

        # Add done callback for cleanup/error handling
        self.download_task.add_done_callback(self._on_download_complete)

    async def _download_and_verify(self, url: str, md5: str, size: int):
        """Long-running background task."""
        try:
            await self.update_stage("downloading")

            # Download (takes minutes)
            download_svc = DownloadService()
            await download_svc.download_package(url, Path("./tmp/package.zip"))

            await self.update_stage("verifying")

            # Verify MD5
            verify_svc = VerificationService()
            await verify_svc.verify_package(Path("./tmp/package.zip"), md5)

            await self.update_stage("success")

        except Exception as e:
            logger.error(f"Download failed: {e}", exc_info=True)
            await self.update_stage("failed", error=str(e))

    def _on_download_complete(self, task: asyncio.Task):
        """Callback when download task finishes or fails."""
        try:
            # Check if task raised exception
            task.result()
        except Exception as e:
            logger.error(f"Download task failed: {e}")

# api/endpoints.py - Trigger background task
@router.post("/api/v1.0/download")
async def trigger_download(
    request: DownloadRequest,
    state_mgr: StateManager = Depends(get_state_manager)
):
    """
    Start async download. Returns immediately (200 OK).
    Client polls /progress for status.
    """
    await state_mgr.start_download(
        version=request.version,
        url=request.package_url,
        md5=request.package_md5,
        size=request.package_size
    )

    return {"status": "accepted", "message": "Download started"}
```

**Task Cancellation Pattern** (for graceful shutdown):

```python
# main.py - Cancel background tasks on shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # Startup
    logger.info("Updater starting...")
    yield

    # Shutdown - cancel background tasks
    state_mgr = StateManager.get_instance()
    if state_mgr.download_task and not state_mgr.download_task.done():
        logger.info("Cancelling download task...")
        state_mgr.download_task.cancel()
        try:
            await state_mgr.download_task
        except asyncio.CancelledError:
            logger.info("Download task cancelled successfully")

app = FastAPI(lifespan=lifespan)
```

---

## 7. Lifecycle Management - Startup/Shutdown with Lifespan

### Decision: Use @asynccontextmanager for resource initialization/cleanup

**Modern Pattern** (FastAPI 0.93+): `lifespan` parameter replaces deprecated `@app.on_event("startup")`.

**Rationale**:
- Startup and shutdown logic often share resources (DB connections, HTTP clients, locks)
- Context manager ensures cleanup happens even if startup fails
- Prevents resource leaks (critical for embedded devices with limited memory)

**Code Example**:

```python
# main.py - Lifespan management
from contextlib import asynccontextmanager
from fastapi import FastAPI
import logging
import httpx

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle: startup and shutdown.
    Code before yield runs at startup.
    Code after yield runs at shutdown.
    """
    # === STARTUP ===
    logger = logging.getLogger("updater")
    logger.info("Initializing updater service...")

    # Create required directories (FR-031, FR-032)
    for directory in [Path("./tmp"), Path("./logs"), Path("./backups")]:
        directory.mkdir(mode=0o755, exist_ok=True)
        logger.info(f"Created directory: {directory}")

    # Initialize shared HTTP client (reuse connection pool)
    app.state.http_client = httpx.AsyncClient(timeout=30.0)
    logger.info("HTTP client initialized")

    # Initialize state manager
    app.state.state_mgr = StateManager.get_instance()

    # Check for incomplete operations (FR-024)
    state_file = Path("./tmp/state.json")
    if state_file.exists():
        logger.info("Found incomplete operation, attempting recovery...")
        await app.state.state_mgr.recover_from_state_file(state_file)

    logger.info("Updater service ready on port 12315")

    # === APPLICATION RUNS HERE ===
    yield

    # === SHUTDOWN ===
    logger.info("Shutting down updater service...")

    # Cancel background tasks
    if app.state.state_mgr.download_task:
        app.state.state_mgr.download_task.cancel()

    # Close HTTP client (release connections)
    await app.state.http_client.aclose()
    logger.info("HTTP client closed")

    logger.info("Updater service stopped")

app = FastAPI(
    title="TOPE OTA Updater",
    version="1.0.0",
    lifespan=lifespan  # Register lifecycle manager
)
```

**Accessing lifespan resources in dependencies**:

```python
# api/dependencies.py
from fastapi import Request

def get_http_client(request: Request) -> httpx.AsyncClient:
    """Dependency: provides shared HTTP client from app state."""
    return request.app.state.http_client

# services/download.py - Using injected client
async def download_package(
    self,
    url: str,
    dest: Path,
    http_client: httpx.AsyncClient
):
    """Download with injected client (connection pooling)."""
    async with http_client.stream("GET", url) as response:
        # ... download logic
```

---

## 8. Production Deployment - uvicorn Configuration

### Decision: Single-worker uvicorn with systemd process management

**Configuration**:

```python
# main.py - Programmatic uvicorn config
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "updater.main:app",
        host="0.0.0.0",        # Listen on all interfaces
        port=12315,            # Hardcoded port (FR-001)
        log_level="info",      # Production: "warning"
        access_log=False,      # Disable access logs (use custom logging)
        workers=1,             # Single worker (state is in-memory)
        limit_concurrency=10,  # Max 10 concurrent requests
        timeout_keep_alive=5,  # Close idle connections after 5s
    )
```

**systemd Service Unit**:

```ini
# deploy/tope-updater.service
[Unit]
Description=TOPE OTA Updater Service
After=network.target
Wants=network.target

[Service]
Type=simple
User=root                                # Run as root (FR-034)
WorkingDirectory=/opt/tope/updater
ExecStart=/usr/bin/python3 -m updater.main
Restart=always                           # Auto-restart on failure
RestartSec=10                            # Wait 10s before restart
StandardOutput=journal                   # Log to systemd journal
StandardError=journal

# Resource limits (embedded device protection)
LimitNOFILE=1024                         # Max 1024 open files
MemoryLimit=100M                         # Hard limit: 100MB RAM

# Security (while running as root)
PrivateTmp=yes                           # Isolated /tmp
ProtectSystem=strict                     # Read-only /usr, /boot
ReadWritePaths=/opt/tope                 # Write access only to app dir

[Install]
WantedBy=multi-user.target
```

**Logging Configuration**:

```python
# utils/logging.py - Production logging setup
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logging():
    """
    Configure rotating file logger (FR-017, FR-018, FR-019).
    Production: INFO level, JSON format for parsing.
    """
    logger = logging.getLogger("updater")
    logger.setLevel(logging.INFO)

    # Rotating file handler: 10MB max, 3 backups
    log_file = Path("./logs/updater.log")
    handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=3
    )

    # ISO 8601 timestamp + log level (FR-019)
    formatter = logging.Formatter(
        fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S%z'  # ISO 8601
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Also log to stdout for systemd journal
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

# main.py - Initialize logging at startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup logging first
    logger = setup_logging()
    logger.info("Logging initialized")
    # ... rest of startup
```

**Monitoring Recommendations**:

```bash
# Check service status
systemctl status tope-updater

# View real-time logs
journalctl -u tope-updater -f

# Check resource usage
systemctl show tope-updater | grep Memory
ps aux | grep updater  # RAM usage

# Test port binding
netstat -tlnp | grep 12315
```

**Health Check Endpoint**:

```python
# api/endpoints.py - Health check for monitoring
@router.get("/health")
async def health_check():
    """
    Simple health check endpoint.
    Returns 200 if service is running.
    """
    return {
        "status": "healthy",
        "service": "tope-updater",
        "version": "1.0.0"
    }
```

---

## Summary Table - Quick Reference

| Pattern | Decision | Rationale |
|---------|----------|-----------|
| **Project Structure** | Layered: api/ (routes) + services/ (logic) + models/ (domain) | Testability - services independent of FastAPI |
| **Async I/O** | Use `httpx.AsyncClient`, `aiofiles`, `asyncio.sleep()` | Prevent blocking /progress endpoint during downloads |
| **CPU-bound ops** | Use `asyncio.to_thread()` or `run_in_executor()` | Offload MD5 computation to thread pool |
| **Error Handling** | Custom exceptions + global @app.exception_handler | Structured error responses for device-API parsing |
| **Testing** | pytest-asyncio + httpx AsyncClient for integration | Test async endpoints without production server |
| **Shared State** | FastAPI Depends() with singleton StateManager | Thread-safe, testable, no globals |
| **Background Tasks** | asyncio.create_task() for long-running ops | Downloads take minutes (BackgroundTasks are for short tasks) |
| **Lifecycle** | @asynccontextmanager lifespan for startup/shutdown | Resource cleanup (HTTP client, cancel tasks) |
| **Deployment** | Single-worker uvicorn + systemd service | State is in-memory (no multi-worker conflicts) |
| **Logging** | RotatingFileHandler 10MB + systemd journal | FR-018 compliance + remote debugging via journalctl |

---

## Production Checklist

Before deploying to embedded device:

- [ ] All tests pass (unit + integration + contract)
- [ ] /progress endpoint responds <100ms under load (use `pytest-benchmark`)
- [ ] MD5 verification tested with corrupted files
- [ ] Resume download tested with simulated network interruption
- [ ] Atomic file deployment tested with simulated power failure (kill -9 during write)
- [ ] Graceful shutdown cancels background tasks (SIGTERM test)
- [ ] Log rotation working (test with 10MB+ logs)
- [ ] systemd service starts on boot and restarts on crash
- [ ] Port 12315 binding fails loudly if already in use
- [ ] Memory usage <50MB peak (test with 100MB download)
- [ ] No hardcoded paths outside /opt/tope (allow relocation)

---

---

## 9. httpx Resumable Downloads - HTTP Range Best Practices

### Decision: Streaming with HTTP Range headers and incremental MD5

**Implementation Pattern**:
```python
async def download_package_resumable(
    url: str,
    dest_path: Path,
    expected_md5: str,
    progress_callback
) -> None:
    """
    Download package with resume support (断点续传).
    Computes MD5 while streaming to avoid second pass.
    """
    # Check existing file for resume
    resume_pos = dest_path.stat().st_size if dest_path.exists() else 0
    md5_hash = hashlib.md5()

    # If resuming, compute MD5 of existing partial file first
    if resume_pos > 0:
        with open(dest_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b""):
                md5_hash.update(chunk)

    headers = {"Range": f"bytes={resume_pos}-"} if resume_pos > 0 else {}

    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=300.0)) as client:
        async with client.stream("GET", url, headers=headers) as response:
            # Handle HTTP status codes
            if response.status_code == 416:  # Range Not Satisfiable
                # File changed on server, restart from beginning
                dest_path.unlink(missing_ok=True)
                return await download_package_resumable(url, dest_path, expected_md5, progress_callback)

            response.raise_for_status()

            # Determine file mode: append (206) or overwrite (200)
            mode = 'ab' if response.status_code == 206 else 'wb'
            if mode == 'wb':
                # Server doesn't support Range or no Range sent
                resume_pos = 0
                md5_hash = hashlib.md5()

            total_size = int(response.headers.get('content-length', 0)) + resume_pos
            downloaded = resume_pos
            last_progress = 0

            # Stream to disk with progress tracking
            async with aiofiles.open(dest_path, mode) as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    await f.write(chunk)
                    md5_hash.update(chunk)  # Incremental MD5
                    downloaded += len(chunk)

                    # Report progress every 5%
                    progress_pct = (downloaded * 100) // total_size
                    if progress_pct >= last_progress + 5:
                        await progress_callback(progress_pct)
                        last_progress = progress_pct

                        # Persist state every 1MB for crash recovery
                        if downloaded % (1024 * 1024) < 8192:
                            await save_state(url, downloaded, expected_md5)

    # Verify MD5 after download completes
    computed_md5 = md5_hash.hexdigest()
    if computed_md5 != expected_md5:
        dest_path.unlink()
        raise MD5MismatchError(expected=expected_md5, actual=computed_md5)
```

**Key Decisions**:

1. **Chunk size: 8192 bytes** - Optimal balance between throughput and progress granularity
2. **Read timeout: 300s** - Allow 5 minutes for large chunks on slow networks
3. **Incremental MD5** - Compute hash during streaming (single-pass, memory efficient)
4. **State persistence: Every 1MB** - Balance between crash recovery and I/O overhead
5. **HTTP 416 handling** - Delete partial file and restart (server file changed)
6. **Mode selection** - Use `ab` for 206 Partial Content, `wb` for 200 OK

**Rationale**:
- Memory efficiency: <2MB peak RAM (8KB chunks + httpx buffers)
- Crash resilience: State saved every 1MB allows resume after power failure
- Network resilience: Exponential backoff for transient errors (FR-003)
- Single-pass MD5: No need to re-read file after download (saves time + disk I/O)

---

## 10. systemd Service Configuration

### Decision: Simple service type with auto-restart and resource limits

**systemd Unit File**:
```ini
[Unit]
Description=TOPE OTA Updater Service
Documentation=https://github.com/tope/updater
After=network-online.target
Wants=network-online.target
# Ensure device-api can be restarted by updater
Conflicts=

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/tope/updater
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 -m updater.main
Restart=always
RestartSec=10
StartLimitBurst=5
StartLimitIntervalSec=300

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=tope-updater

# Resource limits (FR-009 - resource protection)
LimitNOFILE=1024
MemoryMax=100M
CPUQuota=50%

# Security hardening (while running as root)
PrivateTmp=yes
NoNewPrivileges=no
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/opt/tope/updater/tmp /opt/tope/updater/logs /opt/tope/updater/backups
ReadWritePaths=/opt/tope /usr/bin /usr/local/bin
# Allow process control and file deployment
CapabilityBoundingSet=CAP_KILL CAP_FOWNER CAP_CHOWN CAP_DAC_OVERRIDE

# Graceful shutdown (FR-030)
TimeoutStopSec=30
KillMode=mixed
KillSignal=SIGTERM

[Install]
WantedBy=multi-user.target
```

**Key Decisions**:

1. **Type=simple** - Python script runs in foreground (uvicorn doesn't daemonize)
2. **User=root** - Required for process control (SIGTERM/SIGKILL) and file deployment to /usr/bin, /opt/tope
3. **After=network-online.target** - Wait for network before starting (downloads require connectivity)
4. **Restart=always** - Auto-restart on failure (critical service for OTA)
5. **MemoryMax=100M** - Hard limit (SC-009 requires <50MB peak, 100M gives headroom)
6. **TimeoutStopSec=30** - Allow 30s for graceful shutdown (cancel background tasks)
7. **ProtectSystem=strict** - Read-only /usr, /boot; write access only to specified paths
8. **CapabilityBoundingSet** - Minimal capabilities for process control and file ops

**Rationale**:
- Reliability: Auto-restart ensures service survives crashes
- Security: Capability restrictions limit root damage if compromised
- Resource protection: Memory/CPU limits prevent runaway resource consumption
- Graceful shutdown: SIGTERM + timeout allows cancelling downloads cleanly

**Installation Commands**:
```bash
# Install service unit
sudo cp deploy/tope-updater.service /etc/systemd/system/
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable tope-updater

# Start service
sudo systemctl start tope-updater

# Check status
sudo systemctl status tope-updater
journalctl -u tope-updater -f
```

---

**Document Status**: Production-ready | **Last Updated**: 2025-11-26 | **Reviewed**: Pending
