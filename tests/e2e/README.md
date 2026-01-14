# E2E Tests

End-to-end tests for TOP.E OTA Updater.

## 📋 目录

- [概述](#概述)
- [前置条件](#前置条件)
- [快速开始](#快速开始)
- [测试用例](#测试用例)
- [编写新测试](#编写新测试)
- [故障排查](#故障排查)

---

## 概述

E2E 测试验证完整的 OTA 更新流程，从 API 调用到文件部署，模拟真实使用场景。

### 测试范围

- ✅ HTTP API 端点
- ✅ 下载流程（带进度监控）
- ✅ MD5 验证
- ✅ 部署流程
- ✅ 错误处理
- ⏳ systemd 集成（待实现）

### 测试标记

所有 E2E 测试使用 `@pytest.mark.e2e` 标记：

```bash
# 只运行 E2E 测试
pytest tests/e2e/ -v -m e2e
```

---

## 前置条件

### 1. 安装依赖

```bash
uv sync --dev
```

### 2. 测试数据

E2E 测试需要测试包文件。有两种方式：

#### 方式 1: 使用现有测试包

```bash
# 检查是否有测试包
ls test-update-*.zip

# 如果没有，生成一个
python tests/fixtures/generate_test_packages.py
```

#### 方式 2: 使用自动生成（推荐）

E2E 测试框架会自动生成测试包（通过 `sample_test_package` fixture）。

### 3. Mock 服务器（可选）

某些测试需要 mock 服务器：

```bash
# 启动 package server
python tests/fixtures/tests/mocks/package_server.py &

# 启动 device-api mock
python tests/fixtures/tests/mocks/device_api_server.py &
```

---

## 快速开始

### 运行所有 E2E 测试

```bash
# 确保 updater 服务未运行
pkill -f 'updater/main.py'

# 运行测试
pytest tests/e2e/ -v -m e2e -s
```

### 运行特定测试

```bash
# 运行单个测试文件
pytest tests/e2e/test_happy_path.py -v -s

# 运行特定测试用例
pytest tests/e2e/test_happy_path.py::test_updater_service_health -v -s

# 运行所有健康检查测试
pytest tests/e2e/ -k "health" -v -s
```

### 查看详细输出

```bash
# 显示 print 输出
pytest tests/e2e/ -v -s

# 显示本地变量
pytest tests/e2e/ -v -l

# 显示完整日志
pytest tests/e2e/ -v --log-cli-level=INFO
```

---

## 测试用例

### 当前实现的测试

#### `test_happy_path.py`

基础 API 和健康检查测试：

| 测试用例 | 描述 | 状态 |
|---------|------|------|
| `test_updater_service_health` | 验证服务启动和健康检查 | ✅ |
| `test_simple_api_call` | 验证 API 端点可访问性 | ✅ |
| `test_idle_state_after_startup` | 验证启动后处于 IDLE 状态 | ✅ |
| `test_download_request_acceptance` | 验证下载 API 接受请求 | ✅ |
| `test_progress_polling` | 验证进度轮询 | ✅ |
| `test_error_handling_invalid_request` | 验证错误处理 | ✅ |
| `test_concurrent_download_requests` | 验证并发请求处理 | ✅ |
| `test_debug_environment` | 调试环境检查 | ✅ |

### 计划中的测试

详细规划见：[E2E 测试规划](../../../specs/001-updater-core/e2e-test-plan.md)

- E2E-001: 正常更新流程（完整下载 + 部署）
- E2E-002: MD5 校验失败
- E2E-003: 包大小不匹配
- E2E-004: 部署失败回滚
- E2E-005: 状态恢复
- E2E-006 ~ E2E-015: 更多场景

---

## 编写新测试

### 测试模板

```python
"""E2E tests for feature X."""

import logging
import pytest

logger = logging.getLogger(__name__)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_your_scenario(
    http_client: httpx.AsyncClient,
    sample_test_package: Path
):
    """Test description here."""
    logger.info("Starting test...")

    # 1. Setup
    # Prepare test data

    # 2. Execute
    # Call API, perform actions

    # 3. Verify
    # Assert results

    logger.info("Test completed successfully")
```

### 使用 Fixtures

#### `http_client`
提供异步 HTTP 客户端：

```python
async def test_example(http_client: httpx.AsyncClient):
    response = await http_client.get("http://localhost:12315/api/v1.0/progress")
    assert response.status_code == 200
```

#### `sample_test_package`
提供自动生成的测试包：

```python
async def test_with_package(sample_test_package: Path):
    # sample_test_package is a Path to a valid test package
    assert sample_test_package.exists()
```

#### `updater_service`
自动启动/停止 updater 服务：

```python
async def test_with_service(updater_service, http_client):
    # updater_service is automatically started before test
    response = await http_client.get("http://localhost:12315/api/v1.0/progress")
    # updater_service is automatically stopped after test
```

#### `mock_servers`
启动 mock 服务器：

```python
async def test_with_mocks(mock_servers, http_client):
    # mock_servers contains server URLs and PIDs
    package_url = mock_servers["package_server"]["url"]
```

### 工具函数

#### `wait_for_stage()`
等待 updater 到达指定阶段：

```python
from tests.e2e.conftest import wait_for_stage

async def test_download(http_client):
    # Trigger download
    # ...

    # Wait for download to complete
    status = await wait_for_stage(http_client, "TO_INSTALL", timeout=60)

    assert status["stage"] == "TO_INSTALL"
```

#### `create_test_package()`
创建自定义测试包：

```python
from tests.e2e.conftest import create_test_package

def test_with_custom_package():
    package = create_test_package(
        version="2.0.0",
        modules=[{
            "name": "custom-module",
            "src": "bin/custom",
            "dest": "/tmp/custom",
            "md5": "...",
            "size": 100
        }]
    )
```

---

## 故障排查

### 问题 1: Updater 服务无法启动

**症状**: `RuntimeError: Updater service failed to start`

**解决方案**:
```bash
# 检查端口占用
lsof -i :12315

# 杀掉占用进程
pkill -f 'updater/main.py'

# 手动启动测试
uv run python -m updater.main
```

### 问题 2: 测试包找不到

**症状**: `pytest skip: Test package not found`

**解决方案**:
```bash
# 生成测试包
python tests/fixtures/generate_test_packages.py

# 或使用自动生成（在测试中使用 sample_test_package fixture）
```

### 问题 3: Mock 服务器无法连接

**症状**: `Connection refused` 错误

**解决方案**:
```bash
# 检查服务器是否运行
ps aux | grep package_server

# 手动启动
python tests/fixtures/tests/mocks/package_server.py
```

### 问题 4: 测试超时

**症状**: `TimeoutError: Timeout waiting for stage`

**解决方案**:
- 增加超时时间: `wait_for_stage(client, "SUCCESS", timeout=120)`
- 检查日志: `tail -f ./logs_e2e/updater.log`
- 减小测试数据大小

### 问题 5: 权限错误

**症状**: `Permission denied` 部署到系统目录

**解决方案**:
- 使用临时目录进行测试
- 或使用 `sudo` 运行测试（不推荐）
- 修改测试配置，使用 `/tmp` 下的目录

---

## 持续集成

### GitHub Actions 示例

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e:
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

    - name: Generate test packages
      run: python tests/fixtures/generate_test_packages.py

    - name: Run E2E tests
      run: pytest tests/e2e/ -v -m e2e --cov=src/updater

    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

---

## 最佳实践

### 1. 测试隔离
- 每个测试应该独立运行
- 使用 `reset_state` fixture 自动清理状态
- 避免测试间共享状态

### 2. 超时处理
- 为网络操作设置合理的超时
- 使用 `wait_for_stage()` 而不是固定 `sleep()`
- 避免硬编码等待时间

### 3. 日志记录
- 使用 `logger.info()` 记录关键步骤
- 包含足够的上下文信息
- 避免过多调试输出

### 4. 错断言
- 使用明确的断言消息
- 验证实际行为而非实现细节
- 覆盖成功和失败场景

### 5. 测试数据
- 使用最小的必要测试数据
- 自动生成测试数据
- 清理测试文件

---

## 相关文档

- [E2E 测试规划](../../../specs/001-updater-core/e2e-test-plan.md) - 详细规划
- [测试指南](../../../specs/001-updater-core/testing-guide.md) - 测试基础设施
- [任务清单](../../../specs/001-updater-core/tasks.md) - 开发进度

---

**最后更新**: 2026-01-14
**维护者**: 测试团队
