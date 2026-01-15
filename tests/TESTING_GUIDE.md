# 测试指南

本文档说明如何运行 tope_updater 项目的各种测试。

---

## 快速开始

### 1. 安装依赖

```bash
# 安装所有依赖（包括开发依赖）
uv sync --dev
```

### 2. 运行单元测试

```bash
# 运行所有单元测试
uv run pytest tests/unit/ -v

# 运行单元测试（不显示覆盖率）
uv run pytest tests/unit/ -v --no-cov

# 运行特定模块的测试
uv run pytest tests/unit/test_download.py -v

# 运行特定测试用例
uv run pytest tests/unit/test_download.py::TestDownloadService::test_download_package_success -v
```

### 3. 运行 E2E 测试

**重要**: E2E 测试需要 updater 服务运行。

```bash
# 终端1: 启动 updater 服务
uv run python -m updater.main

# 终端2: 运行 E2E 测试
uv run pytest tests/e2e/test_complete_flow.py -v -s --no-cov

# 运行单个 E2E 测试
uv run pytest tests/e2e/test_complete_flow.py::test_e2e_001_complete_update_flow -v -s --no-cov

# 运行调试测试（不需要 updater 服务）
uv run pytest tests/e2e/test_happy_path.py::test_debug_environment -v -s --no-cov
```

---

## 测试类型

### 单元测试

**位置**: `tests/unit/`
**数量**: 98 tests
**状态**: ✅ 全部通过
**覆盖率**: 76% (服务层 97%)

测试模块：
- `test_state_manager.py` - StateManager 单元测试 (9 tests)
- `test_download.py` - DownloadService 单元测试 (10 tests)
- `test_verification.py` - VerificationUtils 单元测试 (19 tests)
- `test_reporter.py` - ReportService 单元测试 (11 tests)
- `test_process.py` - ProcessManager 单元测试 (21 tests)
- `test_deploy.py` - DeployService 单元测试 (28 tests)

### E2E 测试

**位置**: `tests/e2e/`
**数量**: 6 scenarios
**状态**: ✅ 框架完成，⏳ 需要真实环境验证

测试场景：
- `E2E-001` - 完整 OTA 更新流程
- `E2E-002` - MD5 校验失败
- `E2E-003` - 包大小不匹配
- `E2E-004` - 部署失败回滚
- `E2E-005` - 状态持久化
- `E2E-006` - 并发请求处理

---

## 测试配置

### pytest.ini

测试配置文件位于项目根目录：`pytest.ini`

关键配置：
- `testpaths = tests` - 测试目录
- `asyncio_mode = auto` - 自动异步模式
- `--cov=src/updater` - 覆盖率测试
- `--cov-fail-under=80` - 最低覆盖率要求

### 覆盖率配置

覆盖率配置在 `pytest.ini` 的 `[coverage:run]` 部分：
- `branch = True` - 启用分支覆盖
- `source = src/updater` - 覆盖源代码目录

---

## 常用命令

### 覆盖率报告

```bash
# 生成 HTML 覆盖率报告
uv run pytest tests/unit/ --cov=src/updater --cov-report=html

# 查看覆盖率报告
open tests/reports/htmlcov/index.html
```

### 运行特定标记的测试

```bash
# 运行单元测试
uv run pytest -m unit -v

# 运行 E2E 测试
uv run pytest -m e2e -v -s --no-cov

# 运行慢速测试
uv run pytest -m slow -v
```

### 详细输出

```bash
# 显示详细日志
uv run pytest tests/unit/ -v -s --log-cli-level=DEBUG

# 显示打印输出
uv run pytest tests/unit/ -v -s

# 显示失败的详细信息
uv run pytest tests/unit/ -v --tb=long
```

---

## E2E 测试环境

### 端口配置

- **Updater 服务**: 12315
- **HTTP 服务器**: 8080 (自动启动)
- **Device-API Mock**: 9080 (可选)

### 目录配置

- **测试数据**: `tests/e2e/test_data/`
- **测试包**: `tests/e2e/test_data/packages/`
- **临时文件**: `tmp_e2e/`
- **日志**: `logs_e2e/`
- **备份**: `backups_e2e/`

### HTTP 服务器

E2E 测试使用内置的 HTTP 服务器提供测试包：
- **实现**: `tests/e2e/simple_http_server.py`
- **Fixture**: `package_http_server`
- **自动启动**: 测试开始时自动启动，结束时自动停止

---

## 故障排除

### 问题 1: 端口占用

**错误**: `OSError: [Errno 98] Address already in use`

**解决方案**:
```bash
# 检查端口占用
lsof -i :8080
lsof -i :12315

# 杀死占用进程
kill -9 <PID>
```

### 问题 2: Updater 服务未运行

**错误**: `Connection refused` 或 `httpx.ConnectError`

**解决方案**:
```bash
# 启动 updater 服务
uv run python -m updater.main
```

### 问题 3: 测试包不存在

**错误**: `FileNotFoundError: test-update-1.0.0.zip`

**解决方案**:
测试包会自动生成，如果遇到问题，检查：
```bash
# 检查测试包目录
ls -la tests/e2e/test_data/packages/

# 手动运行测试生成测试包
uv run pytest tests/e2e/test_http_server.py -v -s --no-cov
```

### 问题 4: 权限问题

**错误**: `PermissionError` 在 E2E-004 测试中

**解决方案**:
E2E-004 测试使用 `/root/` 目录来模拟权限错误，这是预期行为。

---

## 测试报告

测试报告位于 `tests/reports/` 目录：

- **UNIT_TEST_SUMMARY.md** - 单元测试详细报告
- **E2E_TEST_SUMMARY.md** - E2E 测试报告
- **TESTING_COMPLETE_SUMMARY.md** - 总体测试报告
- **E2E_FRAMEWORK_COMPLETE.md** - E2E 框架完成报告
- **WORK_SUMMARY.md** - 工作总结报告

HTML 报告：
- **htmlcov/index.html** - 覆盖率报告
- **test-report.html** - pytest HTML 报告

---

## CI/CD 集成

### GitHub Actions (待配置)

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install uv
        run: pip install uv
      - name: Install dependencies
        run: uv sync --dev
      - name: Run unit tests
        run: uv run pytest tests/unit/ -v
```

---

## 最佳实践

### 编写测试

1. **使用 AAA 模式**: Arrange-Act-Assert
2. **清晰的测试名称**: `test_<功能>_<场景>_<预期结果>`
3. **详细的文档字符串**: 说明测试目的和步骤
4. **适当的 fixtures**: 重用测试设置
5. **全面的错误路径**: 测试正常和异常情况

### 运行测试

1. **频繁运行**: 每次修改代码后运行相关测试
2. **完整测试**: 提交前运行所有测试
3. **覆盖率检查**: 确保新代码有测试覆盖
4. **E2E 验证**: 重大更改后运行 E2E 测试

---

## 参考资料

- [pytest 文档](https://docs.pytest.org/)
- [pytest-asyncio 文档](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov 文档](https://pytest-cov.readthedocs.io/)
- [httpx 文档](https://www.python-httpx.org/)

---

**最后更新**: 2026-01-15
**维护者**: 测试团队
