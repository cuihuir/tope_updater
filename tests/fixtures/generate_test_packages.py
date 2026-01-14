"""Generate test packages for testing."""

import hashlib
import json
import zipfile
from pathlib import Path


def calculate_md5(content: str | bytes) -> str:
    """Calculate MD5 hash of content."""
    if isinstance(content, str):
        content = content.encode('utf-8')
    return hashlib.md5(content).hexdigest()


def create_valid_package(output_path: Path, version: str = "1.0.0"):
    """Create a valid test package."""
    test_content = "test"
    manifest = {
        "version": version,
        "modules": [
            {
                "name": "test-module",
                "src": "bin/test-binary",
                "dest": "/opt/tope/bin/test-binary",
                "md5": calculate_md5(test_content),  # MD5 of "test"
                "size": len(test_content),
                "restart_order": 1,
                "process_name": "test-service"
            }
        ]
    }

    with zipfile.ZipFile(output_path, 'w') as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("bin/test-binary", test_content)

    print(f"✅ Created: {output_path}")


def create_invalid_md5_package(output_path: Path):
    """Create package with wrong MD5."""
    test_content = "test"
    manifest = {
        "version": "1.0.0",
        "modules": [
            {
                "name": "test-module",
                "src": "bin/test-binary",
                "dest": "/opt/tope/bin/test-binary",
                "md5": "wrongmd5hash12345678901234567890",  # Invalid MD5
                "size": len(test_content)
            }
        ]
    }

    with zipfile.ZipFile(output_path, 'w') as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("bin/test-binary", test_content)

    print(f"✅ Created: {output_path} (invalid MD5)")


def create_path_traversal_package(output_path: Path):
    """Create package with path traversal attack."""
    test_content = "test"
    manifest = {
        "version": "1.0.0",
        "modules": [
            {
                "name": "evil-module",
                "src": "bin/../../etc/passwd",  # Path traversal
                "dest": "/opt/tope/bin/evil",
                "md5": calculate_md5(test_content),
                "size": len(test_content)
            }
        ]
    }

    with zipfile.ZipFile(output_path, 'w') as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("bin/../../etc/passwd", test_content)

    print(f"✅ Created: {output_path} (path traversal)")


def create_oversized_package(output_path: Path):
    """Create package with mismatched size."""
    test_content = "test"
    manifest = {
        "version": "1.0.0",
        "modules": [
            {
                "name": "test-module",
                "src": "bin/test-binary",
                "dest": "/opt/tope/bin/test-binary",
                "md5": calculate_md5(test_content),
                "size": 999999  # Wrong size
            }
        ]
    }

    with zipfile.ZipFile(output_path, 'w') as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("bin/test-binary", test_content)

    print(f"✅ Created: {output_path} (oversized)")


if __name__ == "__main__":
    fixtures_dir = Path(__file__).parent

    print("🔧 Generating test packages...")

    create_valid_package(fixtures_dir / "packages" / "valid-1.0.0.zip")
    create_invalid_md5_package(fixtures_dir / "packages" / "invalid-md5.zip")
    create_path_traversal_package(fixtures_dir / "packages" / "path-traversal.zip")
    create_oversized_package(fixtures_dir / "packages" / "oversized.zip")

    print("\n✅ All test packages generated!")
