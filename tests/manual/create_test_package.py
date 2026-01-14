#!/usr/bin/env python3
"""Create test OTA update package for deployment testing."""

import hashlib
import json
import zipfile
from pathlib import Path

# Create test package structure
test_dir = Path("/home/tope/project_py/tope_updater/test_package")
test_dir.mkdir(exist_ok=True)
(test_dir / "modules" / "test-app").mkdir(parents=True, exist_ok=True)

# Create manifest.json
manifest = {
    "version": "1.0.0",
    "modules": [
        {
            "name": "test-app",
            "src": "modules/test-app/test-binary",
            "dst": "/tmp/tope-updater-test/test-binary"
        }
    ]
}
with open(test_dir / "manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)

# Create test binary
test_binary = test_dir / "modules" / "test-app" / "test-binary"
test_binary.write_text("""#!/bin/bash
# Test OTA Update Binary v1.0.0
echo "Test application v1.0.0 - OTA Update Test"
echo "Timestamp: $(date)"
exit 0
""")
test_binary.chmod(0o755)

# Create ZIP package
zip_path = Path("/home/tope/project_py/tope_updater/test-update-1.0.0.zip")
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.write(test_dir / "manifest.json", "manifest.json")
    zf.write(test_binary, "modules/test-app/test-binary")

# Compute MD5
md5_hash = hashlib.md5()
with open(zip_path, "rb") as f:
    for chunk in iter(lambda: f.read(4096), b""):
        md5_hash.update(chunk)

# Print results
print(f"✅ Test package created: {zip_path}")
print(f"📦 Size: {zip_path.stat().st_size} bytes")
print(f"🔐 MD5: {md5_hash.hexdigest()}")
print()
print("Test download request:")
print(json.dumps({
    "version": "1.0.0",
    "package_url": f"file://{zip_path}",
    "package_name": "test-update-1.0.0.zip",
    "package_size": zip_path.stat().st_size,
    "package_md5": md5_hash.hexdigest()
}, indent=2))
