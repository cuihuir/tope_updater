"""E2E test configuration and fixtures."""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
import httpx

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
TEST_DATA_DIR = PROJECT_ROOT / "tests" / "e2e" / "test_data"
TEST_PACKAGES_DIR = TEST_DATA_DIR / "packages"
TMP_DIR = PROJECT_ROOT / "tmp_e2e"
LOGS_DIR = PROJECT_ROOT / "logs_e2e"
BACKUPS_DIR = PROJECT_ROOT / "backups_e2e"

# Constants
UPDATER_PORT = 12315
UPDATER_BASE_URL = f"http://localhost:{UPDATER_PORT}"
PACKAGE_SERVER_PORT = 8080
PACKAGE_SERVER_URL = f"http://localhost:{PACKAGE_SERVER_PORT}"
DEVICE_API_PORT = 9080


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment() -> Generator[None, None, None]:
    """Setup E2E test environment.

    Creates test directories and cleans up after all tests.
    """
    logger.info("Setting up E2E test environment...")

    # Create test directories
    TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
    TEST_PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

    logger.info(f"Test data directory: {TEST_DATA_DIR}")
    logger.info(f"Test packages directory: {TEST_PACKAGES_DIR}")

    yield

    # Cleanup after all tests
    logger.info("Cleaning up E2E test environment...")

    # Clean test directories (optional, comment out to inspect artifacts)
    # shutil.rmtree(TMP_DIR, ignore_errors=True)
    # shutil.rmtree(LOGS_DIR, ignore_errors=True)
    # shutil.rmtree(BACKUPS_DIR, ignore_errors=True)


