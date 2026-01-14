# E2E 测试规划

**文档版本**: 1.0.0
**创建日期**: 2026-01-14
**目标读者**: 测试工程师、开发工程师
**状态**: 📋 规划中

---

## 📋 目录

1. [E2E 测试概述](#e2e-测试概述)
2. [测试环境准备](#测试环境准备)
3. [测试场景设计](#测试场景设计)
4. [测试用例清单](#测试用例清单)
5. [实现计划](#实现计划)
6. [测试数据准备](#测试数据准备)
7. [Mock 服务器需求](#mock-服务器需求)

---

## E2E 测试概述

### 什么是 E2E 测试？

端到端（End-to-End）测试是从用户角度验证完整业务流程的测试方法，模拟真实使用场景，验证整个系统的集成和协作。

### E2E 测试 vs 集成测试 vs 单元测试

| 测试类型 | 范围 | 速度 | 隔离性 | 目标 |
|---------|------|------|--------|------|
| **单元测试** | 单个函数/类 | ⚡ 快 | 完全隔离 | 代码逻辑正确性 |
| **集成测试** | 多个服务协作 | 🚗 中等 | 部分 mock | 服务间协作 |
| **E2E 测试** | 完整业务流程 | 🐢 慢 | 真实环境 | 用户场景验证 |

### 本项目 E2E 测试目标

验证 **TOP.E OTA Updater** 在真实环境下的完整更新流程：

```
设备 API 触发 → 下载包 → MD5 验证 → 停服 → 部署 → 启动服务 → 状态报告
```

### 测试范围

#### ✅ 包含
- 完整 OTA 流程（下载 → 验证 → 部署）
- HTTP API 端到端调用
- 真实文件系统操作
- systemd 服务管理（可选，需要 sudo）
- 错误场景和恢复流程

#### ❌ 不包含
- 单元测试（已覆盖）
- 性能测试（独立规划）
- 压力测试（独立规划）
- 安全测试（独立规划）

---

## 测试环境准备

### 选项 1: Docker 容器环境（推荐）🎯

**优势**: 隔离性好、可重复、易于 CI/CD 集成

```yaml
# docker-compose.yml
version: '3.8'
services:
  tope-updater:
    build: .
    ports:
      - "12315:12315"
    volumes:
      - ./test-data:/app/test-data
      - ./tmp:/app/tmp
      - ./logs:/app/logs
      - ./backups:/app/backups
      - /run/systemd:/run/systemd:ro  # systemd 访问（仅 Linux）

  package-server:
    image: nginx:alpine
    ports:
      - "8080:80"
    volumes:
      - ./test-packages:/usr/share/nginx/html:ro

  device-api-mock:
    build: ./tests/mocks/device-api
    ports:
      - "9080:9080"
```

### 选项 2: 本地 Linux 环境（开发测试）

**要求**:
- Python 3.11+
- systemd（可选，用于服务管理测试）
- 网络访问权限
- 临时目录权限

```bash
# 安装依赖
uv sync --dev

# 启动 mock 服务器
python tests/mocks/package_server.py &  # 端口 8080
python tests/mocks/device_api_server.py &  # 端口 9080

# 运行 E2E 测试
pytest tests/e2e/ -v -m e2e
```

### 选项 3: 真实设备环境（生产前验证）

**要求**:
- 真实的 3D 打印机设备
- 完整的系统环境
- 网络连接
- **⚠️ 可能影响设备正常运行**

---

## 测试场景设计

### 场景 1: 🎉 正常更新流程（Happy Path）

**目标**: 验证完整的 OTA 更新流程在正常情况下能够成功完成

**前置条件**:
- 设备运行旧版本（如 v1.0.0）
- device-api 运行正常
- package server 可访问
- 磁盘空间充足（>2× package size）

**测试步骤**:
1. 调用 `POST /api/v1.0/download` 触发下载
2. 轮询 `GET /api/v1.0/progress` 监控进度
3. 等待下载完成（stage = `TO_INSTALL`）
4. 调用 `POST /api/v1.0/update` 触发安装
5. 验证部署流程：
   - 停止服务（如需要）
   - 备份旧文件
   - 部署新文件
   - 启动服务
   - 验证部署
6. 验证最终状态：`stage = SUCCESS`

**预期结果**:
- 所有阶段顺利完成
- 文件正确部署到目标位置
- 服务成功重启
- 无错误日志
- device-api 收到成功回调

**测试数据**:
- 版本: 1.0.0 → 2.0.0
- 包大小: 10MB
- MD5: 正确
- 模块: 3 个模块（二进制、配置、数据）

---

### 场景 2: 🔄 下载中断后恢复

**目标**: 验证下载中断后的恢复能力

**测试步骤**:
1. 开始下载大文件（100MB+）
2. 在下载到 50% 时手动中断（kill 进程或网络断开）
3. 重启 updater 服务
4. 触发重新下载（相同版本）
5. 验证是否从头开始下载（当前实现）

**预期结果**:
- ✅ 服务重启后状态恢复为 `IDLE`
- ✅ 重新下载从头开始（当前行为，符合 Constitution Principle VIII）
- ✅ 最终下载成功

**注意**: 断点续传是可选功能，当前不实现

---

### 场景 3: ❌ MD5 校验失败

**目标**: 验证 MD5 校验失败时的错误处理

**测试步骤**:
1. 准备测试包，MD5 不匹配
2. 调用下载 API
3. 下载完成，进入验证阶段
4. MD5 验证失败

**预期结果**:
- ✅ 状态更新为 `FAILED`
- ✅ 错误消息包含 `MD5_MISMATCH`
- ✅ 下载的包文件被删除
- ✅ state.json 清理
- ✅ device-api 收到失败回调（如实现）

**测试数据**:
- 包 MD5: `correct_md5_hash`
- 声称 MD5: `wrong_md5_hash`

---

### 场景 4: 📦 包大小不匹配

**目标**: 验证 HTTP Content-Length 与声明大小不一致的处理

**测试步骤**:
1. 准备测试包，实际大小 ≠ 声称大小
2. mock package server 返回错误的 Content-Length
3. 调用下载 API
4. 验证错误处理

**预期结果**:
- ✅ 状态更新为 `FAILED`
- ✅ 错误消息包含 `PACKAGE_SIZE_MISMATCH` 或 `INCOMPLETE_DOWNLOAD`
- ✅ 下载的包文件被删除

---

### 场景 5: 🛑 部署失败后回滚

**目标**: 验证部署失败时自动回滚机制

**测试步骤**:
1. 准备包含损坏文件的测试包
2. 调用部署 API
3. 部署过程中模拟失败（如文件权限错误）
4. 验证回滚流程

**预期结果**:
- ✅ 检测到部署失败
- ✅ 自动触发回滚
- ✅ 所有备份文件恢复
- ✅ 状态更新为 `FAILED`
- ✅ 错误消息包含 `DEPLOYMENT_FAILED` 和 `ROLLBACK_SUCCEEDED`

**测试数据**:
- 目标路径: `/root/protected-file` (无写权限)
- 预期: 部署失败 → 回滚成功

---

### 场景 6: 🔄 状态恢复（重启后）

**目标**: 验证服务重启后状态恢复能力

**测试步骤**:
1. 开始下载，状态为 `DOWNLOADING`
2. 在下载过程中 kill updater 进程
3. 重启 updater 服务
4. 验证启动时的状态处理

**预期结果**:
- ✅ 检测到未完成的下载
- ✅ 清理部分下载的文件
- ✅ 状态重置为 `IDLE`
- ✅ 日志记录清理操作

---

### 场景 7: 🌐 网络错误处理

**目标**: 验证各种网络错误的处理

**子场景**:
1. **连接超时**: package server 无响应
2. **DNS 解析失败**: 无效的 URL
3. **HTTP 404**: 包不存在
4. **HTTP 503**: 服务器暂时不可用
5. **证书错误**: HTTPS 证书无效

**预期结果**:
- ✅ 状态更新为 `FAILED`
- ✅ 错误消息包含网络错误信息
- ✅ 不留下孤儿文件

---

### 场景 8: 🚀 并发请求处理

**目标**: 验证同时处理多个请求的行为

**测试步骤**:
1. 发起第一个下载请求（version A）
2. 在 version A 下载中，发起第二个请求（version B）
3. 验证系统行为

**预期结果**:
- ✅ 第二个请求返回错误（版本冲突）
- ✅ 或第二个请求排队等待（如实现）
- ✅ 不损坏状态文件

---

### 场景 9: 📊 进度报告准确性

**目标**: 验证进度报告的准确性和及时性

**测试步骤**:
1. 下载 100MB 测试包
2. 每 5% 验证进度值
3. 验证阶段转换时机
4. 验证回调频率（如实现）

**预期结果**:
- ✅ 进度值单调递增
- ✅ 阶段转换正确（DOWNLOADING → VERIFYING → TO_INSTALL → INSTALLING → SUCCESS）
- ✅ 进度更新间隔 ≈5%
- ✅ device-api 收到进度回调（如实现）

---

### 场景 10: 🔐 systemd 服务管理（可选）

**目标**: 验证与 systemd 的集成

**前置条件**: 需要 sudo 权限

**测试步骤**:
1. 准备测试 systemd service（如 `mock-updater.service`）
2. 部署包含 `process_name` 的包
3. 验证服务停止
4. 验证文件部署
5. 验证服务启动
6. 验证服务状态

**预期结果**:
- ✅ `systemctl stop` 成功
- ✅ 文件原子替换
- ✅ `systemctl start` 成功
- ✅ `systemctl is-active` 返回 `active`

---

## 测试用例清单

### Priority 1: 核心流程（必须实现）

| ID | 场景 | 优先级 | 预计时间 | 状态 |
|----|------|--------|----------|------|
| E2E-001 | 正常更新流程 | P0 | 30min | ⏳ 待实现 |
| E2E-002 | MD5 校验失败 | P0 | 15min | ⏳ 待实现 |
| E2E-003 | 包大小不匹配 | P0 | 15min | ⏳ 待实现 |
| E2E-004 | 部署失败回滚 | P0 | 20min | ⏳ 待实现 |
| E2E-005 | 状态恢复 | P0 | 20min | ⏳ 待实现 |

### Priority 2: 错误处理（高优先级）

| ID | 场景 | 优先级 | 预计时间 | 状态 |
|----|------|--------|----------|------|
| E2E-006 | 网络连接超时 | P1 | 15min | ⏳ 待实现 |
| E2E-007 | HTTP 404 处理 | P1 | 10min | ⏳ 待实现 |
| E2E-008 | HTTP 503 处理 | P1 | 10min | ⏳ 待实现 |
| E2E-009 | 进度报告准确性 | P1 | 20min | ⏳ 待实现 |

### Priority 3: 边界情况（中优先级）

| ID | 场景 | 优先级 | 预计时间 | 状态 |
|----|------|--------|----------|------|
| E2E-010 | 并发请求处理 | P2 | 15min | ⏳ 待实现 |
| E2E-011 | 下载中断恢复 | P2 | 20min | ⏳ 待实现 |
| E2E-012 | 磁盘空间不足 | P2 | 15min | ⏳ 待实现 |
| E2E-013 | 权限错误处理 | P2 | 15min | ⏳ 待实现 |

### Priority 4: 高级功能（低优先级）

| ID | 场景 | 优先级 | 预计时间 | 状态 |
|----|------|--------|----------|------|
| E2E-014 | systemd 集成 | P3 | 30min | ⏳ 待实现 |
| E2E-015 | device-api 回调 | P3 | 20min | ⏳ 待实现 |

**总计**: 15 个测试用例，预计 **5-6 小时** 实现时间

---

## 实现计划

### Phase 1: 基础设施（1-2 小时）

**目标**: 搭建 E2E 测试基础设施

#### 1.1 创建测试框架
```python
# tests/e2e/conftest.py
import pytest
import asyncio
from pathlib import Path
import subprocess
import time

@pytest.fixture(scope="session")
def test_environment():
    """Setup E2E test environment."""
    # Start mock servers
    # Create test directories
    # Setup test data
    yield
    # Cleanup

@pytest.fixture(scope="session")
def updater_service():
    """Start/stop updater service."""
    proc = subprocess.Popen(["uv", "run", "src/updater/main.py"])
    time.sleep(2)  # Wait for startup
    yield
    proc.terminate()
    proc.wait()
```

#### 1.2 Mock 服务器增强
- 完善 `tests/mocks/package_server.py`
- 完善 `tests/mocks/device_api_server.py`
- 添加测试数据管理

#### 1.3 测试数据生成
```python
# tests/e2e/fixtures.py
def create_test_package(version: str, size_mb: int) -> Path:
    """Create test OTA package."""
    # Generate ZIP with manifest.json
    # Add test files
    # Return package path
```

**交付物**:
- ✅ `tests/e2e/conftest.py`
- ✅ `tests/e2e/fixtures.py`
- ✅ 增强的 mock 服务器
- ✅ 测试数据生成脚本

---

### Phase 2: 核心场景实现（2-3 小时）

**目标**: 实现 Priority 1 测试用例

#### 2.1 E2E-001: 正常更新流程
```python
# tests/e2e/test_happy_path.py
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_full_ota_flow_happy_path(updater_service, test_environment):
    """Test complete OTA update flow."""
    # 1. Call download API
    # 2. Poll progress
    # 3. Call update API
    # 4. Verify deployment
    # 5. Check final state
```

#### 2.2 E2E-002 ~ E2E-005: 错误场景
- MD5 校验失败
- 包大小不匹配
- 部署失败回滚
- 状态恢复

**交付物**:
- ✅ `tests/e2e/test_happy_path.py`
- ✅ `tests/e2e/test_error_scenarios.py`
- ✅ 5 个核心测试用例通过

---

### Phase 3: 错误处理实现（1-2 小时）

**目标**: 实现 Priority 2 测试用例

#### 3.1 网络错误场景
```python
# tests/e2e/test_network_errors.py
@pytest.mark.e2e
async def test_download_timeout():
    """Test network timeout handling."""

@pytest.mark.e2e
async def test_http_404_not_found():
    """Test HTTP 404 handling."""
```

#### 3.2 进度报告验证
```python
# tests/e2e/test_progress_reporting.py
@pytest.mark.e2e
async def test_progress_accuracy():
    """Test progress reporting accuracy."""
```

**交付物**:
- ✅ `tests/e2e/test_network_errors.py`
- ✅ `tests/e2e/test_progress_reporting.py`
- ✅ 4 个错误处理测试通过

---

### Phase 4: 边界情况实现（1-2 小时）

**目标**: 实现 Priority 3 测试用例

#### 4.1 并发和资源限制
- 并发请求
- 磁盘空间不足
- 权限错误

**交付物**:
- ✅ `tests/e2e/test_edge_cases.py`
- ✅ 4 个边界测试通过

---

### Phase 5: 高级功能实现（可选，1-2 小时）

**目标**: 实现 Priority 4 测试用例

#### 5.1 systemd 集成
#### 5.2 device-api 回调

**交付物**:
- ✅ `tests/e2e/test_systemd_integration.py`
- ✅ `tests/e2e/test_device_api_callbacks.py`

---

## 测试数据准备

### 测试包清单

| 包名 | 版本 | 大小 | MD5 | 用途 |
|------|------|------|-----|------|
| `test-update-1.0.0.zip` | 1.0.0 | 10MB | 正确 | 正常流程 |
| `test-update-wrong-md5.zip` | 2.0.0 | 5MB | 错误 | MD5 验证失败 |
| `test-update-large.zip` | 3.0.0 | 100MB | 正确 | 进度报告 |
| `test-update-broken.zip` | 4.0.0 | 1MB | 正确 | 部署失败（损坏文件） |
| `test-update-multi-module.zip` | 5.0.0 | 20MB | 正确 | 多模块部署 |

### 生成脚本

```python
# tests/e2e/generate_test_packages.py
import zipfile
import json
from pathlib import Path
import hashlib

def generate_package(version: str, size_mb: int, broken: bool = False):
    """Generate test OTA package."""
    package_path = Path(f"test-update-{version}.zip")

    # Create manifest
    manifest = {
        "version": version,
        "modules": [
            {
                "name": "mock-app",
                "src": "bin/mock-app",
                "dest": "/tmp/tope-updater-test/mock-app",
                "md5": hashlib.md5(b"mock-data").hexdigest(),
                "size": 9
            }
        ]
    }

    with zipfile.ZipFile(package_path, 'w') as zf:
        zf.writestr("manifest.json", json.dumps(manifest))

        # Add test files
        if not broken:
            zf.writestr("bin/mock-app", b"mock-data")
        else:
            zf.writestr("bin/mock-app", b"corrupted-data")

    print(f"Generated {package_path} ({package_path.stat().st_size} bytes)")
    return package_path

if __name__ == "__main__":
    generate_package("1.0.0", 10)
    generate_package("2.0.0", 5)
    # ...
```

---

## Mock 服务器需求

### Package Server（增强）

**功能**:
- ✅ 返回静态测试包
- ⏳ 支持 HTTP Range header（断点续传）
- ⏳ 可配置的延迟（模拟慢速网络）
- ⏳ 错误注入（404, 503, 超时）
- ⏳ Content-Length 控制

**API**:
```
GET /packages/test-update-1.0.0.zip
GET /packages/test-update-wrong-md5.zip
GET /packages/nonexistent.zip  → 404
GET /packages/slow.zip?delay=10  → 延迟 10 秒
```

**实现**:
```python
# tests/mocks/package_server_enhanced.py
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
import time

app = FastAPI()

@app.get("/packages/{filename}")
async def get_package(filename: str, delay: int = 0):
    """Serve test package with optional delay."""
    file_path = Path(f"test-packages/{filename}")

    if not file_path.exists():
        raise HTTPException(status_code=404)

    if delay > 0:
        time.sleep(delay)

    return FileResponse(file_path)
```

---

### device-api Mock（增强）

**功能**:
- ✅ 接收进度回调
- ⏳ 记录所有回调
- ⏳ 提供查询接口（获取回调历史）
- ⏳ 可配置的失败（模拟 device-api 不可用）

**API**:
```
POST /api/v1.0/updater/progress
GET /api/v1.0/updater/callbacks  → 返回回调历史
DELETE /api/v1.0/updater/callbacks  → 清空历史
```

---

## 运行 E2E 测试

### 本地运行

```bash
# 1. 启动 mock 服务器
python tests/mocks/package_server.py &
python tests/mocks/device_api_server.py &

# 2. 运行所有 E2E 测试
pytest tests/e2e/ -v -m e2e

# 3. 运行特定测试
pytest tests/e2e/test_happy_path.py::test_full_ota_flow_happy_path -v -s

# 4. 生成覆盖率
pytest tests/e2e/ -v -m e2e --cov=src/updater --cov-report=html
```

### Docker 运行

```bash
# 构建测试环境
docker-compose build

# 运行测试
docker-compose run --rm tope-updater pytest tests/e2e/ -v -m e2e

# 清理
docker-compose down -v
```

### CI/CD 集成

```yaml
# .github/workflows/e2e-tests.yml
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

    - name: Install dependencies
      run: |
        pip install uv
        uv sync --dev

    - name: Start mock servers
      run: |
        python tests/mocks/package_server.py &
        python tests/mocks/device_api_server.py &

    - name: Run E2E tests
      run: |
        pytest tests/e2e/ -v -m e2e --cov=src/updater

    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

---

## 成功标准

### Phase 1 完成标准
- ✅ E2E 测试框架搭建完成
- ✅ Mock 服务器正常工作
- ✅ 测试数据自动生成
- ✅ 至少 1 个测试用例通过

### Phase 2 完成标准
- ✅ 5 个核心测试用例通过
- ✅ 测试覆盖率 > 70%
- ✅ 文档完整

### Phase 3 完成标准
- ✅ 9 个测试用例通过（P0 + P1）
- ✅ 测试覆盖率 > 75%
- ✅ CI/CD 集成完成

### 完整完成标准
- ✅ 15 个测试用例全部通过
- ✅ 测试覆盖率 > 80%
- ✅ 文档完整
- ✅ CI/CD 自动运行

---

## 风险和依赖

### 风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| systemd 集成需要 sudo | 测试环境复杂 | 使用 mock 或 Docker |
| 网络测试不稳定 | CI 失败 | 重试机制、本地 mock |
| 测试数据生成复杂 | 实现时间长 | 复用现有脚本 |
| device-api 依赖 | 外部依赖 | Mock server |

### 依赖

- ✅ 单元测试完成
- ✅ 集成测试完成
- ⏳ Mock 服务器增强
- ⏳ 测试数据准备
- ⏳ CI/CD 环境

---

## 下一步行动

1. **评审此规划** - 测试团队和开发团队共同评审
2. **创建 Phase 1 任务** - 在 tasks.md 中添加 E2E 测试任务
3. **开始实现** - 按照 Phase 1 → Phase 2 → Phase 3 顺序实现
4. **持续集成** - 每个 Phase 完成后合并到主分支

---

**最后更新**: 2026-01-14
**维护者**: 测试团队
**状态**: 📋 待评审
