# 实施计划：更新器核心 OTA 程序

**分支**: `001-updater-core` | **日期**: 2025-11-26 | **规格**: [spec_cn.md](./spec_cn.md)
**输入**: 功能规格来自 `/specs/001-updater-core/spec_cn.md`

**注意**: 本文档由 `/speckit.plan` 命令生成。执行工作流请参见 `.specify/templates/commands/plan.md`。

## 概述

为嵌入式 3D 打印机设备实现一个可靠的 OTA 更新器服务。更新器作为 systemd 服务运行，提供 HTTP API 端点用于触发下载和安装，实现支持断点续传的下载和 MD5 校验，执行原子文件部署，安全控制进程生命周期。使用 FastAPI 作为异步 HTTP 服务器，httpx 进行下载，通过 HTTP 回调与 device-api 通信，同时通过轮询端点服务 ota-gui。

## 技术背景

**语言/版本**: Python 3.11+
**主要依赖**: FastAPI 0.115.0（异步 HTTP 服务器），uvicorn 0.32.0（ASGI 服务器），httpx 0.27.0（异步 HTTP 客户端），Python 标准库（zipfile, hashlib, os, signal）
**存储**: 本地文件系统 - ./tmp/（临时下载、状态持久化），./logs/（轮转日志），./backups/（回滚支持）
**测试**: pytest 配合 pytest-asyncio 进行异步测试，httpx AsyncClient 进行 HTTP 端点测试
**目标平台**: Linux 嵌入式设备（ARM/x86），基于 systemd 的 init，已安装 Python 3.11+
**项目类型**: 单个 Python 服务（后台守护进程）
**性能目标**: GET /progress 响应 <100ms，回调 device-api 延迟 <500ms，RAM 峰值使用 <50MB，10Mbps 网络 → 100MB 包在 <5 分钟内完成
**约束条件**: 以 root 运行（进程控制 + 部署文件到系统目录），硬编码端口（updater:12315, device-api:9080），必须在更新中途断电后能恢复
**规模/范围**: 单设备部署，一次处理 1 个 OTA 操作，支持最大约 500MB 的包，每次更新 3-5 个模块
**HTTP 约定**: 仅使用 GET/POST 方法，HTTP 状态码始终返回 200，应用层状态码在响应体 `code` 字段中返回

## 宪法检查

*关卡: 必须在 Phase 0 研究前通过。Phase 1 设计后重新检查。*

### ✅ 原则 I: 核心使命（首要指令）
**状态**: 通过
**检查**: 功能范围限于：下载、校验（MD5）、部署（原子文件操作）、进程控制（SIGTERM/SIGKILL）、命令/状态的 HTTP API。除 OTA 外无业务逻辑。

### ⚠️ 原则 II: 最小化依赖
**状态**: 条件通过 - 需要论证
**违规**: 使用第三方库 FastAPI、uvicorn、httpx、aiofiles（总计约 15-20 个包）而不是 Python 标准库 `http.server` + `urllib`
**论证**（来自规格 FR-029 + 澄清）：
- **性能**: FastAPI 的异步模型防止在处理并发请求时阻塞（device-api 发送下载命令 + ota-gui 轮询进度）。标准库 `http.server` 使用线程模型，需要手动锁管理。
- **兼容性**: httpx 提供异步 HTTP Range 请求用于断点续传下载；`urllib` 需要阻塞 I/O 或复杂的线程处理。
- **安全性/可靠性**: Pydantic（FastAPI 依赖）自动验证请求载荷，减少容易出错的手动验证代码。aiofiles 防止大文件写入阻塞事件循环。
- **宪法条款**: 原则 II 允许"具有安全性/性能/兼容性论证"的例外 — 此处满足。

### ✅ 原则 III: 幂等操作
**状态**: 通过
**检查**: FR-001a 指定 `/download` 端点是幂等的（检查 state.json，如果相同 package_url 则恢复）。FR-010 原子文件部署（写临时文件 → 校验 → rename）。FR-024/025 启动时从未完成的操作恢复。

