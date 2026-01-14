# tope_updater Development Guidelines

Last updated: 2026-01-14

## Project Overview

TOP.E OTA Updater - 防弹级 OTA 更新服务，用于嵌入式 3D 打印机设备的固件/软件更新。

**Current Branch**: `001-updater-core`
**Current Phase**: Phase 5-6 完成，Phase 7-10 待实现

## Active Technologies

- **Language**: Python 3.11+
- **HTTP Framework**: FastAPI 0.115.0 + uvicorn 0.32.0
- **Async HTTP Client**: httpx 0.27.0
- **Async File I/O**: aiofiles 24.1.0
- **Testing**: pytest 8.3.0, pytest-asyncio 0.24.0, pytest-cov 5.0.0, pytest-mock 3.14.0
- **Code Quality**: ruff 0.6.0

## Project Structure

```
src/updater/
├── main.py                      # FastAPI 应用入口
├── api/
│   ├── routes.py                # HTTP 端点 (download, update, progress)
│   └── models.py                # Pydantic 请求/响应模型
├── services/
│   ├── download.py              # 异步下载服务 (httpx + 三层验证)
│   ├── deploy.py                # 部署服务 (ZIP 解压 + 原子操作 + 回滚)
│   ├── process.py               # systemd 服务管理 (stop/start/status)
│   ├── reporter.py              # device-api 回调服务
│   └── state_manager.py         # 状态持久化 (state.json + 单例)
├── models/
│   ├── manifest.py              # Manifest 数据模型
│   ├── state.py                 # StateFile 数据模型
│   └── status.py                # StageEnum 枚举
└── utils/
    ├── logging.py               # 轮转日志 (10MB, 3 files)
    └── verification.py          # MD5 计算工具

specs/001-updater-core/
├── spec.md                      # 功能规范
├── spec_cn.md                   # 中文功能规范
├── plan.md                      # 实现计划
├── plan_cn.md                   # 中文实现计划
├── tasks.md                     # 任务清单与进度
├── data-model.md                # 数据模型文档
├── testing-guide.md             # 测试基础设施指南 ⭐ 新增
├── quickstart.md                # 快速开始指南
└── research.md                  # 技术调研

tests/                           # 测试目录 (待完善)
├── conftest.py                  # 全局 fixtures
├── unit/                        # 单元测试
├── integration/                 # 集成测试
└── contract/                    # 契约测试
```

## Commands

### Package Management (uv)
```bash
# 安装依赖
uv sync

# 安装开发依赖
uv sync --dev

# 运行应用
uv run src/updater/main.py

# 运行测试
uv run pytest
```

### Testing
```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit/ -v

# 运行集成测试
pytest tests/integration/ -v -m integration

# 生成覆盖率报告
pytest --cov=src/updater --cov-report=html

# 查看覆盖率
open htmlcov/index.html
```

### Code Quality
```bash
# 代码格式化
ruff format src/ tests/

# 代码检查
ruff check src/ tests/

# 自动修复
ruff check --fix src/ tests/
```

### Manual Testing Scripts
```bash
# 测试 systemd 集成
sudo python test_systemd_refactor.py

# 测试回滚机制
python test_rollback.py

# 测试部署流程
python test_deploy_flow.py

# 测试完整部署流程
python test_full_deploy_flow.py
```

## Code Style

### Python Conventions
- **Python Version**: 3.11+
- **Imports**: 使用绝对导入 `from updater.services import X`
- **Type Hints**: 所有公共方法必须添加类型注解
- **Docstrings**: 所有公共方法必须添加文档字符串
- **Async**: 所有 I/O 操作使用 async/await

