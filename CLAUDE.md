# tope_updater Development Guidelines

Last updated: 2026-01-28

## Project Overview

TOP.E OTA Updater - 防弹级 OTA 更新服务，用于嵌入式 3D 打印机设备的固件/软件更新。

**Current Branch**: `001-updater-core`
**Current Phase**: Phase 1-2 完成（Reporter + Version Snapshot），Phase 3+ 待规划

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
│   ├── deploy.py                # 部署服务 (版本快照 + 两级回滚) ⭐ 重构
│   ├── process.py               # systemd 服务管理 (stop/start/status)
│   ├── reporter.py              # device-api 回调服务 (单例) ⭐ 新增
│   ├── version_manager.py       # 版本快照管理 (符号链接) ⭐ 新增
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
├── testing-guide.md             # 测试基础设施指南
├── quickstart.md                # 快速开始指南
└── research.md                  # 技术调研

docs/                            # 文档目录 ⭐ 新增
├── DEPLOYMENT.md                # 部署指南
└── ROLLBACK.md                  # 回滚指南

deploy/                          # 部署脚本 ⭐ 新增
├── README.md                    # 脚本概述
├── SYMLINK_SETUP.md             # 符号链接配置指南
├── setup_symlinks.sh            # 符号链接设置脚本
├── create_factory_version.sh   # 出厂版本创建脚本
├── test_symlink_switch.sh       # 符号链接切换测试
├── verify_setup.sh              # 配置验证脚本
└── device-api.service.example   # systemd 服务示例

tests/
├── conftest.py                  # 全局 fixtures
├── unit/                        # 单元测试
│   ├── test_download.py
│   ├── test_state_manager.py
│   ├── test_deploy.py
│   └── test_version_manager.py  ⭐ 新增
├── integration/                 # 集成测试
│   └── test_reporter_integration.py ⭐ 新增
├── manual/                      # 手动测试脚本
│   ├── test_version_snapshot.py ⭐ 新增
│   └── test_two_level_rollback.py ⭐ 新增
└── reports/                     # 测试报告
    └── version_snapshot_test_report.md ⭐ 新增
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
Service Layer (download.py, deploy.py, process.py, version_manager.py)
    ↓
Data Layer (state_manager.py, models/)
```

### 2. 单例模式
- `StateManager` 使用单例模式确保全局状态一致
- `ReportService` 使用单例模式确保回调一致性
- 所有服务通过 `state_manager = StateManager()` 获取单例

### 3. 版本快照架构 ⭐ NEW (2026-01-28)

**核心设计**: 使用符号链接实现快速版本切换和可靠回滚

#### 3.1 目录结构
```
/opt/tope/versions/
├── v1.0.0/              # 版本快照（完整目录）
├── v1.1.0/              # 新版本快照
├── current -> v1.1.0/   # 当前版本（符号链接）
├── previous -> v1.0.0/  # 上一版本（符号链接）
└── factory -> v1.0.0/   # 出厂版本（符号链接，只读）
```

#### 3.2 原子符号链接更新
```python
# 使用 temp + rename 模式确保原子性
temp_link = Path(f".{link_name}.tmp.{os.getpid()}")
temp_link.symlink_to(target)
temp_link.replace(link_path)  # 原子操作
```

#### 3.3 两级回滚机制
```
部署失败
    ↓
Level 1: 回滚到 previous 版本
    ↓ (如果失败)
Level 2: 回滚到 factory 版本
    ↓ (如果失败)