@pytest.fixture(scope="session")
def mock_servers() -> Generator[dict, None, None]:
    """Start mock servers for testing.

    Yields:
        dict: Server URLs and PIDs
    """
    logger.info("Starting mock servers...")

    servers = {}

    # Start package server
    package_server_script = PROJECT_ROOT / "tests" / "fixtures" / "tests" / "mocks" / "package_server.py"
    if package_server_script.exists():
        proc = subprocess.Popen(
            ["python", str(package_server_script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        servers["package_server"] = {
            "url": PACKAGE_SERVER_URL,
            "port": PACKAGE_SERVER_PORT,
            "pid": proc.pid,
            "process": proc
        }
        logger.info(f"Package server started on port {PACKAGE_SERVER_PORT}")
        time.sleep(1)  # Wait for server to start

    # Start device-api mock
    device_api_script = PROJECT_ROOT / "tests" / "fixtures" / "tests" / "mocks" / "device_api_server.py"
    if device_api_script.exists():
        proc = subprocess.Popen(
            ["python", str(device_api_script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        servers["device_api"] = {
            "url": f"http://localhost:{DEVICE_API_PORT}",
            "port": DEVICE_API_PORT,
            "pid": proc.pid,
            "process": proc
        }
        logger.info(f"Device API mock started on port {DEVICE_API_PORT}")
        time.sleep(1)  # Wait for server to start

    yield servers

    # Stop all servers
    logger.info("Stopping mock servers...")
    for name, server_info in servers.items():
        try:
            server_info["process"].terminate()
            server_info["process"].wait(timeout=5)
            logger.info(f"{name} stopped")
        except Exception as e:
            logger.error(f"Error stopping {name}: {e}")
            try:
                server_info["process"].kill()
            except:
                pass


@pytest.fixture(scope="function")
def updater_service() -> Generator[subprocess.Popen, None, None]:
    """Start/stop updater service for each test.

    Yields:
        subprocess.Popen: The updater process
    """
    logger.info("Starting updater service...")

    # Start updater
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")

    proc = subprocess.Popen(
        ["uv", "run", "python", "-m", "updater.main"],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for service to start
    max_wait = 10  # seconds
    for i in range(max_wait):
        try:
            response = httpx.get(f"{UPDATER_BASE_URL}/api/v1.0/progress", timeout=1)
            logger.info(f"Updater service started (attempt {i+1})")
            break
        except Exception:
            if i < max_wait - 1:
                time.sleep(1)
    else:
        proc.kill()
        proc.wait()
        raise RuntimeError("Updater service failed to start")

    yield proc

    # Stop updater
    logger.info("Stopping updater service...")
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


@pytest.fixture(scope="function")
async def http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide async HTTP client for API calls.

    Yields:
        httpx.AsyncClient: Configured HTTP client
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        yield client


@pytest.fixture
def test_package() -> Path:
    """Provide path to a valid test package.

    Returns:
        Path: Path to test package
    """
    # Check if test package exists
    package_path = PROJECT_ROOT / "test-update-1.0.0.zip"
    if not package_path.exists():
        pytest.skip(f"Test package not found: {package_path}")

    return package_path


def create_test_package(
    version: str,
    dest_dir: Path = TEST_PACKAGES_DIR,
    modules: list = None,
    corrupt: bool = False
) -> Path:
    """Create a test OTA package.

    Args:
        version: Package version
        dest_dir: Destination directory
        modules: List of module dicts (default: single test module)
        corrupt: Create corrupted package for testing error scenarios

    Returns:
        Path: Created package path
    """
    import zipfile
    from updater.utils.verification import compute_md5

    if modules is None:
        modules = [{
            "name": "test-module",
            "src": "bin/test-app",
            "dest": "/tmp/tope-e2e-test/test-app",
            "md5": "098f6bcd4621d373cade4e832627b4f6",
            "size": 4
        }]

    package_path = dest_dir / f"test-update-{version}.zip"

    manifest = {
        "version": version,
        "modules": modules
    }

    with zipfile.ZipFile(package_path, 'w') as zf:
        # Add manifest
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        # Add modules
        for module in modules:
            if corrupt:
                # Write corrupted data
                zf.writestr(module["src"], "corrupted")
            else:
                # Write test data matching MD5
                zf.writestr(module["src"], "test")

    logger.info(f"Created test package: {package_path}")
    return package_path


@pytest.fixture
def sample_test_package() -> Path:
    """Create a sample test package.

    Returns:
        Path: Path to created test package
    """
    return create_test_package("1.0.0")


def cleanup_state_file():
    """Remove state.json file to reset state between tests."""
    state_file = PROJECT_ROOT / "state.json"
    if state_file.exists():
        state_file.unlink()
        logger.info("Removed state.json")


@pytest.fixture(autouse=True)
def reset_state() -> Generator[None, None, None]:
    """Reset state before and after each test."""
    cleanup_state_file()
    yield
    cleanup_state_file()


async def wait_for_stage(
    client: httpx.AsyncClient,
    target_stage: str,
    timeout: float = 60.0,
    interval: float = 0.5
) -> dict:
    """Wait for updater to reach a specific stage.

    Args:
        client: HTTP client
        target_stage: Target stage (e.g., "IDLE", "SUCCESS")
        timeout: Maximum wait time in seconds
        interval: Polling interval in seconds

    Returns:
        dict: Final status response

    Raises:
        TimeoutError: If timeout reached
    """
    start_time = time.time()

    while (time.time() - start_time) < timeout:
        try:
            response = await client.get(f"{UPDATER_BASE_URL}/api/v1.0/progress")
            response.raise_for_status()
            data = response.json()

            if data["code"] == 200:
                stage = data["data"]["stage"]
                if stage == target_stage:
                    logger.info(f"Reached target stage: {target_stage}")
                    return data["data"]
                elif stage == "FAILED":
                    logger.error(f"Updater failed: {data['data'].get('error')}")
                    return data["data"]

            await asyncio.sleep(interval)
        except Exception as e:
            logger.error(f"Error polling progress: {e}")
            await asyncio.sleep(interval)

    raise TimeoutError(f"Timeout waiting for stage: {target_stage}")


# Export utilities for tests
__all__ = [
    "PROJECT_ROOT",
    "TEST_DATA_DIR",
    "TEST_PACKAGES_DIR",
    "UPDATER_BASE_URL",
    "PACKAGE_SERVER_URL",
    "create_test_package",
    "cleanup_state_file",
    "wait_for_stage",
]