### ✅ 原则 IV: 原子文件操作
**状态**: 通过
**检查**: FR-010 强制要求临时文件 → MD5 校验 → `rename()` 系统调用进行原子提交。FR-011 替换前备份。FR-032 创建 ./backups/ 目录。

### ✅ 原则 V: 强制 MD5 校验
**状态**: 通过
**检查**: FR-004 计算下载包的 MD5 哈希。FR-005 不匹配时中止并返回 `MD5_MISMATCH` 错误。FR-001b 安装前校验 MD5。无跳过机制。

### ✅ 原则 VI: 清单驱动部署
**状态**: 通过
**检查**: FR-007 从包根目录解析 manifest.json。FR-008 验证路径（拒绝 `..` 和未授权的绝对路径）。FR-009 创建缺失的目标目录。FR-014 按清单指定的依赖顺序部署。

### ✅ 原则 VII: 安全进程控制
**状态**: 通过
**检查**: FR-012 发送 SIGTERM，等待 10 秒，然后如有需要发送 SIGKILL。FR-013 通过 `/proc/<pid>` 验证终止。FR-014 按依赖顺序重启（device-api 优先）。FR-020 报告进程控制失败。

### ✅ 原则 VIII: 可恢复操作（断点续传）
**状态**: 通过
**检查**: FR-003 实现基于 HTTP Range 的断点续传下载。FR-025 从 state.json 字节位置恢复。FR-026 如果状态损坏则回退到完整下载。

### ✅ 原则 IX: 资源保护
**状态**: 通过
**检查**: FR-021 流式下载到磁盘（无 RAM 缓冲）。SC-009 目标 <50MB RAM 峰值。使用异步 I/O 避免阻塞。FR-018 日志在 10MB 时轮转以防止磁盘耗尽。

### ✅ 原则 X: 全面错误报告
**状态**: 通过
**检查**: FR-016 POST 错误到 device-api `/api/v1.0/ota/report` 并附错误码（`MD5_MISMATCH`、`DISK_FULL`、`INVALID_MANIFEST` 等）。FR-020 包含描述性消息。FR-005 中止前报告错误。

### ✅ 原则 XI: 结构化日志
**状态**: 通过
**检查**: FR-017 记录到 `./logs/updater.log`。FR-018 在 10MB 时轮转，保留 3 个轮转。FR-019 包含 ISO 8601 时间戳和 DEBUG/INFO/WARN/ERROR 级别。

### ✅ 原则 XII: 双语文档
**状态**: 通过
**检查**: 规格同时存在 `spec.md`（英文）和 `spec_cn.md`（中文）。计划也提供两种语言版本。

**最终关卡状态**: ✅ 通过，有一个合理的例外（原则 II - FastAPI/httpx/aiofiles 使用由性能/兼容性论证）。

## 项目结构

### 文档（本功能）

```text
specs/001-updater-core/
├── plan.md              # 英文版本（/speckit.plan 输出）
├── plan_cn.md           # 本文件（原则 XII）
├── research.md          # Phase 0 输出（技术决策）
├── data-model.md        # Phase 1 输出（状态机、实体）
├── quickstart.md        # Phase 1 输出（开发设置）
├── contracts/           # Phase 1 输出（OpenAPI 规范）
│   ├── updater-api.yaml # Updater HTTP API（端口 12315）
│   └── device-api-callbacks.yaml # device-api 回调合约（端口 9080）
└── tasks.md             # Phase 2 输出（/speckit.tasks - 不由 /speckit.plan 创建）
```

### 源代码（仓库根目录）

