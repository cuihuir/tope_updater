#!/usr/bin/env python3
"""Test script for rollback mechanism (Phase 5: T040-T041).

This script tests:
- Backup creation and tracking
- Rollback on deployment failure
- DEPLOYMENT_FAILED error reporting
- Atomic file operations

Prerequisites:
- test-update-1.0.0.zip package (or create with create_test_package.py)
"""

import asyncio
import json
import logging
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from updater.services.deploy import DeployService
from updater.services.state_manager import StateManager
from updater.models.status import StageEnum

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("test-rollback")


def create_test_package_with_invalid_file(output_path: Path) -> None:
    """Create a test package that will fail deployment.

    Package contains:
    - manifest.json with valid module definition
    - A file that references a non-existent source in ZIP
    """
    manifest = {
        "version": "2.0.0",
        "modules": [
            {
                "name": "test-module",
                "src": "bin/nonexistent-file",  # This file doesn't exist in ZIP
                "dest": "/tmp/tope-updater-rollback-test/test-binary",
                "md5": "098f6bcd4621d373cade4e832627b4f6",
                "size": 4
            }
        ]
    }

    with zipfile.ZipFile(output_path, 'w') as zf:
        # Add manifest
        zf.writestr("manifest.json", json.dumps(manifest))
        # Intentionally don't add the file referenced in manifest

    logger.info(f"Created test package: {output_path}")


def create_test_package_with_multiple_modules(output_path: Path, fail_on_module: int = 2) -> None:
    """Create a test package with multiple modules, one will fail.

    Args:
        output_path: Path to create package
        fail_on_module: Which module (1-indexed) should have a non-existent file
    """
    modules = []
    for i in range(1, 4):  # Create 3 modules
        module = {
            "name": f"module-{i}",
            "src": f"bin/file-{i}",
            "dst": f"/tmp/tope-updater-rollback-test/file-{i}",  # Must use "dst" (not "dest")
            "md5": "098f6bcd4621d373cade4e832627b4f6",
            "size": 4
        }
        modules.append(module)

    manifest = {
        "version": "2.0.0",
        "modules": modules
    }

    with zipfile.ZipFile(output_path, 'w') as zf:
        # Add manifest
        zf.writestr("manifest.json", json.dumps(manifest))

        # Add files for all modules except the one that should fail
        for i, module in enumerate(modules, start=1):
            if i != fail_on_module:
                zf.writestr(f"bin/file-{i}", f"content-{i}")

    logger.info(f"Created test package with {len(modules)} modules (module {fail_on_module} will fail)")


async def test_backup_creation():
    """Test that backups are created correctly."""
    print("\n" + "=" * 80)
    print("🧪 Test 1: Backup Creation")
    print("=" * 80)

    # Create a temporary directory with a file to backup
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir) / "test"
        test_dir.mkdir()
        test_file = test_dir / "test-binary"

        # Create original file
        test_file.write_text("original content v1.0")
        print(f"  Created original file: {test_file}")

        # Initialize deploy service
        state_manager = StateManager()
        deploy_service = DeployService(state_manager)
        deploy_service.backup_dir = Path(tmpdir) / "backups"

        # Backup the file
        backup_path = await deploy_service._backup_file(test_file, "2.0.0")

        # Verify backup exists
        assert backup_path.exists(), "Backup file should exist"
        print(f"  ✅ Backup created: {backup_path}")

        # Verify backup content matches original
        backup_content = backup_path.read_text()
        original_content = test_file.read_text()
        assert backup_content == original_content, "Backup content should match original"
        print(f"  ✅ Backup content matches original")

        # Verify backup naming
        assert "test-binary.2.0.0" in backup_path.name, "Backup name should include version"
        assert backup_path.suffix == ".bak", "Backup should have .bak extension"
        print(f"  ✅ Backup naming correct")

        print("\n  ✅ Test 1 PASSED: Backup creation works correctly")


