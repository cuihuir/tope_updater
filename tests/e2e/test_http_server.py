"""Test HTTP server fixture."""

import pytest
import httpx
from pathlib import Path


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_http_server_serves_packages(
    package_http_server: str,
    sample_test_package: Path,
    http_client: httpx.AsyncClient
):
    """Test that HTTP server can serve test packages."""
    # Construct URL
    package_url = f"{package_http_server}/{sample_test_package.name}"
    print(f"\nTesting HTTP server at: {package_url}")

    # Try to download the package
    response = await http_client.get(package_url)

    print(f"Response status: {response.status_code}")
    print(f"Response headers: {response.headers}")
    print(f"Content length: {len(response.content)}")

    # Verify response
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    # Verify content matches the file
    with open(sample_test_package, "rb") as f:
        expected_content = f.read()

    assert response.content == expected_content, "Downloaded content doesn't match file"
    print("✓ HTTP server successfully serves test packages")