### Naming Conventions
- **Classes**: `PascalCase` (e.g., `DownloadService`)
- **Functions/Variables**: `snake_case` (e.g., `download_package`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRIES`)
- **Private Methods**: `_leading_underscore` (e.g., `_backup_file`)

## Architecture Principles

### 1. 分层架构
```
API Layer (routes.py)
    ↓
Service Layer (download.py, deploy.py, process.py)
    ↓
Data Layer (state_manager.py, models/)
```

### 2. 单例模式
- `StateManager` 使用单例模式确保全局状态一致
- 所有服务通过 `state_manager = StateManager()` 获取单例

### 3. 原子操作
- 文件部署使用 `temp → verify → rename` 模式
- 失败时自动回滚到备份

### 4. 错误处理
- 所有异常必须记录日志
- 用户可见错误使用结构化错误代码 (e.g., `DEPLOYMENT_FAILED`)
- 区分可恢复错误和致命错误

## Current Implementation Status

### ✅ Completed (Phase 1-3, 5-6, Testing Infrastructure)
- ✅ **Phase 1**: 项目初始化
- ✅ **Phase 2**: 基础组件
- ✅ **Phase 3**: 基本 OTA 流程 (下载 → 验证 → 部署)
- ✅ **Phase 5**: 原子部署 + 回滚机制
- ✅ **Phase 6**: systemd 服务管理 (stop/start/status)
- ✅ **Testing Infrastructure**: 完整的测试基础设施和单元测试 ⭐ NEW (2026-01-14)
  - pytest 配置 (pytest.ini, pyproject.toml)
  - 全局 fixtures (conftest.py)
  - 单元测试 (test_download.py, test_state_manager.py)
  - 测试 fixtures 和 mock 服务器
  - 手动测试脚本 (tests/manual/)
  - 测试报告 (tests/reports/)

### ⚠️ Partially Completed (Phase 8)
- ⚠️ **Phase 8**: 状态报告 (已实现回调，未测试)

### ❌ Not Started (Phase 4, 7, 9, 10)
- ❌ **Phase 4**: 断点续传 (可选功能)
- ❌ **Phase 7**: 启动自愈增强
- ❌ **Phase 9**: GUI 集成 (可选功能)
- ❌ **Phase 10**: 完善与测试

## Key Features Implemented

### 1. 三层下载验证
```python
# Layer 1: HTTP Content-Length
# Layer 2: 业务层 package_size
# Layer 3: MD5 完整性验证
```

### 2. 原子文件部署
```python
# temp 文件 → MD5 验证 → os.rename() → 原子替换
# 失败时自动回滚到备份
```

### 3. systemd 服务管理
```python
# systemctl stop → 状态验证 → 部署 → systemctl start
# 支持服务依赖自动排序
```

### 4. 回滚机制
```python
# 部署失败时自动恢复所有备份
# 错误消息: DEPLOYMENT_FAILED → Rollback completed
```

## Testing Guide

完整的测试基础设施搭建指南见：`specs/001-updater-core/testing-guide.md`

### Quick Start
```bash
# 1. 创建 pytest.ini
# 2. 创建 tests/conftest.py
# 3. 生成测试数据
python tests/fixtures/generate_test_packages.py

# 4. 运行测试
pytest tests/unit/test_download.py -v
```

## Bug Tracking Workflow

### BUGS.md 概述
项目使用 `BUGS.md` 作为 bug 跟踪系统，位于项目根目录。这是一个集中式的 bug 报告和跟踪文档，由测试团队维护，开发团队负责修复。

**文档位置**: `BUGS.md` (项目根目录)

### Bug 生命周期
```
🔴 Open (待修复)
    ↓ 测试团队发现并记录
🟡 In Progress (进行中) ← 开发团队认领
    ↓ 开发团队修复代码
🟢 Fixed (已修复) ← 开发团队完成修复
    ↓ 测试团队验证
✅ Verified (已验证)
    ↓ 确认修复成功
⚫ Closed (已关闭)
```

### Bug 严重程度定义

| 级别 | 图标 | 定义 | 示例 |
|------|------|------|------|
| **Critical** | 💀 | 导致系统崩溃或数据丢失 | 核心功能完全失效 |
| **High** | 🔴 | 严重影响功能，无替代方案 | 主要功能失效 |
| **Medium** | 🟡 | 影响功能但有变通方案 | 边界情况失效 |
| **Low** | 🟢 | 小问题，不影响主要功能 | UI问题、日志错误 |

### 团队职责

#### 测试团队职责
1. ✅ 发现并记录 bug（添加到 BUGS.md）
2. ✅ 提供详细的重现步骤和代码位置
3. ✅ 编写失败或跳过的测试用例
4. ✅ 更新 bug 统计
5. ✅ 验证修复并更新状态为 Closed

#### 开发团队职责
1. 🔧 认领 bug（状态改为 In Progress）
2. 🔧 修复代码
3. 🔧 更新 BUGS.md 状态为 Fixed
4. 🔧 在代码中添加修复注释（例如：`# FIX for BUG-001`）
5. 🔧 通知测试团队验证

### Bug 报告格式

每个 bug 必须按以下格式记录：

```markdown
### BUG-XXX: [简短描述]

**严重程度**: 🔴 High / 🟡 Medium / 🟢 Low
**发现日期**: YYYY-MM-DD
**修复日期**: YYYY-MM-DD (可选)
**发现者**: [发现者/团队]
**修复者**: [修复者/团队] (可选)
**发现位置**: [测试文件::测试方法]
**状态**: 🔴 Open / 🟡 In Progress / 🟢 Fixed / ⚫ Closed

#### 问题描述
[详细描述问题]

#### 代码位置
- **文件**: path/to/file.py
- **函数**: function_name()
- **行号**: XX

#### 重现步骤
1. 步骤1
2. 步骤2
3. ...

#### 当前代码
\`\`\`python
# 有问题的代码
\`\`\`

#### 根本原因
[分析根本原因]

#### 预期行为
[描述期望的正确行为]

#### 建议修复方案
\`\`\`python
# 建议的修复代码
\`\`\`

#### 修复验证
- ✅ 代码编译通过，无语法错误
- ⏳ 单元测试需要验证
- ⏳ 需要测试特定场景

#### 影响范围
[描述影响范围和严重性]

#### 相关测试
- **测试文件**: path/to/test.py
- **测试用例**: test_name
- **当前状态**: Pass / Fail / Skip

#### 提交记录
- Commit hash: (待提交/已提交)
- Commit message: "fix: 修复 XXX (BUG-XXX)"
```

### 协作流程

```
测试发现 → 记录BUGS.md → 开发认领 → 修复代码 → 测试验证 → 关闭Bug
```

### Bug 修复示例

**示例**: BUG-001 - download.py 中 expected_from_server 变量未初始化

1. **测试团队发现**: 单元测试 `test_download_network_error` 失败
2. **记录 Bug**: 在 BUGS.md 中添加 BUG-001，标记为 🔴 Open
3. **开发团队认领**: 状态改为 🟡 In Progress
4. **修复代码**:
   ```python
   # src/updater/services/download.py:199
   # FIX for BUG-001: Initialize before async with block
   expected_from_server = None
   ```
5. **更新状态**: BUGS.md 中标记为 🟢 Fixed，添加修复详情
6. **提交代码**:
   ```bash
   git add src/updater/services/download.py BUGS.md
   git commit -m "fix: 修复 download.py 中 expected_from_server 未初始化的 bug (BUG-001)"
   ```
7. **测试验证**: 运行 `test_download_network_error` 确认通过
8. **关闭 Bug**: 状态改为 ⚫ Closed

### 相关文档
- [BUGS.md](BUGS.md) - Bug 跟踪清单
- [测试指南](specs/001-updater-core/testing-guide.md) - 测试基础设施
- [任务清单](specs/001-updater-core/tasks.md) - 功能开发任务

## Known Limitations

1. **断点续传** - 可选功能，当前重启后从头下载
2. **自动化测试** - 无 pytest 测试，仅手动测试脚本
3. **部署测试** - 需要真实设备集成测试
4. **启动自愈** - 仅部分实现 (downloading/verifying 清理)

## Development Workflow

### 1. 开始新功能
```bash
# 创建功能分支
git checkout -b feature/xxx

# 查看任务清单
cat specs/001-updater-core/tasks.md
```

### 2. 开发与测试
```bash
# 编写代码
# 运行手动测试脚本
python test_xxx.py

# 代码检查
ruff check src/ --fix
```

### 3. 提交代码
```bash
# 添加文件
git add src/ tests/ specs/

# 提交 (遵循约定式提交)
git commit -m "feat: 添加新功能"

# 推送
git push origin 001-updater-core
```

### 4. 更新文档
```bash
# 更新 tasks.md 标记完成的任务
# 更新 README.md 同步进度
# 更新 CLAUDE.md (本文件)
```

## Configuration

### Hardcoded Settings
- **Updater Port**: 12315
- **device-api Port**: 9080
- **Working Directory**: Current directory
- **Temp Directory**: `./tmp/`
- **Logs Directory**: `./logs/`
- **Backups Directory**: `./backups/`

### Runtime Directories
```bash
./tmp/          # 临时文件 (下载中的包)
./logs/         # 日志文件 (轮转)
./backups/      # 部署备份
./state.json    # 状态持久化
```

## Project Constitution

核心设计原则见：`specs/.specify/memory/constitution.md`

**关键原则**:
- I. 核心使命: 仅实现 OTA 功能
- IV. 原子文件操作: 所有替换必须是原子的
- V. 强制 MD5 校验: 无跳过机制
- VII. systemd 服务管理: 使用 systemd 生命周期
- X. 全面错误报告: 所有错误必须报告

## Recent Changes (2026-01-14)

### Phase 6: systemd 服务管理重构
- 新增 `ServiceStatus` 枚举
- 实现 `stop_service()`, `start_service()`, `get_service_status()`
- 实现 `wait_for_service_status()` (带超时)
- 重构 `DeployService` 使用 stop → deploy → start 流程

### Phase 5: 原子部署和回滚机制
- 新增 `backup_paths` 跟踪备份
- 实现 `_rollback_deployment()` 自动恢复
- 实现 `DEPLOYMENT_FAILED` 错误报告
- 新增 `test_rollback.py` 测试脚本

### 测试基础设施
- 新增 `specs/001-updater-core/testing-guide.md`
- 完整的测试搭建指南
- Mock 服务器示例

## Next Steps

### 立即行动 (P0 - 阻塞生产部署)
1. ✅ Phase 6: systemd 集成 (已完成)
2. ⏳ 端到端集成测试
3. ⏳ 性能验证 (<100ms /progress, <50MB RAM)

### 短期任务 (P1 - 质量保证)
1. ⏳ Phase 7: 启动自愈增强
2. ⏳ 建立测试基础设施
3. ⏳ 编写单元测试

### 中期任务 (P2 - 功能增强)
1. ⏳ Phase 8: 完善状态报告
2. ⏳ Phase 10: 代码完善
3. ⏸️ Phase 4: 断点续传 (可选)

## Git Workflow

### Branch Strategy
- `001-updater-core` - 主开发分支
- `main` - 生产分支

### Commit Convention
```
feat: 新功能
fix: 修复 bug
docs: 文档更新
test: 测试相关
refactor: 代码重构
```

### Recent Commits
```
cb14547 feat: 实现原子部署和回滚机制 (Phase 5: T040-T041)
47dc969 feat: 完成测试基础设施文档和systemd服务管理重构
03223ff docs: 在宪法中添加设计哲学引言
```

## Contact

- **开发负责人**: [待填写]
- **文档维护**: Claude Code (Sonnet 4.5)
- **最后更新**: 2026-01-14

---

<!-- MANUAL ADDITIONS START -->
<!-- 手动添加的内容放在这里 -->
<!-- MANUAL ADDITIONS END -->
