# 测试目录说明

**项目**: tope_updater
**最后更新**: 2026-01-14

---

## 📁 目录结构

```
tests/
├── README.md                    # 本文件
├── conftest.py                  # 全局 pytest fixtures
├── __init__.py
│
├── unit/                        # 单元测试（自动化）
│   ├── test_state_manager.py   # StateManager 单元测试 (9 tests, 96% cov)
│   ├── test_download.py         # DownloadService 单元测试 (7 tests, 94% cov)
│   └── __init__.py
│
├── integration/                 # 集成测试（自动化）
│   └── __init__.py
│
├── contract/                    # 契约测试（自动化）
│   └── __init__.py
│
├── e2e/                        # 端到端测试（自动化）
│   └── __init__.py
│
├── manual/                     # 手动测试脚本
│   ├── test_deploy_flow.py           # 部署流程测试
│   ├── test_full_deploy_flow.py      # 完整部署流程测试
│   ├── test_rollback.py              # 回滚机制测试
│   ├── test_systemd_refactor.py      # systemd 集成测试
│   ├── create_test_package.py        # 生成测试包 v1.0.0
│   └── create_full_test_package.py   # 生成测试包 v2.0.0
│
├── mocks/                      # Mock 服务器
│   ├── device_api_server.py    # Mock Device-API 服务器
│   ├── package_server.py       # Mock 包下载服务器
│   └── __init__.py
│
├── fixtures/                   # 测试数据生成器
│   ├── generate_test_packages.py    # 生成各种测试包
│   ├── packages/                    # 生成的测试包
│   │   ├── valid-1.0.0.zip
│   │   ├── invalid-md5.zip
│   │   ├── path-traversal.zip
│   │   └── oversized.zip
│   ├── manifests/
│   └── __init__.py
│
├── test_data/                  # 手动测试数据
│   ├── test-update-1.0.0.zip
│   ├── test-update-2.0.0.zip
│   ├── test_package/
│   └── test_package_full/
│
└── reports/                    # 测试报告（自动生成）
    ├── test-report.html              # pytest-html 测试报告
    ├── htmlcov/                      # 覆盖率 HTML 报告
    ├── TESTING_SETUP_SUMMARY.md      # 测试基础设施搭建报告
    ├── DOWNLOAD_TEST_SUMMARY.md      # 下载服务测试报告
    └── DEPLOYMENT_TEST_REPORT.md     # 部署测试报告
```

---

## 🚀 快速开始

### 运行自动化测试

```bash
# 运行所有单元测试
uv run pytest tests/unit/ -v --no-cov

# 运行所有测试（包含覆盖率）
uv run pytest tests/ -v

# 只运行特定测试
uv run pytest tests/unit/test_download.py -v

# 查看覆盖率报告
xdg-open tests/reports/htmlcov/index.html    # Linux
open tests/reports/htmlcov/index.html        # macOS

# 查看测试结果报告
xdg-open tests/reports/test-report.html
```

### 运行手动测试脚本

```bash
# 生成测试包
uv run python tests/manual/create_test_package.py

# 测试部署流程
uv run python tests/manual/test_deploy_flow.py

# 测试回滚机制
uv run python tests/manual/test_rollback.py

# 测试 systemd 集成（需要 root）
sudo uv run python tests/manual/test_systemd_refactor.py
```

### 启动 Mock 服务器

```bash
# 启动 Device-API Mock 服务器（端口 9080）
uv run python tests/mocks/device_api_server.py

# 启动 Package Mock 服务器（端口 8888）
uv run python tests/mocks/package_server.py
```

### 生成测试数据

```bash
# 生成各种类型的测试包
uv run python tests/fixtures/generate_test_packages.py
```

---

## 📊 当前测试状态

### 自动化测试
| 模块 | 测试数 | 覆盖率 | 分支覆盖 | 状态 |
|------|--------|--------|----------|------|
| StateManager | 9 | 96% | N/A | ✅ |
| DownloadService | 10 | 97% | 100% | ✅ |
| VerificationUtils | 19 | 100% | 100% | ✅ |
| ReportService | 11 | 82% | N/A | ✅ |
| ProcessManager | 21 | 100% | 100% | ✅ |
| DeployService | 28 | 100% | 100% | ✅ |
| **总计** | **98** | **~50%** | **N/A** | 🟢 |