```text
# 单个 Python 项目结构
src/
├── updater/
│   ├── __init__.py
│   ├── main.py              # FastAPI 应用 + uvicorn 启动
│   ├── api/
│   │   ├── __init__.py
│   │   ├── endpoints.py     # POST /download, POST /update, GET /progress
│   │   └── models.py        # Pydantic 请求/响应模型
│   ├── services/
│   │   ├── __init__.py
│   │   ├── download.py      # 使用 httpx 的异步下载，Range 支持
│   │   ├── verification.py  # MD5 计算
│   │   ├── deployment.py    # 原子文件操作，清单解析
│   │   ├── process_control.py # SIGTERM/SIGKILL，/proc 检查
│   │   └── state_manager.py # state.json 持久化，状态管理
│   ├── models/
│   │   ├── __init__.py
│   │   ├── manifest.py      # 清单数据结构
│   │   ├── state.py         # 状态文件结构
│   │   └── status.py        # 状态枚举（idle/downloading/等）
│   └── utils/
│       ├── __init__.py
│       ├── logging.py       # 轮转日志设置
│       └── callbacks.py     # HTTP POST 到 device-api

tests/
├── unit/
│   ├── test_download.py
│   ├── test_verification.py
│   ├── test_deployment.py
│   ├── test_process_control.py
│   └── test_state_manager.py
├── integration/
│   ├── test_full_ota_flow.py
│   ├── test_resume_download.py
│   └── test_power_failure_simulation.py
└── contract/
    ├── test_api_endpoints.py # 验证 OpenAPI 合约
    └── test_device_api_callbacks.py

# 部署文件（仓库根目录）
deploy/
├── tope-updater.service  # systemd 单元文件
└── install.sh            # 安装服务 + 创建目录的脚本
```

**结构决策**: 选择单个 Python 项目（选项 1），因为更新器是一个独立的后端服务，没有前端。所有代码都位于 `src/updater/` 模块中以保持简单。部署文件在 `deploy/` 中与源代码分离，以便打包清晰。

## HTTP API 设计约定

**简化原则**:
- **HTTP 方法**: 仅使用 GET（查询）和 POST（命令）
- **HTTP 状态码**: 所有响应始终返回 `200 OK`
- **应用层状态码**: 在响应体的 `code` 字段中返回业务状态码

**响应格式示例**:

```json
// 成功响应
{
  "code": 200,
  "msg": "success",
  "data": { ... }
}

// 错误响应（验证失败）
{
  "code": 400,
  "msg": "VALIDATION_ERROR: package_md5 must be 32-character hex string"
}

// 错误响应（操作冲突）
{
  "code": 409,
  "msg": "OPERATION_IN_PROGRESS: Cannot start download, installation in progress"
}

// 错误响应（MD5 校验失败，携带状态信息）
{
  "code": 500,
  "msg": "MD5_MISMATCH: expected a1b2c3d4..., got e5f6g7h8...",
  "stage": "verifying",
  "progress": 100
}
```

**应用层状态码定义**:
- `200`: 操作成功
- `400`: 请求参数验证失败
- `404`: 资源不存在
- `409`: 操作冲突（如另一操作正在进行）
- `500`: 内部错误（下载失败、MD5 不匹配、部署失败等）

## 复杂度跟踪

> **仅在宪法检查有必须论证的违规时填写**

| 违规 | 为何需要 | 被拒绝的更简单替代方案及原因 |
|------|----------|---------------------------|
| 原则 II: FastAPI + uvicorn + httpx + aiofiles（约 15-20 个包） | 并发操作需要异步 I/O 以避免阻塞：device-api 发送下载命令的同时 ota-gui 轮询进度端点。线程模型（使用标准库 `http.server`）中的手动锁管理容易出错，违反原则 I（简单 = 可靠）。| Python 标准库 `http.server` + `urllib`: 需要线程 + 手动锁来管理共享状态，下载的阻塞 I/O 阻止大文件下载期间 /progress 端点的响应，没有内置请求验证（手动 JSON 解析容易出错）。被拒绝是因为异步模型对于这种并发场景*更简单*。|

## Phase 0: 研究

**目标**: 解决技术背景中的所有未知问题，记录技术选择的理由。

**输出**: `research.md` - 包含以下内容：

1. **FastAPI 项目结构最佳实践**
   - 分层架构：api/（路由）+ services/（业务逻辑）+ models/（数据结构）
   - 依赖注入模式用于共享资源（StateManager 单例）
   - 生命周期管理（启动/关闭钩子）

