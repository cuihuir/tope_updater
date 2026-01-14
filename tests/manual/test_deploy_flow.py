#!/usr/bin/env python3
"""Integration test for deployment flow: 解压/停服/备份/替换/启动服务/检查/report成功"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from updater.services.deploy import DeployService
from updater.services.state_manager import StateManager
from updater.models.status import StageEnum

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


async def test_deployment_flow():
    """Test complete deployment flow with test package."""

    print("=" * 80)
    print("🧪 Testing OTA Deployment Flow")
    print("=" * 80)
    print()

    # Setup
    package_path = Path("/home/tope/project_py/tope_updater/test-update-1.0.0.zip")
    version = "1.0.0"

    if not package_path.exists():
        print(f"❌ Test package not found: {package_path}")
        print("Run create_test_package.py first!")
        return False

    print(f"📦 Test Package: {package_path}")
    print(f"🔖 Version: {version}")
    print(f"📏 Size: {package_path.stat().st_size} bytes")
    print()

    # Initialize services
    state_manager = StateManager()
    deploy_service = DeployService(state_manager)

    # Reset state to idle
    state_manager.update_status(
        stage=StageEnum.IDLE,
        progress=0,
        message="Ready for testing",
    )

    print("📋 Test Phases:")
    print("  1️⃣  解压 (Extract) - Extract ZIP and parse manifest.json")
    print("  2️⃣  停服 (Stop services) - Currently skipped (no process_name in test manifest)")
    print("  3️⃣  备份 (Backup) - Backup existing files if present")
    print("  4️⃣  替换 (Replace) - Atomic file deployment (temp → rename)")
    print("  5️⃣  启动服务 (Start services) - Currently skipped (no process_name)")
    print("  6️⃣  检查 (Verify) - Check deployed files exist")
    print("  7️⃣  Report成功 (Report success) - Update stage to SUCCESS")
    print()

    try:
        print("-" * 80)
        print("🚀 Starting deployment test...")
        print("-" * 80)
        print()

        # Call deployment service
        await deploy_service.deploy_package(package_path, version)

        print()
        print("-" * 80)
        print("✅ Deployment completed successfully!")
        print("-" * 80)
        print()

        # Check final state
        final_status = state_manager.get_status()
        print("📊 Final Status:")
        print(f"  Stage: {final_status.stage.value}")
        print(f"  Progress: {final_status.progress}%")
        print(f"  Message: {final_status.message}")
        print(f"  Error: {final_status.error or 'None'}")
        print()

        # Verify deployed file
        deployed_file = Path("/tmp/tope-updater-test/test-binary")
        if deployed_file.exists():
            print(f"✅ Deployed file exists: {deployed_file}")
            print(f"   Size: {deployed_file.stat().st_size} bytes")
            print(f"   Permissions: {oct(deployed_file.stat().st_mode)[-3:]}")
            print()
            print("   Content preview:")
            content = deployed_file.read_text()
            for line in content.split('\n')[:5]:
                print(f"   {line}")
        else:
            print(f"❌ Deployed file NOT found: {deployed_file}")
            return False

        # Check backup
        backup_dir = Path("./backups")
        if backup_dir.exists():
            backups = list(backup_dir.glob("*.bak"))
            if backups:
                print()
                print(f"💾 Backups created: {len(backups)}")
                for backup in backups:
                    print(f"   - {backup.name}")

        print()
        print("=" * 80)
        print("🎉 All deployment phases completed successfully!")
        print("=" * 80)

        return True

    except Exception as e:
        print()
        print("-" * 80)
        print(f"❌ Deployment failed: {e}")
        print("-" * 80)

        import traceback
        traceback.print_exc()

        final_status = state_manager.get_status()
        print()
        print("📊 Final Status:")
        print(f"  Stage: {final_status.stage.value}")
        print(f"  Progress: {final_status.progress}%")
        print(f"  Message: {final_status.message}")
        print(f"  Error: {final_status.error or 'None'}")

        return False


if __name__ == "__main__":
    result = asyncio.run(test_deployment_flow())
    sys.exit(0 if result else 1)
