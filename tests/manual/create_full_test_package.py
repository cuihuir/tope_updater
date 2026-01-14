#!/usr/bin/env python3
"""Create test OTA update package with service management."""

import hashlib
import json
import zipfile
from pathlib import Path

# Create test package structure
test_dir = Path("/home/tope/project_py/tope_updater/test_package_full")
test_dir.mkdir(exist_ok=True)
(test_dir / "modules" / "mock-service").mkdir(parents=True, exist_ok=True)

# Create manifest.json with process_name and restart_order
manifest = {
    "version": "2.0.0",
    "modules": [
        {
            "name": "mock-service",
            "src": "modules/mock-service/mock-app",
            "dst": "/tmp/tope-updater-test/mock-app",
            "process_name": "mock-service",  # For process control testing
            "restart_order": 1
        }
    ]
}
with open(test_dir / "manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)

# Create mock service binary
mock_binary = test_dir / "modules" / "mock-service" / "mock-app"
mock_binary.write_text("""#!/bin/bash
# Mock Service v2.0.0 for OTA testing
# This is a mock service that doesn't actually run as a systemd service
echo "Mock Service v2.0.0"
echo "This would be a real service binary in production"
exit 0
""")
mock_binary.chmod(0o755)

# Create ZIP package
zip_path = Path("/home/tope/project_py/tope_updater/test-update-2.0.0.zip")
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.write(test_dir / "manifest.json", "manifest.json")
    zf.write(mock_binary, "modules/mock-service/mock-app")

# Compute MD5
md5_hash = hashlib.md5()
with open(zip_path, "rb") as f:
    for chunk in iter(lambda: f.read(4096), b""):
        md5_hash.update(chunk)

# Print results
print(f"✅ Full test package created: {zip_path}")
print(f"📦 Size: {zip_path.stat().st_size} bytes")
print(f"🔐 MD5: {md5_hash.hexdigest()}")
print()
print("📋 Manifest contents:")
print(json.dumps(manifest, indent=2))
print()
print("⚠️  Note: This package includes process_name field, but the service")
print("   'mock-service' doesn't actually exist as a systemd service.")
print("   The deployment will attempt to restart it using systemctl.")
