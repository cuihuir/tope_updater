# tope_updater Development Guidelines

Last updated: 2026-02-26

## Project Overview

TOP.E OTA Updater — 用于嵌入式 3D 打印机设备的 OTA 更新服务。

**Current Branch**: `002-gui`

## Tech Stack

- Python 3.11+, FastAPI + uvicorn, httpx, aiofiles
- Testing: pytest, pytest-asyncio, pytest-cov, pytest-mock
- Code Quality: ruff
- GUI: pysdl2 (SDL2)

## Project Structure

```
src/updater/
├── main.py                  # FastAPI 入口，端口 12315
├── api/
│   ├── routes.py            # 端点: /download, /update, /progress
│   └── models.py            # Pydantic 模型
├── services/
│   ├── download.py          # 异步下载（三层验证：Content-Length + size + MD5）
│   ├── deploy.py            # 部署（版本快照 + 两级回滚）
│   ├── process.py           # systemd 管理（stop/start/status）
│   ├── reporter.py          # device-api 回调（单例，防御性）
│   ├── version_manager.py   # 版本快照管理（符号链接原子更新）
│   └── state_manager.py     # 状态持久化（state.json，单例）
├── models/
│   ├── manifest.py          # Manifest 数据模型
│   ├── state.py             # StateFile 数据模型
│   └── status.py            # StageEnum 枚举
├── gui/
│   ├── launcher.py          # GUI 子进程管理
│   ├── progress_window.py   # SDL2 主窗口 + 事件循环
│   ├── renderer.py          # 渲染（logo/进度条/完成按钮/倒计时）
│   ├── layout.py            # 自适应布局配置
│   ├── assets/              # logo PNG（多分辨率）
│   └── fonts/               # NotoSansCJKsc 字体
└── utils/
    ├── logging.py           # 轮转日志（10MB × 3）
    └── verification.py      # MD5 工具

tests/
├── conftest.py              # 全局 fixtures
├── unit/                    # 单元测试
├── integration/             # 集成测试
├── e2e/                     # 端到端测试（tmp/e2e, logs/e2e, backups/e2e）
├── manual/                  # 手动测试脚本
└── reports/                 # 测试报告

docs/
├── DEPLOYMENT.md            # 部署指南
├── ROLLBACK.md              # 回滚指南
└── testing/                 # 设备测试文档

deploy/                      # 部署脚本（symlink 设置、出厂版本创建等）
```

## Commands

```bash
# 运行服务
uv run src/updater/main.py

# 测试
uv run pytest
uv run pytest tests/unit/ -v

# 代码检查 / 修复
uv run ruff check src/ tests/
uv run ruff check --fix src/ tests/
```

## Architecture

### OTA 流程
```
POST /download → downloading → verifying → toInstall
POST /update   → installing → success/failed → (65s后) idle
```

### Stage 枚举
`idle` → `downloading` → `verifying` → `toInstall` → `installing` → `success` / `failed`

### 版本快照
```
/opt/tope/versions/
├── vX.Y.Z/          # 完整版本目录
├── current -> vX.Y.Z
├── previous -> vX.Y.Z
└── factory -> vX.Y.Z  # 只读，最后防线
```
符号链接用 `temp + rename` 原子更新。部署失败自动两级回滚：previous → factory。

### GUI
- 安装触发时启动 SDL2 子进程（`GUILauncher`）
- success/failed 后显示 60s 倒计时 + "完成安装"按钮，点击立即退出
- `routes.py` 的 `finally` 无条件调用 `gui_launcher.stop()` 回收僵尸进程

### 单例
`StateManager()` 和 `ReportService()` 均为单例，直接实例化即可获取。

### 运行时目录
```
tmp/          # 下载临时文件
tmp/e2e/      # e2e 测试临时文件
logs/         # 轮转日志
logs/e2e/     # e2e 测试日志
backups/      # 部署备份
backups/e2e/  # e2e 测试备份
tmp/state.json  # 状态持久化
```

## Code Style

- 绝对导入：`from updater.services import X`
- 所有公共方法加类型注解和 docstring
- 所有 I/O 用 async/await
- 命名：`PascalCase` 类，`snake_case` 函数/变量，`UPPER_SNAKE_CASE` 常量

## Bug Tracking

`BUGS.md` 记录所有 bug，格式：BUG-XXX，状态：🔴 Open → 🟡 In Progress → 🟢 Fixed → ⚫ Closed

## Key Decisions

| 决策 | 原因 |
|------|------|
| 符号链接版本快照 | 原子切换 <1ms，可靠回滚，无需文件复制 |
| 两级回滚 | factory 版本作为最后防线，保证设备可用 |
| factory 只读 | 防止误操作破坏最后防线 |
| Reporter 防御性 | 回调失败不阻塞 OTA 主流程 |
| GUI 子进程 | 与 FastAPI 主进程隔离，崩溃不影响升级 |

## Git

- 分支：`002-gui`（当前），`master`（主分支）
- Commit 格式：`feat/fix/docs/test/refactor/chore: 描述`
- 提交前向用户确认
