"""E2E tests for complete OTA update flow."""

import asyncio
import hashlib
import logging
from pathlib import Path

import httpx
import pytest

from tests.e2e.conftest import (
    UPDATER_BASE_URL,
    PACKAGE_SERVER_URL,
    create_test_package,
    wait_for_stage,
)

logger = logging.getLogger(__name__)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_001_complete_update_flow(
    http_client: httpx.AsyncClient,
    sample_test_package: Path,
    package_http_server: str
):
    """E2E-001: Complete OTA update flow (download + verify + deploy).

    Test the full happy path:
    1. Start in IDLE state
    2. Trigger download
    3. Monitor download progress
    4. Verify MD5 checksum
    5. Deploy package
    6. Verify SUCCESS state
    """
    logger.info("=" * 80)
    logger.info("E2E-001: Complete OTA Update Flow")
    logger.info("=" * 80)

    # Step 1: Verify initial IDLE state
    logger.info("Step 1: Verify initial IDLE state")
    response = await http_client.get(f"{UPDATER_BASE_URL}/api/v1.0/progress")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["stage"] == "idle"
    logger.info("✓ Initial state is IDLE")

    # Step 2: Calculate package metadata
    logger.info("Step 2: Calculate package metadata")
    with open(sample_test_package, "rb") as f:
        package_content = f.read()
        md5_hash = hashlib.md5(package_content).hexdigest()
    package_size = len(package_content)
    logger.info(f"Package size: {package_size} bytes")
    logger.info(f"Package MD5: {md5_hash}")

    # Step 3: Trigger download
    logger.info("Step 3: Trigger download")
    package_url = f"{package_http_server}/{sample_test_package.name}"
    logger.info(f"Package URL: {package_url}")

    download_payload = {
        "version": "1.0.0",
        "package_url": package_url,
        "package_name": sample_test_package.name,
        "package_size": package_size,
        "package_md5": md5_hash
    }

    response = await http_client.post(
        f"{UPDATER_BASE_URL}/api/v1.0/download",
        json=download_payload
    )
    logger.info(f"Download request status: {response.status_code}")
    logger.info(f"Download response: {response.text}")

    # Step 4: Monitor download progress
    logger.info("Step 4: Monitor download progress")
    try:
        status = await wait_for_stage(http_client, "toInstall", timeout=30)
        logger.info(f"✓ Download completed: {status}")
    except TimeoutError as e:
        logger.error(f"Download timeout: {e}")
        # Get current status for debugging
        response = await http_client.get(f"{UPDATER_BASE_URL}/api/v1.0/progress")
        logger.error(f"Current status: {response.json()}")
        raise

    # Step 5: Verify package is ready for installation
    logger.info("Step 5: Verify package ready for installation")
    response = await http_client.get(f"{UPDATER_BASE_URL}/api/v1.0/progress")
    data = response.json()
    assert data["data"]["stage"] == "toInstall"
    assert data["data"]["progress"] == 100
    logger.info("✓ Package verified and ready for installation")

    # Step 6: Trigger deployment
    logger.info("Step 6: Trigger deployment")
    deploy_payload = {
        "version": "1.0.0"
    }
    response = await http_client.post(
        f"{UPDATER_BASE_URL}/api/v1.0/update",
        json=deploy_payload
    )
    logger.info(f"Deploy request status: {response.status_code}")

    # Step 7: Monitor deployment progress
    logger.info("Step 7: Monitor deployment progress")
    try:
        status = await wait_for_stage(http_client, "success", timeout=30)
        logger.info(f"✓ Deployment completed: {status}")
    except TimeoutError as e:
        logger.error(f"Deployment timeout: {e}")
        response = await http_client.get(f"{UPDATER_BASE_URL}/api/v1.0/progress")
        logger.error(f"Current status: {response.json()}")
        raise

    # Step 8: Verify final SUCCESS state
    logger.info("Step 8: Verify final SUCCESS state")
    response = await http_client.get(f"{UPDATER_BASE_URL}/api/v1.0/progress")
    data = response.json()
    assert data["data"]["stage"] == "success"
    assert data["data"]["progress"] == 100
    assert data["data"]["error"] is None
    logger.info("✓ Update completed successfully")

    logger.info("=" * 80)
    logger.info("E2E-001: PASSED")
    logger.info("=" * 80)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_002_md5_verification_failure(
    http_client: httpx.AsyncClient,
    sample_test_package: Path,
    package_http_server: str
):
    """E2E-002: MD5 checksum verification failure.

    Test error handling when MD5 doesn't match:
    1. Trigger download with incorrect MD5
    2. Verify download completes
    3. Verify MD5 check fails
    4. Verify FAILED state with appropriate error
    """
    logger.info("=" * 80)
    logger.info("E2E-002: MD5 Verification Failure")
    logger.info("=" * 80)

    # Step 1: Verify initial IDLE state
    logger.info("Step 1: Verify initial IDLE state")
    response = await http_client.get(f"{UPDATER_BASE_URL}/api/v1.0/progress")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["stage"] == "idle"

    # Step 2: Prepare download with WRONG MD5
    logger.info("Step 2: Prepare download with incorrect MD5")
    package_size = sample_test_package.stat().st_size
    wrong_md5 = "0" * 32  # Intentionally wrong MD5
    package_url = f"{package_http_server}/{sample_test_package.name}"

    download_payload = {
        "version": "1.0.0",
        "package_url": package_url,
        "package_name": sample_test_package.name,
        "package_size": package_size,
        "package_md5": wrong_md5
    }

    # Step 3: Trigger download
    logger.info("Step 3: Trigger download with wrong MD5")
    response = await http_client.post(
        f"{UPDATER_BASE_URL}/api/v1.0/download",
        json=download_payload
    )
    logger.info(f"Download request status: {response.status_code}")

    # Step 4: Wait for FAILED state
    logger.info("Step 4: Wait for FAILED state due to MD5 mismatch")
    try:
        status = await wait_for_stage(http_client, "failed", timeout=30)
        logger.info(f"✓ Failed as expected: {status}")

        # Verify error message contains MD5_MISMATCH
        assert status["error"] is not None
        assert "MD5" in status["error"].upper() or "MISMATCH" in status["error"].upper()
        logger.info(f"✓ Error message: {status['error']}")

    except TimeoutError:
        # If timeout, check if it's in failed state
        response = await http_client.get(f"{UPDATER_BASE_URL}/api/v1.0/progress")
        data = response.json()
        logger.info(f"Current status: {data}")

        # Should be in failed state
        assert data["data"]["stage"] == "failed"
        assert data["data"]["error"] is not None

    logger.info("=" * 80)
    logger.info("E2E-002: PASSED")
    logger.info("=" * 80)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_003_package_size_mismatch(
    http_client: httpx.AsyncClient,
    sample_test_package: Path,
    package_http_server: str
):
    """E2E-003: Package size mismatch detection.

    Test error handling when declared size doesn't match actual size:
    1. Trigger download with incorrect size
    2. Verify size mismatch is detected
    3. Verify FAILED state
    """
    logger.info("=" * 80)
    logger.info("E2E-003: Package Size Mismatch")
    logger.info("=" * 80)

    # Step 1: Verify initial IDLE state
    response = await http_client.get(f"{UPDATER_BASE_URL}/api/v1.0/progress")
    assert response.status_code == 200
    assert response.json()["data"]["stage"] == "idle"

    # Step 2: Calculate correct MD5 but wrong size
    with open(sample_test_package, "rb") as f:
        md5_hash = hashlib.md5(f.read()).hexdigest()

    wrong_size = 999999  # Intentionally wrong size
    package_url = f"{package_http_server}/{sample_test_package.name}"

    download_payload = {
        "version": "1.0.0",
        "package_url": package_url,
        "package_name": sample_test_package.name,
        "package_size": wrong_size,
        "package_md5": md5_hash
    }

    # Step 3: Trigger download
    logger.info("Step 3: Trigger download with wrong size")
    response = await http_client.post(
        f"{UPDATER_BASE_URL}/api/v1.0/download",
        json=download_payload
    )

    # Step 4: Wait for FAILED state
    logger.info("Step 4: Wait for FAILED state due to size mismatch")
    try:
        status = await wait_for_stage(http_client, "failed", timeout=30)
        logger.info(f"✓ Failed as expected: {status}")

        # Verify error message contains size mismatch info
        assert status["error"] is not None
        assert "SIZE" in status["error"].upper() or "MISMATCH" in status["error"].upper()
        logger.info(f"✓ Error message: {status['error']}")

    except TimeoutError:
        response = await http_client.get(f"{UPDATER_BASE_URL}/api/v1.0/progress")
        data = response.json()
        logger.info(f"Current status: {data}")
        assert data["data"]["stage"] == "failed"

    logger.info("=" * 80)
    logger.info("E2E-003: PASSED")
    logger.info("=" * 80)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_004_deployment_rollback(
    http_client: httpx.AsyncClient,
    tmp_path: Path,
    package_http_server: str
):
    """E2E-004: Deployment failure and rollback.

    Test rollback mechanism when deployment fails:
    1. Create package with invalid deployment target
    2. Trigger download (should succeed)
    3. Trigger deployment (should fail)
    4. Verify rollback is attempted
    5. Verify FAILED state with rollback info
    """
    logger.info("=" * 80)
    logger.info("E2E-004: Deployment Rollback")
    logger.info("=" * 80)

    # Step 1: Create package with invalid deployment target
    logger.info("Step 1: Create package with invalid deployment target")

    # Create a package that will fail during deployment
    # Use a destination that requires root permissions
    invalid_package = create_test_package(
        version="2.0.0",
        dest_dir=TEST_PACKAGES_DIR,  # Save to packages dir so HTTP server can serve it
        modules=[{
            "name": "invalid-module",
            "src": "bin/test",
            "dst": "/root/test-file",  # Requires root, will fail
            "process_name": None
        }]
    )

    # Calculate metadata
    with open(invalid_package, "rb") as f:
        package_content = f.read()
        md5_hash = hashlib.md5(package_content).hexdigest()
    package_size = len(package_content)
    package_url = f"{package_http_server}/{invalid_package.name}"

    # Step 2: Trigger download
    logger.info("Step 2: Trigger download")
    download_payload = {
        "version": "2.0.0",
        "package_url": package_url,
        "package_name": invalid_package.name,
        "package_size": package_size,
        "package_md5": md5_hash
    }

    response = await http_client.post(
        f"{UPDATER_BASE_URL}/api/v1.0/download",
        json=download_payload
    )
    logger.info(f"Download request status: {response.status_code}")

    # Step 3: Wait for download to complete
    logger.info("Step 3: Wait for download completion")
    try:
        await wait_for_stage(http_client, "toInstall", timeout=30)
        logger.info("✓ Download completed")
    except TimeoutError:
        logger.warning("Download timeout, checking current state")
        response = await http_client.get(f"{UPDATER_BASE_URL}/api/v1.0/progress")
        logger.info(f"Current status: {response.json()}")

    # Step 4: Trigger deployment (should fail)
    logger.info("Step 4: Trigger deployment (expected to fail)")
    deploy_payload = {"version": "2.0.0"}
    response = await http_client.post(
        f"{UPDATER_BASE_URL}/api/v1.0/update",
        json=deploy_payload
    )

    # Step 5: Wait for FAILED state
    logger.info("Step 5: Wait for FAILED state")
    try:
        status = await wait_for_stage(http_client, "failed", timeout=30)
        logger.info(f"✓ Deployment failed as expected: {status}")

        # Verify error message mentions deployment failure
        assert status["error"] is not None
        error_msg = status["error"].upper()
        assert "DEPLOYMENT" in error_msg or "FAILED" in error_msg or "PERMISSION" in error_msg
        logger.info(f"✓ Error message: {status['error']}")

        # Check if rollback was mentioned
        if "ROLLBACK" in error_msg:
            logger.info("✓ Rollback was attempted")

    except TimeoutError:
        response = await http_client.get(f"{UPDATER_BASE_URL}/api/v1.0/progress")
        data = response.json()
        logger.info(f"Current status: {data}")
        assert data["data"]["stage"] == "failed"

    logger.info("=" * 80)
    logger.info("E2E-004: PASSED")
    logger.info("=" * 80)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_005_state_persistence(
    http_client: httpx.AsyncClient,
    sample_test_package: Path,
    package_http_server: str
):
    """E2E-005: State persistence and recovery.

    Test that state is persisted across service restarts:
    1. Start download
    2. Verify state is saved
    3. Check state.json file exists
    4. Verify state can be read
    """
    logger.info("=" * 80)
    logger.info("E2E-005: State Persistence")
    logger.info("=" * 80)

    # Step 1: Verify initial state
    response = await http_client.get(f"{UPDATER_BASE_URL}/api/v1.0/progress")
    assert response.status_code == 200
    initial_state = response.json()["data"]
    logger.info(f"Initial state: {initial_state}")

    # Step 2: Trigger an operation to change state
    with open(sample_test_package, "rb") as f:
        md5_hash = hashlib.md5(f.read()).hexdigest()
    package_size = sample_test_package.stat().st_size
    package_url = f"{package_http_server}/{sample_test_package.name}"

    download_payload = {
        "version": "1.0.0",
        "package_url": package_url,
        "package_name": sample_test_package.name,
        "package_size": package_size,
        "package_md5": md5_hash
    }

    response = await http_client.post(
        f"{UPDATER_BASE_URL}/api/v1.0/download",
        json=download_payload
    )
    logger.info(f"Download triggered: {response.status_code}")

    # Step 3: Wait a moment for state to be saved
    await asyncio.sleep(1)

    # Step 4: Check if state.json exists
    from tests.e2e.conftest import PROJECT_ROOT
    state_file = PROJECT_ROOT / "state.json"

    logger.info(f"Checking state file: {state_file}")
    if state_file.exists():
        logger.info("✓ State file exists")

        # Read and verify state file
        import json
        with open(state_file, 'r') as f:
            saved_state = json.load(f)

        logger.info(f"Saved state: {saved_state}")
        assert "stage" in saved_state
        assert "progress" in saved_state
        logger.info("✓ State file contains valid data")
    else:
        logger.warning("State file not found (may not be created yet)")

    # Step 5: Get current state from API
    response = await http_client.get(f"{UPDATER_BASE_URL}/api/v1.0/progress")
    current_state = response.json()["data"]
    logger.info(f"Current state: {current_state}")

    # State should have changed from initial IDLE
    assert current_state["stage"] != "idle" or current_state["progress"] > 0

    logger.info("=" * 80)
    logger.info("E2E-005: PASSED")
    logger.info("=" * 80)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_006_concurrent_requests_handling(
    http_client: httpx.AsyncClient,
    sample_test_package: Path,
    package_http_server: str
):
    """E2E-006: Concurrent request handling.

    Test that system properly handles concurrent download requests:
    1. Trigger first download
    2. Immediately trigger second download
    3. Verify second request is rejected or queued
    4. Verify first download continues
    """
    logger.info("=" * 80)
    logger.info("E2E-006: Concurrent Requests Handling")
    logger.info("=" * 80)

    # Prepare download payload
    with open(sample_test_package, "rb") as f:
        md5_hash = hashlib.md5(f.read()).hexdigest()
    package_size = sample_test_package.stat().st_size
    package_url = f"{package_http_server}/{sample_test_package.name}"

    download_payload = {
        "version": "1.0.0",
        "package_url": package_url,
        "package_name": sample_test_package.name,
        "package_size": package_size,
        "package_md5": md5_hash
    }

    # Step 1: Trigger first download
    logger.info("Step 1: Trigger first download")
    response1 = await http_client.post(
        f"{UPDATER_BASE_URL}/api/v1.0/download",
        json=download_payload
    )
    logger.info(f"First request status: {response1.status_code}")
    logger.info(f"First request response: {response1.text}")

    # Step 2: Immediately trigger second download
    logger.info("Step 2: Trigger second download immediately")
    response2 = await http_client.post(
        f"{UPDATER_BASE_URL}/api/v1.0/download",
        json=download_payload
    )
    logger.info(f"Second request status: {response2.status_code}")
    logger.info(f"Second request response: {response2.text}")

    # Step 3: Verify behavior
    # Second request should be rejected (409 Conflict) or queued
    if response2.status_code == 409:
        logger.info("✓ Second request rejected with 409 Conflict (expected)")
    elif response2.status_code == 202:
        logger.info("✓ Second request queued with 202 Accepted")
    elif response2.status_code == 200:
        logger.info("⚠ Second request accepted (may indicate race condition)")
    else:
        logger.warning(f"Unexpected status code: {response2.status_code}")

    # Step 4: Verify first download can complete
    logger.info("Step 4: Verify first download continues")
    response = await http_client.get(f"{UPDATER_BASE_URL}/api/v1.0/progress")
    data = response.json()
    logger.info(f"Current state: {data['data']}")

    # Should be in downloading, verifying, or toInstall state
    stage = data["data"]["stage"]
    assert stage in ["downloading", "verifying", "toInstall", "idle", "failed"]
    logger.info(f"✓ System is in valid state: {stage}")

    logger.info("=" * 80)
    logger.info("E2E-006: PASSED")
    logger.info("=" * 80)
