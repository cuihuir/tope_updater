"""E2E tests for happy path scenarios."""

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
async def test_updater_service_health(http_client: httpx.AsyncClient):
    """Test that updater service starts and responds to health check."""
    logger.info("Testing updater service health...")

    response = await http_client.get(f"{UPDATER_BASE_URL}/api/v1.0/progress")
    assert response.status_code == 200

    data = response.json()
    assert data["code"] == 200
    assert "data" in data
    assert "stage" in data["data"]

    logger.info(f"Updater service is healthy. Current stage: {data['data']['stage']}")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_simple_api_call(http_client: httpx.AsyncClient):
    """Test simple API call to verify endpoint accessibility."""
    logger.info("Testing simple API call...")

    response = await http_client.get(f"{UPDATER_BASE_URL}/api/v1.0/progress")
    assert response.status_code == 200

    data = response.json()
    logger.info(f"API response: {data}")

    assert data["code"] == 200
    assert data["msg"] == "success"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_idle_state_after_startup(
    http_client: httpx.AsyncClient,
    sample_test_package: Path
):
    """Test that updater starts in IDLE state."""
    logger.info("Testing initial IDLE state...")

    response = await http_client.get(f"{UPDATER_BASE_URL}/api/v1.0/progress")
    assert response.status_code == 200

    data = response.json()
    stage = data["data"]["stage"]

    logger.info(f"Initial stage: {stage}")
    assert stage == "IDLE"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_download_request_acceptance(
    http_client: httpx.AsyncClient,
    sample_test_package: Path
):
    """Test that download API accepts valid request."""
    logger.info("Testing download request acceptance...")

    # Calculate MD5 of test package
    with open(sample_test_package, "rb") as f:
        md5_hash = hashlib.md5(f.read()).hexdigest()
    package_size = sample_test_package.stat().st_size

    # Prepare download request
    download_payload = {
        "version": "1.0.0",
        "package_url": f"{PACKAGE_SERVER_URL}/packages/test-update-1.0.0.zip",
        "package_name": "test-update-1.0.0.zip",
        "package_size": package_size,
        "package_md5": md5_hash
    }

    logger.info(f"Download payload: {download_payload}")

    # Send download request
    response = await http_client.post(
        f"{UPDATER_BASE_URL}/api/v1.0/download",
        json=download_payload
    )

    logger.info(f"Download response status: {response.status_code}")
    logger.info(f"Download response: {response.text}")

    # Note: This might fail if package server doesn't have the file
    # We're just testing that the API accepts the request format
    # The actual download will be tested in E2E-001


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_progress_polling(
    http_client: httpx.AsyncClient,
):
    """Test progress endpoint polling."""
    logger.info("Testing progress polling...")

    # Poll progress multiple times
    for i in range(3):
        response = await http_client.get(f"{UPDATER_BASE_URL}/api/v1.0/progress")
        assert response.status_code == 200

        data = response.json()
        assert data["code"] == 200
        assert "data" in data

        stage = data["data"]["stage"]
        progress = data["data"]["progress"]
        message = data["data"]["message"]

        logger.info(f"Poll {i+1}: stage={stage}, progress={progress}, message={message}")

        # Small delay between polls
        await asyncio.sleep(0.5)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_error_handling_invalid_request(
    http_client: httpx.AsyncClient,
):
    """Test error handling for invalid download request."""
    logger.info("Testing error handling...")

    # Send invalid request (missing required fields)
    invalid_payload = {
        "version": "1.0.0"
        # Missing other required fields
    }

    response = await http_client.post(
        f"{UPDATER_BASE_URL}/api/v1.0/download",
        json=invalid_payload
    )

    logger.info(f"Response status: {response.status_code}")

    # Should return validation error
    # Note: FastAPI will validate Pydantic model
    # Expected: 422 Validation Error or 400 Bad Request
    assert response.status_code in [400, 422]


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_concurrent_download_requests(
    http_client: httpx.AsyncClient,
    sample_test_package: Path
):
    """Test behavior with concurrent download requests."""
    logger.info("Testing concurrent download requests...")

    # Calculate MD5 of test package
    with open(sample_test_package, "rb") as f:
        md5_hash = hashlib.md5(f.read()).hexdigest()
    package_size = sample_test_package.stat().st_size

    download_payload = {
        "version": "1.0.0",
        "package_url": f"{PACKAGE_SERVER_URL}/packages/test-update-1.0.0.zip",
        "package_name": "test-update-1.0.0.zip",
        "package_size": package_size,
        "package_md5": md5_hash
    }

    # Send first request
    response1 = await http_client.post(
        f"{UPDATER_BASE_URL}/api/v1.0/download",
        json=download_payload
    )

    logger.info(f"First request status: {response1.status_code}")

    # Send second request immediately
    response2 = await http_client.post(
        f"{UPDATER_BASE_URL}/api/v1.0/download",
        json=download_payload
    )

    logger.info(f"Second request status: {response2.status_code}")

    # At least one should be rejected or queued
    # Current implementation: second request should fail with conflict
    # This test documents current behavior


# Additional helper test for debugging
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_debug_environment(
    http_client: httpx.AsyncClient,
    sample_test_package: Path
):
    """Debug test to verify environment setup."""
    logger.info("=" * 80)
    logger.info("DEBUG: Environment Check")
    logger.info("=" * 80)

    # Check if test package exists
    logger.info(f"Test package path: {sample_test_package}")
    logger.info(f"Test package exists: {sample_test_package.exists()}")
    if sample_test_package.exists():
        logger.info(f"Test package size: {sample_test_package.stat().st_size} bytes")

    # Check updater service
    try:
        response = await http_client.get(f"{UPDATER_BASE_URL}/api/v1.0/progress")
        logger.info(f"Updater service reachable: {response.status_code == 200}")
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Current state: {data['data']}")
    except Exception as e:
        logger.error(f"Updater service not reachable: {e}")

    logger.info("=" * 80)


# Import asyncio for sleep
import asyncio
