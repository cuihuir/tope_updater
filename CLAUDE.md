# tope_updater Development Guidelines

Last updated: 2026-02-28

## Project Overview

TOP.E OTA Updater — 用于嵌入式 3D 打印机设备的 OTA 更新服务。

**Current Branch**: `master`

## Tech Stack

- Python 3.11+, FastAPI + uvicorn, httpx, aiofiles
- Testing: pytest, pytest-asyncio, pytest-cov, pytest-mock, pytest-html
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
├── unit/                    # 单元测试（214 个，91.47% 覆盖率）
│   ├── test_deploy.py
│   ├── test_download.py
│   ├── test_logging.py
│   ├── test_main_lifespan.py
│   ├── test_process.py
│   ├── test_reporter.py
│   ├── test_routes.py
│   ├── test_state_manager.py
│   └── test_version_manager.py
├── integration/             # 集成测试（待完成）
├── e2e/                     # 端到端测试（tmp/e2e, logs/e2e, backups/e2e）
├── manual/                  # 手动测试脚本
└── reports/                 # 测试报告（htmlcov/，test-report.html）

docs/
├── DEPLOYMENT.md            # 部署指南
└── ROLLBACK.md              # 回滚指南

deploy/                      # 部署脚本（symlink 设置、出厂版本创建等）
```

## Commands

```bash
# 运行服务
uv run src/updater/main.py

# 测试（含覆盖率报告）
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
- 三栏布局：左(Logo) / 中(信息+日志) / 右(操作区)
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

## Test Coverage（当前状态）

```
214 个单元测试，全部通过，总覆盖率 91.47%

routes.py          100%
main.py            100%
utils/logging.py   100%
utils/verification 100%
services/process   100%
state_manager      95%
version_manager    97%
deploy.py          82%
download.py        86%
GUI（已排除）       —
```

### 测试配置关键点
- `.coveragerc`：排除 `src/updater/gui/*`（SDL2 GUI 无法在无头环境运行）
- `pytest.ini` 的 `markers` / `filterwarnings` / `log_cli` 必须在 `[pytest]` section 内
- `StateManager._instance = None` 和 `ReportService._instance = None` 在测试前后重置
- 异步测试使用 `asyncio_mode = auto`

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
| GUI 排除覆盖率 | SDL2 依赖显示器，无法在无头环境测试 |

## Git

- 分支：`master`（当前）
- Commit 格式：`feat/fix/docs/test/refactor/chore: 描述`
- 提交前向用户确认

# currentDate
Today's date is 2026-02-28.