手动干预
```

#### 3.4 设计优势
- ✅ **快速切换**: 符号链接切换 < 1ms
- ✅ **原子操作**: rename() 系统调用保证原子性
- ✅ **零停机**: 最小化服务重启时间
- ✅ **可靠回滚**: 两级回滚机制
- ✅ **空间高效**: 只保留必要版本
- ✅ **易于管理**: 清晰的版本历史

### 4. 错误处理
- 所有异常必须记录日志
- 用户可见错误使用结构化错误代码 (e.g., `DEPLOYMENT_FAILED`)
- 区分可恢复错误和致命错误
- 回滚失败时上报详细错误信息

## Design Decisions ⭐ NEW

### 决策 1: 为什么选择符号链接而不是文件级备份？

**背景**: 原始设计使用逐文件备份（`file.version.timestamp.bak`）

**问题**:
- 备份和恢复速度慢（需要复制所有文件）
- 难以管理版本历史
- 回滚时需要逐个文件恢复
- 无法快速切换版本

**决策**: 采用符号链接 + 版本快照架构

**理由**:
1. **性能**: 符号链接切换 < 1ms，文件复制需要数秒到数分钟
2. **原子性**: rename() 系统调用保证原子性，避免中间状态
3. **可靠性**: 版本目录完整保留，回滚时无需复制文件
4. **可维护性**: 清晰的版本历史，易于管理和调试
5. **行业标准**: Docker、Kubernetes 等都使用类似机制

**权衡**:
- ❌ 磁盘空间占用更多（保留完整版本目录）
- ✅ 但可以通过版本清理策略控制

**实施日期**: 2026-01-28

---

### 决策 2: 为什么需要两级回滚？

**背景**: 原始设计只有一级回滚（回滚到备份）

**问题**:
- 如果上一版本也有问题，系统无法恢复
- 没有"最后防线"保证系统可用

**决策**: 实现两级回滚机制（previous → factory）

**理由**:
1. **可靠性**: 出厂版本作为最后防线，保证系统始终可用
2. **自动恢复**: 无需人工干预即可恢复到稳定状态
3. **用户需求**: 用户明确要求"回退到上一个可用版本，如果版本还不可用就回退到出厂版本"
4. **行业实践**: 嵌入式系统通常保留出厂版本作为恢复手段

**权衡**:
- ❌ 增加了复杂度（需要管理 factory 版本）
- ✅ 但显著提高了系统可靠性

**实施日期**: 2026-01-28

---

### 决策 3: 为什么出厂版本需要只读保护？

**背景**: 出厂版本是系统的最后防线

**问题**:
- 如果出厂版本被意外修改或删除，系统将无法恢复
- 需要防止误操作

**决策**: 设置出厂版本为只读（0555 目录，0444 文件）

**理由**:
1. **防止误操作**: 只读权限防止意外修改或删除
2. **明确标识**: 只读权限清晰标识这是受保护的版本
3. **系统安全**: 即使 root 用户也需要显式移除保护才能修改

**权衡**:
- ❌ 更新出厂版本需要额外步骤（移除保护 → 更新 → 重新保护）
- ✅ 但这是有意为之，强制用户谨慎操作

**实施日期**: 2026-01-28

---

### 决策 4: 为什么 Reporter 使用单例模式？

**背景**: Reporter 需要在多个服务中使用

**问题**:
- 如果每个服务创建独立的 Reporter 实例，可能导致状态不一致
- HTTP 连接池管理复杂

**决策**: Reporter 使用单例模式

**理由**:
1. **状态一致性**: 全局唯一实例确保状态一致
2. **资源管理**: 共享 HTTP 连接池，避免资源浪费
3. **简化使用**: 服务只需 `reporter = ReportService()` 即可获取实例

**权衡**:
- ❌ 单例模式增加了测试复杂度（需要重置单例）
- ✅ 但通过 mock 可以解决测试问题

**实施日期**: 2026-01-27

---

### 决策 5: 为什么回滚失败不阻塞 Reporter？

**背景**: Reporter 需要上报回滚状态到 device-api

**问题**:
- 如果 device-api 不可用，Reporter 会失败
- 是否应该阻塞回滚操作？

**决策**: Reporter 失败不阻塞回滚操作

**理由**:
1. **可用性优先**: 回滚的目的是恢复系统，不应被上报失败阻塞
2. **防御性编程**: Reporter 捕获所有异常，记录日志但继续执行
3. **最终一致性**: device-api 恢复后可以通过 /progress 端点查询状态

**权衡**:
- ❌ device-api 可能无法实时感知回滚状态
- ✅ 但系统可用性更重要

**实施日期**: 2026-01-27

## Current Implementation Status

### ✅ Completed (Phase 1-2: Reporter + Version Snapshot)
- ✅ **Phase 1**: Reporter 集成 ⭐ NEW (2026-01-27)
  - ReportService 单例实现
  - 集成到 DownloadService 和 DeployService
  - 进度上报（每 5% 和阶段转换）
  - 错误上报（防御性错误处理）
  - 集成测试通过

- ✅ **Phase 2**: 版本快照架构 ⭐ NEW (2026-01-28)
  - VersionManager 实现（331 行）
  - 符号链接原子更新
  - 版本目录管理
  - 两级回滚机制
  - 出厂版本管理（只读保护）
  - DeployService 重构（793 行）
  - 部署脚本（setup_symlinks.sh, create_factory_version.sh 等）
  - 完整测试套件（10 个测试全部通过）
  - 文档完善（DEPLOYMENT.md, ROLLBACK.md）

### ✅ Previously Completed
- ✅ **Phase 1**: 项目初始化
- ✅ **Phase 2**: 基础组件
- ✅ **Phase 3**: 基本 OTA 流程 (下载 → 验证 → 部署)
- ✅ **Phase 5**: 原子部署（已被版本快照架构替代）
- ✅ **Phase 6**: systemd 服务管理 (stop/start/status)
- ✅ **Testing Infrastructure**: 完整的测试基础设施和单元测试
  - pytest 配置 (pytest.ini, pyproject.toml)
  - 全局 fixtures (conftest.py)
  - 单元测试 (test_download.py, test_state_manager.py, test_version_manager.py)
  - 测试 fixtures 和 mock 服务器
  - 手动测试脚本 (tests/manual/)
  - 测试报告 (tests/reports/)

### ⚠️ Partially Completed
- ⚠️ **Phase 4**: 断点续传 (可选功能，代码存在但未启用)
- ⚠️ **Phase 7**: 启动自愈增强 (部分实现)

### ❌ Not Started
- ❌ **Phase 9**: GUI 集成 (可选功能)
- ❌ **Phase 10**: 完善与测试 (持续进行中)

## Key Features Implemented

### 1. 版本快照架构 ⭐ NEW
```python
# 符号链接原子更新
temp_link = Path(f".current.tmp.{os.getpid()}")
temp_link.symlink_to("v1.1.0")
temp_link.replace("current")  # 原子操作，< 1ms

