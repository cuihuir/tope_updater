# TOP.E OTA Updater 测试基础设施搭建指南

**文档版本**: 1.0.0
**创建日期**: 2026-01-14
**目标读者**: 测试工程师 / 开发者
**依赖**: tasks.md (Phase 10: Polish & Cross-Cutting Concerns)

---

## 📋 目录

1. [测试概览](#测试概览)
2. [环境准备](#环境准备)
3. [pytest 配置](#pytest-配置)
4. [测试目录结构](#测试目录结构)
5. [测试数据准备](#测试数据准备)
6. [Mock 服务器设置](#mock-服务器设置)
7. [单元测试指南](#单元测试指南)
8. [集成测试指南](#集成测试指南)
9. [契约测试指南](#契约测试指南)
10. [测试用例清单](#测试用例清单)
11. [测试覆盖率目标](#测试覆盖率目标)
12. [CI/CD 集成](#cicd-集成)

---

## 测试概览

### 测试策略

本项目采用**测试金字塔**策略：

```
        🔺 E2E Tests (少量)
       /              \
      /                \
     /    Integration   \  (中等)
    /      Tests         \
   /                      \
  /________________________\
 \   Unit Tests (大量)      /
  \________________________/
```

- **单元测试**: 测试单个类/函数，使用 mock 隔离依赖
- **集成测试**: 测试多个服务的协作，使用真实文件系统
- **契约测试**: 验证 API 符合 OpenAPI 规范
- **端到端测试**: 完整 OTA 流程，接近生产环境

### 当前状态

- ✅ 手动测试脚本存在 (`test_deploy_flow.py`, `test_full_deploy_flow.py`)
- ❌ 无自动化单元测试
- ❌ 无 pytest 配置
- ❌ 无 mock 服务器
- ❌ 无测试覆盖率报告

---

## 环境准备

### 1. 安装测试依赖

```bash
# 使用 uv 安装开发依赖
uv sync --dev

# 或使用 pip
pip install -e ".[dev]"
```

已包含的测试依赖：
- `pytest==8.3.0` - 测试框架
- `pytest-asyncio==0.24.0` - 异步测试支持
- `pytest-cov==5.0.0` - 代码覆盖率
- `pytest-mock` - Mock 工具（需添加到 pyproject.toml）
- `responses` - HTTP mock（需添加）

### 2. 添加缺失的测试依赖

编辑 `pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
    "pytest==8.3.0",
    "pytest-asyncio==0.24.0",
    "pytest-cov==5.0.0",
    "pytest-mock==3.14.0",
    "responses==0.25.0",
    "ruff==0.6.0",
]
```

然后重新安装：
```bash
uv sync --dev
```

---

## pytest 配置

### 创建 `pytest.ini`

在项目根目录创建 `pytest.ini`：

```ini
[pytest]
# Pytest 配置文件

# 测试路径
testpaths = tests

# Python 文件模式
python_files = test_*.py

# Python 类模式
python_classes = Test*

# Python 函数模式
python_functions = test_*

# 异步测试模式
asyncio_mode = auto

# 输出选项
addopts =
    # 详细输出
    -v
    # 显示本地变量
    -l
    # 严格标记模式
    --strict-markers
    # 覆盖率报告
    --cov=src/updater
    --cov-report=term-missing
    --cov-report=html
    # 覆盖率目标
    --cov-fail-under=80

# 标记定义
markers =
    unit: Unit tests (fast, isolated)
    integration: Integration tests (slower, uses filesystem)
    contract: Contract tests (validates API specs)
    e2e: End-to-end tests (slow, real environment)
    slow: Slow tests (network, real I/O)

# 日志配置
log_cli = true
log_cli_level = INFO
log_cli_format = %(asctime)s [%(levelname)8s] %(message)s
log_cli_date_format = %Y-%m-%d %H:%M:%S

# 警告设置
filterwarnings =
    error
    ignore::DeprecationWarning
```

### 创建 `conftest.py` (全局 fixtures)

在 `tests/` 目录创建 `conftest.py`：

```python
"""Global pytest fixtures and configuration."""

import asyncio
import sys
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
    import zipfile

    package_path = tmp_path / "test-package.zip"
    with zipfile.ZipFile(package_path, 'w') as zf:
        # Add manifest.json
        import json
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
```

---

## 测试目录结构

创建完整的测试目录结构：

```
tests/
├── conftest.py                    # 全局 fixtures
├── __init__.py
├── unit/                          # 单元测试
│   ├── __init__.py
│   ├── test_download.py          # DownloadService 测试
│   ├── test_verification.py      # VerificationService 测试
│   ├── test_deployment.py        # DeploymentService 测试
│   ├── test_state_manager.py     # StateManager 测试
│   ├── test_process.py           # Process control 测试
│   └── test_reporter.py          # Reporter 测试
├── integration/                   # 集成测试
│   ├── __init__.py
│   ├── test_full_ota_flow.py     # 完整 OTA 流程
│   └── test_service_restart.py   # 服务管理测试
├── contract/                      # 契约测试
│   ├── __init__.py
│   ├── test_api_endpoints.py     # API 契约测试
│   └── test_device_api_callbacks.py # 回调契约测试
├── e2e/                          # 端到端测试
│   ├── __init__.py
│   └── test_real_deployment.py   # 真实环境测试
└── fixtures/                     # 测试数据
    ├── __init__.py
    ├── packages/                 # 测试包
    │   ├── valid-1.0.0.zip
    │   ├── invalid-md5.zip
    │   └── oversized.zip
    └── manifests/                # 测试清单
        ├── valid.json
        ├── invalid-path.json
        └── missing-fields.json
```

创建目录：
```bash
mkdir -p tests/{unit,integration,contract,e2e,fixtures/{packages,manifests}}
touch tests/{__init__.py,unit/__init__.py,integration/__init__.py,contract/__init__.py,e2e/__init__.py,fixtures/__init__.py}
```

---

## 测试数据准备

### 1. 创建测试包生成脚本

在 `tests/fixtures/` 创建 `generate_test_packages.py`：

```python
"""Generate test packages for testing."""

import json
import zipfile
from pathlib import Path


def create_valid_package(output_path: Path, version: str = "1.0.0"):
    """Create a valid test package."""
    manifest = {
        "version": version,
        "modules": [
            {
                "name": "test-module",
                "src": "bin/test-binary",
                "dest": "/opt/tope/bin/test-binary",
                "md5": "098f6bcd4621d373cade4e832627b4f6",  # MD5 of "test"
                "size": 4,
                "restart_order": 1,
                "process_name": "test-service"
            }
        ]
    }

    with zipfile.ZipFile(output_path, 'w') as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("bin/test-binary", "test")

    print(f"✅ Created: {output_path}")


def create_invalid_md5_package(output_path: Path):
    """Create package with wrong MD5."""
    manifest = {
        "version": "1.0.0",
        "modules": [
            {
                "name": "test-module",
                "src": "bin/test-binary",
                "dest": "/opt/tope/bin/test-binary",
                "md5": "wrongmd5hash",  # Invalid MD5
                "size": 4
            }
        ]
    }

    with zipfile.ZipFile(output_path, 'w') as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("bin/test-binary", "test")

    print(f"✅ Created: {output_path} (invalid MD5)")


def create_path_traversal_package(output_path: Path):
    """Create package with path traversal attack."""
    manifest = {
        "version": "1.0.0",
        "modules": [
            {
                "name": "evil-module",
                "src": "bin/../../etc/passwd",  # Path traversal
                "dest": "/opt/tope/bin/evil",
                "md5": "098f6bcd4621d373cade4e832627b4f6",
                "size": 4
            }
        ]
    }

    with zipfile.ZipFile(output_path, 'w') as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("bin/../../etc/passwd", "test")

    print(f"✅ Created: {output_path} (path traversal)")


if __name__ == "__main__":
    fixtures_dir = Path(__file__).parent

    print("🔧 Generating test packages...")

    create_valid_package(fixtures_dir / "packages" / "valid-1.0.0.zip")
    create_invalid_md5_package(fixtures_dir / "packages" / "invalid-md5.zip")
    create_path_traversal_package(fixtures_dir / "packages" / "path-traversal.zip")

    print("\n✅ All test packages generated!")
```

运行生成：
```bash
python tests/fixtures/generate_test_packages.py
```

---

## Mock 服务器设置

### 1. Mock Device-API 服务器

创建 `tests/mocks/device_api_server.py`：

```python
"""Mock device-api server for testing callbacks."""

import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="Mock Device-API")

# Store received callbacks
callbacks = []

logger = logging.getLogger("mock-device-api")


@app.post("/api/v1.0/ota/report")
async def ota_report(request: Request):
    """Receive OTA status callback."""
    body = await request.json()
    callbacks.append(body)

    logger.info(f"📨 Received callback: {body}")

    return JSONResponse(content={
        "code": 200,
        "msg": "success",
        "data": None
    })


@app.get("/api/v1.0/ota/callbacks")
async def get_callbacks():
    """Return all received callbacks."""
    return {
        "code": 200,
        "msg": "success",
        "data": {
            "count": len(callbacks),
            "callbacks": callbacks
        }
    }


@app.delete("/api/v1.0/ota/callbacks")
async def clear_callbacks():
    """Clear callback history."""
    callbacks.clear()
    return {
        "code": 200,
        "msg": "success",
        "data": None
    }


def run_mock_server(port: int = 9080):
    """Run mock server."""
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    run_mock_server()
```

### 2. Mock Package Server

创建 `tests/mocks/package_server.py`：

```python
"""Mock package server for testing downloads."""

from fastapi import FastAPI, Response
from fastapi.responses import FileResponse
from pathlib import Path

app = FastAPI(title="Mock Package Server")

PACKAGES_DIR = Path(__file__).parent.parent / "fixtures" / "packages"


@app.get("/download/{filename}")
async def download_package(filename: str):
    """Serve test package."""
    package_path = PACKAGES_DIR / filename

    if not package_path.exists():
        return Response(
            content='{"code": 404, "msg": "Package not found"}',
            status_code=404,
            media_type="application/json"
        )

    return FileResponse(
        path=package_path,
        media_type="application/zip",
        filename=filename
    )


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8888, log_level="info")
```

---

## 单元测试指南

### 示例：`tests/unit/test_download.py`

```python
"""Unit tests for DownloadService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import httpx

from updater.services.download import DownloadService
from updater.models.status import StageEnum


@pytest.mark.unit
class TestDownloadService:
    """Test DownloadService in isolation."""

    @pytest.mark.asyncio
    async def test_download_package_success(self, mock_state_manager, tmp_path):
        """Test successful package download."""
        # Arrange
        service = DownloadService(mock_state_manager)
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-length": "1024"}
        mock_response.aiterator_bytes = AsyncMock(
            return_value=b"test content"
        )

        # Act
        with patch('httpx.AsyncClient.stream', return_value=mock_response):
            result = await service.download_package(
                version="1.0.0",
                package_url="http://example.com/package.zip",
                package_name="package.zip",
                package_size=1024,
                package_md5="098f6bcd4621d373cade4e832627b4f6"
            )

        # Assert
        assert result.exists()
        mock_state_manager.update_status.assert_called()

    @pytest.mark.asyncio
    async def test_download_package_md5_mismatch(self, mock_state_manager):
        """Test MD5 mismatch raises error."""
        service = DownloadService(mock_state_manager)

        with pytest.raises(ValueError, match="MD5_MISMATCH"):
            await service.download_package(
                version="1.0.0",
                package_url="http://example.com/package.zip",
                package_name="package.zip",
                package_size=1024,
                package_md5="wrongmd5hash"
            )

    @pytest.mark.asyncio
    async def test_download_package_size_mismatch(self, mock_state_manager):
        """Test package size mismatch raises error."""
        service = DownloadService(mock_state_manager)

        with pytest.raises(ValueError, match="PACKAGE_SIZE_MISMATCH"):
            # Mock HTTP response with wrong Content-Length
            # ... implementation
            pass
```

### 运行单元测试

```bash
# 运行所有单元测试
pytest tests/unit/ -v

# 运行特定测试文件
pytest tests/unit/test_download.py -v

# 运行特定测试方法
pytest tests/unit/test_download.py::TestDownloadService::test_download_package_success -v

# 查看覆盖率
pytest tests/unit/ --cov=src/updater --cov-report=html
```

---

## 集成测试指南

### 示例：`tests/integration/test_full_ota_flow.py`

```python
"""Integration tests for complete OTA flow."""

import pytest
import asyncio
from pathlib import Path
import zipfile
import json

from updater.services.state_manager import StateManager
from updater.services.download import DownloadService
from updater.services.deploy import DeployService
from updater.models.status import StageEnum


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_ota_flow(tmp_path):
    """Test complete OTA flow: download → verify → deploy."""
    # Setup: Create test package
    package_path = tmp_path / "test-package.zip"
    manifest = {
        "version": "1.0.0",
        "modules": [
            {
                "name": "test-module",
                "src": "bin/test",
                "dest": str(tmp_path / "target" / "test"),
                "md5": "098f6bcd4621d373cade4e832627b4f6",
                "size": 4
            }
        ]
    }

    with zipfile.ZipFile(package_path, 'w') as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("bin/test", "test")

    # Test
    state_manager = StateManager()
    state_file = tmp_path / "state.json"
    state_manager.state_file = state_file

    # Deploy
    deploy_service = DeployService(state_manager)
    await deploy_service.deploy_package(package_path, "1.0.0")

    # Assert
    final_status = state_manager.get_status()
    assert final_status.stage == StageEnum.SUCCESS
    assert (tmp_path / "target" / "test").exists()
```

### 运行集成测试

```bash
# 运行所有集成测试
pytest tests/integration/ -v -m integration

# 运行特定集成测试
pytest tests/integration/test_full_ota_flow.py -v
```

---

## 契约测试指南

### 示例：`tests/contract/test_api_endpoints.py`

```python
"""Contract tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient
from updater.main import app


@pytest.mark.contract
class TestAPIContracts:
    """Test API conforms to OpenAPI spec."""

    def test_download_endpoint_accepts_valid_request(self):
        """Test POST /download accepts valid payload."""
        client = TestClient(app)

        response = client.post("/api/v1.0/download", json={
            "version": "1.0.0",
            "package_url": "http://example.com/package.zip",
            "package_name": "package.zip",
            "package_size": 1024,
            "package_md5": "098f6bcd4621d373cade4e832627b4f6"
        })

        # Should return 200 (async task started)
        # or 400/500 for validation errors
        assert response.status_code in [200, 400, 500]

        if response.status_code == 200:
            data = response.json()
            assert "code" in data
            assert "msg" in data
            assert data["code"] == 200

    def test_progress_endpoint_returns_valid_format(self):
        """Test GET /progress returns correct format."""
        client = TestClient(app)

        response = client.get("/api/v1.0/progress")

        assert response.status_code == 200
        data = response.json()
        assert "code" in data
        assert "data" in data
        assert "stage" in data["data"]
        assert "progress" in data["data"]
```

### 运行契约测试

```bash
pytest tests/contract/ -v -m contract
```

---

## 测试用例清单

### Phase 1-3: 核心功能 (P0 - 必须实现)

#### 下载服务 (`test_download.py`)
- [ ] `test_download_package_success` - 成功下载
- [ ] `test_download_package_md5_mismatch` - MD5 不匹配
- [ ] `test_download_package_size_mismatch` - Size 不匹配
- [ ] `test_download_package_disk_full` - 磁盘满
- [ ] `test_download_package_network_error` - 网络错误
- [ ] `test_download_progress_updates` - 进度更新

#### 验证服务 (`test_verification.py`)
- [ ] `test_verify_md5_success` - MD5 验证成功
- [ ] `test_verify_md5_failure` - MD5 验证失败
- [ ] `test_verify_incremental_hash` - 增量哈希计算

#### 部署服务 (`test_deployment.py`)
- [ ] `test_deploy_package_success` - 成功部署
- [ ] `test_deploy_invalid_zip` - 无效 ZIP
- [ ] `test_deploy_missing_manifest` - 缺少 manifest
- [ ] `test_deploy_atomic_replacement` - 原子替换
- [ ] `test_deploy_backup_creation` - 备份创建
- [ ] `test_deploy_rollback_on_failure` - 失败回滚

#### 状态管理 (`test_state_manager.py`)
- [ ] `test_update_status` - 更新状态
- [ ] `test_get_status` - 获取状态
- [ ] `test_persist_state` - 持久化
- [ ] `test_load_state` - 加载状态

#### 进程控制 (`test_process.py`)
- [ ] `test_stop_service_success` - 停止服务
- [ ] `test_start_service_success` - 启动服务
- [ ] `test_stop_nonexistent_service` - 不存在的服务

### Phase 4-6: 弹性功能 (P1 - 高优先级)

#### 断点续传
- [ ] `test_resume_download_with_range_header` - Range header
- [ ] `test_resume_from_bytes_downloaded` - 从断点恢复
- [ ] `test_restart_from_scratch_on_416` - 416 错误处理

#### 服务管理 (systemd)
- [ ] `test_systemctl_stop_service` - systemctl stop
- [ ] `test_systemctl_status_check` - systemctl is-active
- [ ] `test_systemd_dependency_ordering` - 依赖顺序

### Phase 7-9: 增强功能 (P2 - 中优先级)

#### 自愈
- [ ] `test_startup_healing_downloading_state` - 清理 downloading
- [ ] `test_startup_healing_failed_state` - 清理 failed
- [ ] `test_startup_expired_package` - 过期包处理

#### 回调
- [ ] `test_progress_callback_every_5_percent` - 5% 回调
- [ ] `test_stage_transition_callback` - 状态转换回调
- [ ] `test_callback_timeout_handling` - 超时处理

### Phase 10: 边界情况 (P3 - 低优先级)

#### 安全
- [ ] `test_path_traversal_rejection` - 路径遍历攻击
- [ ] `test_manifest_validation` - manifest 验证

#### 性能
- [ ] `test_progress_response_under_100ms` - <100ms 响应
- [ ] `test_memory_usage_under_50mb` - <50MB 内存

---

## 测试覆盖率目标

### 代码覆盖率要求

| 模块 | 目标覆盖率 | 当前状态 |
|------|-----------|---------|
| `download.py` | 90% | 0% |
| `verification.py` | 95% | 0% |
| `deploy.py` | 85% | 0% |
| `state_manager.py` | 90% | 0% |
| `process.py` | 80% | 0% |
| `reporter.py` | 85% | 0% |
| `routes.py` | 85% | 0% |
| **总体** | **>80%** | **0%** |

### 生成覆盖率报告

```bash
# HTML 报告
pytest --cov=src/updater --cov-report=html

# 查看报告
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux

# 终端报告
pytest --cov=src/updater --cov-report=term-missing
```

---

## CI/CD 集成

### GitHub Actions 示例

创建 `.github/workflows/test.yml`：

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install uv
      run: pip install uv

    - name: Install dependencies
      run: uv sync --dev

    - name: Run unit tests
      run: pytest tests/unit/ -v --cov

    - name: Run integration tests
      run: pytest tests/integration/ -v -m integration

    - name: Run contract tests
      run: pytest tests/contract/ -v -m contract

    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

---

## 快速开始

### 第一步：配置环境

```bash
# 1. 创建 pytest.ini
# (复制上面的配置到 pytest.ini)

# 2. 创建测试目录
mkdir -p tests/{unit,integration,contract,e2e,fixtures/{packages,manifests}}

# 3. 创建 conftest.py
# (复制上面的全局 fixtures 到 tests/conftest.py)

# 4. 生成测试数据
python tests/fixtures/generate_test_packages.py
```

### 第二步：编写第一个测试

```bash
# 创建 tests/unit/test_state_manager.py
# (复制上面的示例代码)

# 运行测试
pytest tests/unit/test_state_manager.py -v
```

### 第三步：验证覆盖率

```bash
pytest tests/unit/ --cov=src/updater --cov-report=html
open htmlcov/index.html
```

---

## 下一步行动

### 立即开始 (本周)

1. ✅ 创建 `pytest.ini` 配置文件
2. ✅ 创建 `tests/conftest.py` 全局 fixtures
3. ✅ 创建测试目录结构
4. ✅ 生成测试数据包
5. ✅ 编写第一个单元测试 (`test_state_manager.py`)

### 第二周

1. ✅ 完成所有单元测试 (T062-T066)
2. ✅ 创建 mock 服务器
3. ✅ 编写集成测试 (T067)

### 第三周

1. ✅ 编写契约测试 (T068-T069)
2. ✅ 达到 80% 覆盖率目标
3. ✅ 配置 CI/CD

---

## 故障排除

### 常见问题

**Q: pytest 找不到导入的模块？**
```bash
A: 确保项目根目录有 pytest.ini，且 python_files 配置正确
或在 conftest.py 中添加 sys.path.insert(0, "src")
```

**Q: 异步测试失败？**
```bash
A: 确保在 pytest.ini 中配置 asyncio_mode=auto
或在测试函数上添加 @pytest.mark.asyncio
```

**Q: mock 不生效？**
```bash
A: 确保使用 pytest-mock: pip install pytest-mock
使用 pytest.fixture 中的 mock_state_manager
```

**Q: 覆盖率为 0%？**
```bash
A: 确保 --cov 参数指向正确的模块
--cov=src/updater (不是 --cov=updater)
```

---

## 联系方式

- **开发负责人**: [待填写]
- **文档维护**: Claude Code (Sonnet 4.5)
- **最后更新**: 2026-01-14

---

**附录**:
- [API 契约规范](./contracts/updater-api.yaml)
- [任务清单](./tasks.md)
- [项目宪法](../.specify/memory/constitution.md)
