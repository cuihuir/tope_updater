"""Global pytest fixtures and configuration."""

import asyncio
import json
import sys
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for test files."""
    yield tmp_path


@pytest.fixture
def mock_state_manager():
    """Mock StateManager for unit tests."""
    manager = MagicMock()
    manager.update_status = MagicMock()
    manager.get_status = MagicMock(return_value=MagicMock(
        stage="idle",
        progress=0,
        message="Test",
        error=None
    ))
    return manager


@pytest.fixture
def sample_manifest():
    """Sample manifest.json data."""
    return {
        "version": "1.0.0",
        "modules": [
            {
                "name": "test-module",
                "src": "bin/test-binary",
                "dest": "/opt/tope/bin/test-binary",
                "md5": "d41d8cd98f00b204e9800998ecf8427e",
                "size": 1024,
                "restart_order": 1,
                "process_name": "test-service"
            }
        ]
    }


@pytest.fixture
def sample_package(tmp_path):
    """Sample test package ZIP file."""
    package_path = tmp_path / "test-package.zip"
    with zipfile.ZipFile(package_path, 'w') as zf:
        # Add manifest.json
        manifest = {
            "version": "1.0.0",
            "modules": [
                {
                    "name": "test-module",
                    "src": "bin/test-binary",
                    "dest": "/opt/tope/bin/test-binary",
                    "md5": "d41d8cd98f00b204e9800998ecf8427e",
                    "size": 1024
                }
            ]
        }
        zf.writestr("manifest.json", json.dumps(manifest))

        # Add dummy file
        zf.writestr("bin/test-binary", "test content")

    return package_path