# 版本管理
version_manager.create_version_dir("1.1.0")
version_manager.promote_version("1.1.0")
version_manager.rollback_to_previous()
version_manager.rollback_to_factory()
```

### 2. 两级回滚机制 ⭐ NEW
```python
# Level 1: 回滚到上一版本
await deploy_service.rollback_to_previous(manifest)

# Level 2: 回滚到出厂版本（如果 Level 1 失败）
await deploy_service.rollback_to_factory(manifest)

# 自动回滚流程
try:
    await deploy_service.deploy_package(package_path, version)
except Exception as e:
    # 自动触发两级回滚
    await deploy_service.perform_two_level_rollback(manifest, e)
```

### 3. 三层下载验证
```python
# Layer 1: HTTP Content-Length
# Layer 2: 业务层 package_size
# Layer 3: MD5 完整性验证
```

### 4. Reporter 集成 ⭐ NEW
```python
# 单例模式
reporter = ReportService()

# 进度上报（每 5% 和阶段转换）
await reporter.report_progress("downloading", 45, "Downloading...")

# 错误上报（防御性处理，不阻塞操作）
await reporter.report_progress("failed", 0, "Deployment failed", error="DEPLOYMENT_FAILED")
```

### 5. 原子文件部署（已被版本快照替代）
```python
# 旧方案：temp 文件 → MD5 验证 → os.rename() → 原子替换
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

## Recent Changes (2026-01-28)

### Phase 1: Reporter 集成 (2026-01-27)
- 新增 `ReportService` 单例实现
- 集成到 `DownloadService` 和 `DeployService`
- 实现进度上报（每 5% 和阶段转换）
- 实现错误上报（防御性错误处理）
- 创建集成测试 `test_reporter_integration.py`

### Phase 2: 版本快照架构 (2026-01-28)
- 新增 `VersionManager` 服务（331 行）
  - `create_version_dir()` - 创建版本目录
  - `promote_version()` - 提升版本（更新符号链接）
  - `rollback_to_previous()` - 回滚到上一版本
  - `rollback_to_factory()` - 回滚到出厂版本
  - `create_factory_version()` - 创建出厂版本
  - `update_symlink()` - 原子符号链接更新
- 重构 `DeployService`（793 行）
  - 移除文件级备份逻辑
  - 新增版本快照部署
  - 新增两级回滚机制
  - `perform_two_level_rollback()` - 自动两级回滚
  - `verify_services_healthy()` - 服务健康检查
- 创建部署脚本
  - `setup_symlinks.sh` - 符号链接设置
  - `create_factory_version.sh` - 出厂版本创建
  - `test_symlink_switch.sh` - 符号链接切换测试
  - `verify_setup.sh` - 配置验证
  - `device-api.service.example` - systemd 服务示例
- 创建测试套件
  - `test_version_snapshot.py` - 版本快照基础测试（6 个测试）
  - `test_two_level_rollback.py` - 两级回滚集成测试（4 个测试）
  - `test_version_manager.py` - 单元测试（41 个测试）
  - 所有测试通过 ✅
- 创建文档
  - `docs/DEPLOYMENT.md` - 部署指南
  - `docs/ROLLBACK.md` - 回滚指南
  - `deploy/SYMLINK_SETUP.md` - 符号链接配置指南
  - `deploy/README.md` - 部署脚本概述
  - `tests/reports/version_snapshot_test_report.md` - 测试报告
- 更新文档
  - `README.md` - 添加版本快照架构章节
  - `CLAUDE.md` - 添加设计决策和架构原则

### Previous Changes (2026-01-14)

#### Phase 6: systemd 服务管理重构
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