2. **httpx 断点续传下载**
   - HTTP Range 请求头：`Range: bytes=<start>-`
   - 响应状态码 206（部分内容）vs 200（完整）
   - 增量 MD5 计算（继续现有哈希对象）
   - 错误处理：416 Range Not Satisfiable → 重新开始

3. **systemd 服务配置**
   - Type=simple（前台进程）
   - Restart=always + RestartSec=10
   - 资源限制：MemoryMax, CPUQuota
   - 安全加固：PrivateTmp, ProtectSystem, CapabilityBoundingSet
   - 优雅关闭：TimeoutStopSec=30, KillSignal=SIGTERM

**状态**: ✅ 完成（参见 research.md）

## Phase 1: 设计与合约

**前提条件**: `research.md` 完成

**输出**:

1. **data-model.md** - 实体、状态机、验证规则
   - 实体：Update Package, Manifest, Module, Status State, State File
   - OTA 生命周期状态机（idle → downloading → verifying → installing → success/failed）
   - Pydantic 模型定义（用于请求/响应验证）
   - 关系图和状态转换表

2. **contracts/updater-api.yaml** - Updater HTTP API 的 OpenAPI 3.0 规范
   - POST /api/v1.0/download（触发下载）
   - POST /api/v1.0/update（触发安装）
   - GET /api/v1.0/progress（查询状态）
   - 请求/响应架构、应用层状态码、示例

3. **contracts/device-api-callbacks.yaml** - device-api 回调端点的 OpenAPI 3.0 规范
   - POST /api/v1.0/ota/report（接收更新器状态）
   - 回调触发条件（每 5% 进度，状态转换，错误）

4. **quickstart.md** - 开发环境设置和部署指南
   - 前提条件（Python 3.11+, systemd）
   - 安装步骤（虚拟环境，依赖，目录）
   - 本地运行（开发模式 + API 测试）
   - Mock 服务（device-api 接收器，包服务器）
   - systemd 服务部署
   - 故障排查

5. **代理上下文更新**
   - 运行 `.specify/scripts/bash/update-agent-context.sh claude`
   - 将 FastAPI/uvicorn/httpx/aiofiles 添加到 CLAUDE.md

**状态**: ✅ 完成

**Phase 1 后宪法重新评估**:
- ✅ 原则 II: 确认依赖为 FastAPI/uvicorn/httpx/aiofiles + 传递依赖（~15-20 包）
- ✅ 所有其他原则：设计文档确认符合性

## Phase 2: 任务（不在本命令范围内）

**注意**: Phase 2 由单独的 `/speckit.tasks` 命令执行。

**将生成**: `tasks.md` - 按依赖顺序排列的可执行任务清单：
1. 设置项目骨架（目录、__init__.py）
2. 实现数据模型（Pydantic 模型）
3. 实现服务（download, verification, deployment, process_control, state_manager）
4. 实现 API 端点（endpoints.py + FastAPI 路由）
5. 实现工具（logging, callbacks）
6. 编写单元测试
7. 编写集成测试
8. 创建 systemd 服务单元
9. 编写安装脚本

## 后续步骤

1. **运行** `/speckit.tasks` 生成 `tasks.md`
2. **实施** tasks.md 中的任务
3. **测试** 使用 mock 服务进行全流程 OTA 测试
4. **部署** 到测试设备进行现场测试
5. **迭代** 基于测试结果修复问题

## 参考

- [功能规格（中文）](./spec_cn.md) - 完整功能需求
- [功能规格（英文）](./spec.md) - 英文版功能需求
- [实施计划（英文）](./plan.md) - 英文版本计划
- [数据模型](./data-model.md) - 实体、状态机、验证规则
- [Updater API 合约](./contracts/updater-api.yaml) - OpenAPI 规范
- [device-api 回调](./contracts/device-api-callbacks.yaml) - 回调端点合约
- [快速开始](./quickstart.md) - 开发环境设置
- [宪法](../../.specify/memory/constitution.md) - 核心原则和治理
