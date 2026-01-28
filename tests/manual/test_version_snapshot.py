#!/usr/bin/env python3
"""
端到端测试：版本快照和两级回滚机制

测试场景：
1. 正常升级流程（v1.0.0 → v2.0.0）
2. 符号链接切换验证
3. 回滚到上一版本（模拟部署失败）
4. 回滚到出厂版本（模拟上一版本不健康）
5. 多次升级（v1 → v2 → v3）
6. 版本历史管理

运行方式：
    python tests/manual/test_version_snapshot.py
"""

import asyncio
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List

# 添加 src 到 Python 路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from updater.services.version_manager import VersionManager
from updater.services.deploy import DeployService
from updater.services.state_manager import StateManager
from updater.services.process import ProcessManager
from updater.services.reporter import ReportService
from updater.models.manifest import Manifest, ManifestModule


class TestVersionSnapshot:
    """版本快照和回滚测试套件"""

    def __init__(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="version_test_"))
        self.versions_dir = self.test_dir / "versions"
        self.packages_dir = self.test_dir / "packages"
        self.state_file = self.test_dir / "state.json"

        # 创建测试目录
        self.versions_dir.mkdir(parents=True)
        self.packages_dir.mkdir(parents=True)

        # 初始化服务
        self.version_manager = VersionManager(str(self.versions_dir))
        self.state_manager = StateManager()  # Singleton - 不需要参数
        self.process_manager = ProcessManager()  # Mock - 不实际操作 systemd
        self.reporter = ReportService()  # Mock - 不实际发送 HTTP

        self.deploy_service = DeployService(
            state_manager=self.state_manager,
            process_manager=self.process_manager,
            version_manager=self.version_manager,
            reporter=self.reporter
        )

        self.test_results: List[Dict] = []

    def log(self, message: str, level: str = "INFO"):
        """打印测试日志"""
        prefix = {
            "INFO": "ℹ️ ",
            "SUCCESS": "✅",
            "ERROR": "❌",
            "WARNING": "⚠️ "
        }.get(level, "  ")
        print(f"{prefix} {message}")

    def create_test_package(self, version: str, files: Dict[str, str]) -> Path:
        """
        创建测试包

        Args:
            version: 版本号
            files: 文件内容字典 {相对路径: 内容}

        Returns:
            包文件路径
        """
        package_path = self.packages_dir / f"package_{version}.zip"

        # 创建临时目录
        temp_dir = self.test_dir / f"temp_{version}"
        temp_dir.mkdir(exist_ok=True)

        try:
            # 写入文件
            for rel_path, content in files.items():
                file_path = temp_dir / rel_path
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content)

            # 创建 manifest.json
            manifest = {
                "version": version,
                "modules": [
                    {
                        "name": "test-app",
                        "files": [
                            {
                                "source": rel_path,
                                "destination": f"/opt/tope/services/test-app/{rel_path}",
                                "md5": "dummy_md5"
                            }
                            for rel_path in files.keys()
                        ],
                        "services": ["test-app.service"]
                    }
                ]
            }

            manifest_path = temp_dir / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2))

            # 创建 ZIP 包
            with zipfile.ZipFile(package_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.write(manifest_path, "manifest.json")
                for rel_path in files.keys():
                    file_path = temp_dir / rel_path
                    zf.write(file_path, rel_path)

            self.log(f"创建测试包: {package_path.name} (version={version})")
            return package_path

        finally:
            # 清理临时目录
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def verify_symlink(self, link_name: str, expected_target: str) -> bool:
        """验证符号链接指向"""
        link_path = self.versions_dir / link_name
        if not link_path.exists():
            self.log(f"符号链接不存在: {link_name}", "ERROR")
            return False

        if not link_path.is_symlink():
            self.log(f"不是符号链接: {link_name}", "ERROR")
            return False

        actual_target = link_path.resolve().name
        if actual_target != expected_target:
            self.log(f"符号链接指向错误: {link_name} -> {actual_target} (expected: {expected_target})", "ERROR")
            return False

        self.log(f"符号链接正确: {link_name} -> {actual_target}", "SUCCESS")
        return True

    def verify_version_exists(self, version: str) -> bool:
        """验证版本目录存在"""
        version_dir = self.versions_dir / f"v{version}"
        exists = version_dir.exists() and version_dir.is_dir()

        if exists:
            self.log(f"版本目录存在: v{version}", "SUCCESS")
        else:
            self.log(f"版本目录不存在: v{version}", "ERROR")

        return exists

    async def test_normal_upgrade(self):
        """测试 1: 正常升级流程（v1.0.0 → v2.0.0）"""
        self.log("\n" + "="*60)
        self.log("测试 1: 正常升级流程（v1.0.0 → v2.0.0）")
        self.log("="*60)

        try:
            # 创建 v1.0.0 包
            v1_files = {
                "bin/app": "#!/bin/bash\necho 'Version 1.0.0'\n",
                "config/app.conf": "version=1.0.0\n"
            }
            v1_package = self.create_test_package("1.0.0", v1_files)

            # 部署 v1.0.0
            self.log("部署 v1.0.0...")
            # Note: 实际部署需要 mock systemd，这里只测试版本管理逻辑
            version_dir = self.version_manager.create_version_dir("1.0.0")

            # 模拟文件部署
            for rel_path, content in v1_files.items():
                dest = version_dir / "services" / "test-app" / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content)

            # 提升版本
            self.version_manager.promote_version("1.0.0")

            # 验证符号链接
            assert self.verify_symlink("current", "v1.0.0")
            assert self.verify_version_exists("1.0.0")

            # 创建 v2.0.0 包
            v2_files = {
                "bin/app": "#!/bin/bash\necho 'Version 2.0.0'\n",
                "config/app.conf": "version=2.0.0\n"
            }
            v2_package = self.create_test_package("2.0.0", v2_files)

            # 部署 v2.0.0
            self.log("部署 v2.0.0...")
            version_dir = self.version_manager.create_version_dir("2.0.0")

            # 模拟文件部署
            for rel_path, content in v2_files.items():
                dest = version_dir / "services" / "test-app" / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content)

            # 提升版本
            self.version_manager.promote_version("2.0.0")

            # 验证符号链接
            assert self.verify_symlink("current", "v2.0.0")
            assert self.verify_symlink("previous", "v1.0.0")
            assert self.verify_version_exists("2.0.0")

            self.log("测试 1: 通过", "SUCCESS")
            self.test_results.append({"test": "normal_upgrade", "status": "PASS"})

        except Exception as e:
            self.log(f"测试 1: 失败 - {e}", "ERROR")
            self.test_results.append({"test": "normal_upgrade", "status": "FAIL", "error": str(e)})
            raise

    async def test_rollback_to_previous(self):
        """测试 2: 回滚到上一版本"""
        self.log("\n" + "="*60)
        self.log("测试 2: 回滚到上一版本")
        self.log("="*60)

        try:
            # 前置条件：current=v2.0.0, previous=v1.0.0
            current_version = self.version_manager.get_current_version()
            previous_version = self.version_manager.get_previous_version()

            self.log(f"当前版本: {current_version}")
            self.log(f"上一版本: {previous_version}")

            assert current_version == "2.0.0", f"Expected current=2.0.0, got {current_version}"
            assert previous_version == "1.0.0", f"Expected previous=1.0.0, got {previous_version}"

            # 执行回滚
            self.log("执行回滚到上一版本...")
            self.version_manager.rollback_to_previous()

            # 验证符号链接
            assert self.verify_symlink("current", "v1.0.0")

            # 验证版本
            new_current = self.version_manager.get_current_version()
            assert new_current == "1.0.0", f"Expected current=1.0.0 after rollback, got {new_current}"

            self.log("测试 2: 通过", "SUCCESS")
            self.test_results.append({"test": "rollback_to_previous", "status": "PASS"})

        except Exception as e:
            self.log(f"测试 2: 失败 - {e}", "ERROR")
            self.test_results.append({"test": "rollback_to_previous", "status": "FAIL", "error": str(e)})
            raise

    async def test_factory_version(self):
        """测试 3: 出厂版本管理"""
        self.log("\n" + "="*60)
        self.log("测试 3: 出厂版本管理")
        self.log("="*60)

        try:
            # 创建出厂版本（基于 v1.0.0）
            self.log("创建出厂版本...")

            # 先回到 v1.0.0
            self.version_manager.promote_version("1.0.0")

            # 创建出厂版本
            factory_dir = self.version_manager.create_factory_version("1.0.0")

            # 验证符号链接
            assert self.verify_symlink("factory", "v1.0.0")

            # 验证出厂版本
            factory_version = self.version_manager.get_factory_version()
            assert factory_version == "1.0.0", f"Expected factory=1.0.0, got {factory_version}"

            self.log("测试 3: 通过", "SUCCESS")
            self.test_results.append({"test": "factory_version", "status": "PASS"})

        except Exception as e:
            self.log(f"测试 3: 失败 - {e}", "ERROR")
            self.test_results.append({"test": "factory_version", "status": "FAIL", "error": str(e)})
            raise

    async def test_rollback_to_factory(self):
        """测试 4: 回滚到出厂版本"""
        self.log("\n" + "="*60)
        self.log("测试 4: 回滚到出厂版本")
        self.log("="*60)

        try:
            # 前置条件：current=v1.0.0, factory=v1.0.0
            # 先升级到 v2.0.0
            self.version_manager.promote_version("2.0.0")
            assert self.verify_symlink("current", "v2.0.0")

            # 执行回滚到出厂版本
            self.log("执行回滚到出厂版本...")
            self.version_manager.rollback_to_factory()

            # 验证符号链接
            assert self.verify_symlink("current", "v1.0.0")

            # 验证版本
            current_version = self.version_manager.get_current_version()
            assert current_version == "1.0.0", f"Expected current=1.0.0 after factory rollback, got {current_version}"

            self.log("测试 4: 通过", "SUCCESS")
            self.test_results.append({"test": "rollback_to_factory", "status": "PASS"})

        except Exception as e:
            self.log(f"测试 4: 失败 - {e}", "ERROR")
            self.test_results.append({"test": "rollback_to_factory", "status": "FAIL", "error": str(e)})
            raise

    async def test_multiple_upgrades(self):
        """测试 5: 多次升级（v1 → v2 → v3）"""
        self.log("\n" + "="*60)
        self.log("测试 5: 多次升级（v1 → v2 → v3）")
        self.log("="*60)

        try:
            # 创建 v3.0.0 包
            v3_files = {
                "bin/app": "#!/bin/bash\necho 'Version 3.0.0'\n",
                "config/app.conf": "version=3.0.0\n"
            }
            v3_package = self.create_test_package("3.0.0", v3_files)

            # 部署 v3.0.0
            self.log("部署 v3.0.0...")
            version_dir = self.version_manager.create_version_dir("3.0.0")

            # 模拟文件部署
            for rel_path, content in v3_files.items():
                dest = version_dir / "services" / "test-app" / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content)

            # 提升版本
            self.version_manager.promote_version("3.0.0")

            # 验证符号链接
            assert self.verify_symlink("current", "v3.0.0")
            assert self.verify_symlink("previous", "v1.0.0")  # previous 应该是之前的 current
            assert self.verify_version_exists("3.0.0")

            # 验证版本历史
            available_versions = self.version_manager.list_versions()
            self.log(f"可用版本: {available_versions}")

            self.log("测试 5: 通过", "SUCCESS")
            self.test_results.append({"test": "multiple_upgrades", "status": "PASS"})

        except Exception as e:
            self.log(f"测试 5: 失败 - {e}", "ERROR")
            self.test_results.append({"test": "multiple_upgrades", "status": "FAIL", "error": str(e)})
            raise

    async def test_version_cleanup(self):
        """测试 6: 版本历史管理（清理旧版本）"""
        self.log("\n" + "="*60)
        self.log("测试 6: 版本历史管理")
        self.log("="*60)

        try:
            # 列出所有版本
            all_versions = self.version_manager.list_versions()
            self.log(f"所有版本: {all_versions}")

            # 验证版本数量（应该有 v1.0.0, v2.0.0, v3.0.0）
            assert len(all_versions) >= 3, f"Expected at least 3 versions, got {len(all_versions)}"

            # 删除旧版本（v2.0.0）
            self.log("删除旧版本 v2.0.0...")
            self.version_manager.delete_version("2.0.0")

            # 验证版本已删除
            remaining_versions = self.version_manager.list_versions()
            self.log(f"剩余版本: {remaining_versions}")
            assert "2.0.0" not in remaining_versions, "v2.0.0 should be deleted"

            self.log("测试 6: 通过", "SUCCESS")
            self.test_results.append({"test": "version_cleanup", "status": "PASS"})

        except Exception as e:
            self.log(f"测试 6: 失败 - {e}", "ERROR")
            self.test_results.append({"test": "version_cleanup", "status": "FAIL", "error": str(e)})
            raise

    def print_summary(self):
        """打印测试总结"""
        self.log("\n" + "="*60)
        self.log("测试总结")
        self.log("="*60)

        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r["status"] == "PASS")
        failed = total - passed

        self.log(f"总测试数: {total}")
        self.log(f"通过: {passed}", "SUCCESS")
        if failed > 0:
            self.log(f"失败: {failed}", "ERROR")

        for result in self.test_results:
            status_icon = "✅" if result["status"] == "PASS" else "❌"
            self.log(f"{status_icon} {result['test']}: {result['status']}")
            if "error" in result:
                self.log(f"   错误: {result['error']}", "ERROR")

        self.log(f"\n测试目录: {self.test_dir}")
        self.log("可以手动检查版本目录结构")

    async def run_all_tests(self):
        """运行所有测试"""
        try:
            await self.test_normal_upgrade()
            await self.test_rollback_to_previous()
            await self.test_factory_version()
            await self.test_rollback_to_factory()
            await self.test_multiple_upgrades()
            await self.test_version_cleanup()
        finally:
            self.print_summary()

    def cleanup(self):
        """清理测试目录"""
        if self.test_dir.exists():
            self.log(f"\n清理测试目录: {self.test_dir}")
            shutil.rmtree(self.test_dir)


async def main():
    """主函数"""
    test_suite = TestVersionSnapshot()

    try:
        await test_suite.run_all_tests()
    except KeyboardInterrupt:
        print("\n\n测试被中断")
    except Exception as e:
        print(f"\n\n测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 询问是否清理
        try:
            response = input("\n是否清理测试目录？(y/N): ").strip().lower()
            if response == 'y':
                test_suite.cleanup()
            else:
                print(f"测试目录保留: {test_suite.test_dir}")
        except (EOFError, KeyboardInterrupt):
            # 非交互环境或用户中断 - 保留测试目录
            print(f"\n测试目录保留: {test_suite.test_dir}")


if __name__ == "__main__":
    asyncio.run(main())