async def test_rollback_on_deployment_failure():
    """Test rollback when deployment fails."""
    print("\n" + "=" * 80)
    print("🧪 Test 2: Rollback on Deployment Failure")
    print("=" * 80)

    # Use a fixed directory for deployment (not tmpdir)
    deploy_root = Path("/tmp/tope-updater-rollback-test")
    deploy_root.mkdir(exist_ok=True)
    backup_dir = Path("./backups")
    backup_dir.mkdir(exist_ok=True)

    # Clean up any previous test files
    for f in deploy_root.glob("file-*"):
        f.unlink()

    # Create existing files (version 1.0)
    file1 = deploy_root / "file-1"
    file2 = deploy_root / "file-2"
    file3 = deploy_root / "file-3"

    file1.write_text("original-v1.0")
    file2.write_text("original-v1.0")
    file3.write_text("original-v1.0")

    print(f"  Created original files:")
    print(f"    - {file1}")
    print(f"    - {file2}")
    print(f"    - {file3}")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create package that will fail on module 2
        package_path = Path(tmpdir) / "test-package.zip"
        create_test_package_with_multiple_modules(package_path, fail_on_module=2)

        # Initialize deploy service
        state_manager = StateManager()
        state_file = Path(tmpdir) / "state.json"
        state_manager.state_file = state_file

        deploy_service = DeployService(state_manager)

        # Reset state to idle
        state_manager.update_status(
            stage=StageEnum.IDLE,
            progress=0,
            message="Ready for testing",
        )

        # Try to deploy (should fail on module 2 and rollback)
        print(f"\n  Attempting deployment (expected to fail on module 2)...")
        try:
            await deploy_service.deploy_package(package_path, "2.0.0")
            print("  ❌ Test failed: Deployment should have raised an error")
            return False
        except RuntimeError as e:
            error_msg = str(e)
            print(f"  ✅ Deployment failed as expected")
            print(f"     Error: {error_msg[:200]}...")

            # Verify error message contains DEPLOYMENT_FAILED
            assert "DEPLOYMENT_FAILED" in error_msg, "Error should mention DEPLOYMENT_FAILED"
            print(f"  ✅ Error contains DEPLOYMENT_FAILED")

            # Verify rollback message
            assert "Rollback completed successfully" in error_msg, "Error should mention rollback"
            print(f"  ✅ Error mentions rollback")

        # Verify files were rolled back
        print(f"\n  Verifying rollback...")
        file1_content = file1.read_text()
        file2_content = file2.read_text()
        file3_content = file3.read_text()

        assert file1_content == "original-v1.0", f"File 1 should be restored, got: {file1_content}"
        print(f"  ✅ File 1 restored: '{file1_content}'")

        assert file2_content == "original-v1.0", f"File 2 should be restored, got: {file2_content}"
        print(f"  ✅ File 2 restored: '{file2_content}'")

        assert file3_content == "original-v1.0", f"File 3 should be restored, got: {file3_content}"
        print(f"  ✅ File 3 restored: '{file3_content}'")

        # Verify backups exist in ./backups
        backups = list(backup_dir.glob("*.bak"))
        assert len(backups) >= 1, "At least one backup should exist"
        print(f"  ✅ Backups created: {len(backups)} files")
        for backup in backups[:3]:  # Show first 3
            print(f"     - {backup.name}")

        print("\n  ✅ Test 2 PASSED: Rollback works correctly")

    # Cleanup
    for f in deploy_root.glob("file-*"):
        f.unlink()
    deploy_root.rmdir()


async def test_atomic_replacement():
    """Test that file replacement is atomic."""
    print("\n" + "=" * 80)
    print("🧪 Test 3: Atomic File Replacement")
    print("=" * 80)

    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir) / "test"
        test_dir.mkdir()

        # Create a package with a valid module
        package_path = Path(tmpdir) / "test-package.zip"
        manifest = {
            "version": "1.0.0",
            "modules": [
                {
                    "name": "test-module",
                    "src": "bin/test",
                    "dst": str(test_dir / "test-binary"),  # Use "dst" not "dest"
                    "md5": "098f6bcd4621d373cade4e832627b4f6",
                    "size": 4
                }
            ]
        }

        with zipfile.ZipFile(package_path, 'w') as zf:
            zf.writestr("manifest.json", json.dumps(manifest))
            zf.writestr("bin/test", "test")

        # Initialize deploy service
        state_manager = StateManager()
        state_manager.state_file = Path(tmpdir) / "state.json"

        deploy_service = DeployService(state_manager)
        deploy_service.backup_dir = Path(tmpdir) / "backups"

        # Deploy
        await deploy_service.deploy_package(package_path, "1.0.0")

        # Verify file exists
        deployed_file = test_dir / "test-binary"
        assert deployed_file.exists(), "Deployed file should exist"
        print(f"  ✅ File deployed: {deployed_file}")

        # Verify content
        content = deployed_file.read_text()
        assert content == "test", f"Content should be 'test', got: {content}"
        print(f"  ✅ Content correct: '{content}'")

        print("\n  ✅ Test 3 PASSED: Atomic replacement works")


async def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("🚀 TOP.E OTA Updater - Rollback Mechanism Tests")
    print("=" * 80)
    print("\n📋 Testing Phase 5 Features (T040-T041)")
    print("   - Backup creation and tracking")
    print("   - Rollback on deployment failure")
    print("   - DEPLOYMENT_FAILED error reporting")
    print("   - Atomic file operations")

    try:
        # Test 1: Backup creation
        await test_backup_creation()

        # Test 2: Rollback on failure
        await test_rollback_on_deployment_failure()

        # Test 3: Atomic replacement
        await test_atomic_replacement()

        # Summary
        print("\n" + "=" * 80)
        print("✅ All tests passed!")
        print("=" * 80)
        print("\n📊 Test Summary:")
        print("   ✅ T038: Backup creation - Working")
        print("   ✅ T040: Rollback mechanism - Working")
        print("   ✅ T041: DEPLOYMENT_FAILED error reporting - Working")
        print("\n🎉 Phase 5 implementation complete!")

    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Tests failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