### 手动测试脚本
- ✅ `test_deploy_flow.py` - 部署流程验证
- ✅ `test_full_deploy_flow.py` - 完整流程验证
- ✅ `test_rollback.py` - 回滚机制验证
- ✅ `test_systemd_refactor.py` - systemd 集成验证

---

## 🎯 测试类型说明

### 1. 单元测试 (Unit Tests)
- **位置**: `tests/unit/`
- **特点**: 快速、隔离、使用 mock
- **运行**: `pytest tests/unit/ -m unit`
- **目标**: 每个服务 90%+ 覆盖率

### 2. 集成测试 (Integration Tests)
- **位置**: `tests/integration/`
- **特点**: 测试多个组件协作
- **运行**: `pytest tests/integration/ -m integration`
- **示例**: 完整 OTA 流程测试

### 3. 契约测试 (Contract Tests)
- **位置**: `tests/contract/`
- **特点**: 验证 API 符合 OpenAPI 规范
- **运行**: `pytest tests/contract/ -m contract`
- **目标**: 所有 API 端点

### 4. 端到端测试 (E2E Tests)
- **位置**: `tests/e2e/`
- **特点**: 接近生产环境的完整测试
- **运行**: `pytest tests/e2e/ -m e2e`
- **示例**: 真实设备部署测试

### 5. 手动测试 (Manual Tests)
- **位置**: `tests/manual/`
- **特点**: 需要特定环境或权限
- **运行**: 手动执行 Python 脚本
- **用途**: 系统集成验证

---

## 📝 编写新测试

### 单元测试模板

```python
"""Unit tests for MyService."""

import pytest
from unittest.mock import MagicMock, patch

from updater.services.my_service import MyService
from updater.models.status import StageEnum


@pytest.mark.unit
class TestMyService:
    """Test MyService in isolation."""

    @pytest.fixture
    def mock_state_manager(self):
        """Mock StateManager."""
        manager = MagicMock()
        # ... setup mocks
        return manager

    @pytest.mark.asyncio
    async def test_my_function_success(self, mock_state_manager):
        """Test successful operation."""
        # Arrange
        service = MyService(mock_state_manager)
        
        # Act
        result = await service.my_function()
        
        # Assert
        assert result is not None
        mock_state_manager.update_status.assert_called()
```

### 添加测试数据

1. 放在 `tests/fixtures/` - 自动生成的测试数据
2. 放在 `tests/test_data/` - 手动创建的测试数据

### 生成测试报告

测试报告会自动生成到 `tests/reports/`:
- `test-report.html` - pytest-html 生成的测试结果
- `htmlcov/` - pytest-cov 生成的覆盖率报告

---

## 🐛 Bug 追踪

所有测试发现的 bug 记录在根目录：
- **文件**: `/BUGS.md`
- **格式**: BUG-XXX 编号
- **流程**: 测试发现 → 记录 BUGS.md → 开发修复

---

## 📚 相关文档

- [测试指南](../specs/001-updater-core/testing-guide.md)
- [Bug 跟踪](../BUGS.md)
- [项目宪法](../specs/.specify/memory/constitution.md)
- [任务清单](../specs/001-updater-core/tasks.md)

---

## 💡 最佳实践

### 编写测试时
1. ✅ 使用 AAA 模式 (Arrange-Act-Assert)
2. ✅ 每个测试只测一件事
3. ✅ 使用清晰的测试名称
4. ✅ 添加文档字符串说明测试目的
5. ✅ 使用 fixtures 减少重复代码

### 运行测试时
1. ✅ 开发时使用 `--no-cov` 快速反馈
2. ✅ 提交前运行完整测试套件
3. ✅ 定期查看覆盖率报告
4. ✅ 修复所有警告

### 维护测试时
1. ✅ 发现 bug 立即添加测试
2. ✅ 修改代码后更新相关测试
3. ✅ 删除过时的测试
4. ✅ 保持测试独立可重复

---

**最后更新**: 2026-01-14
**维护者**: 测试团队
