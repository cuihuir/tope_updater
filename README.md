# TOPE Updater — OTA Update Service

用于嵌入式 3D 打印机设备的 OTA (Over-The-Air) 更新服务。提供 HTTP API，支持固件/软件的下载、验证和部署，具备版本快照回滚、Qt/QML GUI 进度窗口和 systemd 集成。

![安装成功界面](docs/screenshots/gui_success.png)

> GUI 安装完成界面：左侧品牌 Logo、中部安装日志、右侧完成按钮与倒计时

## 项目状态（2026-02-28）

**当前分支**: `master`
**生产就绪度**: ~92%

| 功能模块 | 状态 |
|----------|------|
| 核心 OTA 流程（下载 → 验证 → 部署） | ✅ 完成 |
| 三层下载验证（Content-Length / size / MD5） | ✅ 完成 |
| 版本快照架构（符号链接原子切换） | ✅ 完成 |
| 两级自动回滚（previous → factory） | ✅ 完成 |
| systemd 服务管理（stop/start/status） | ✅ 完成 |
| 持久化状态管理（state.json + 重启自愈） | ✅ 完成 |
| Reporter 回调（device-api 进度上报） | ✅ 完成 |
| Qt/QML GUI 进度窗口（EGLFS） | ✅ 完成 |
| 单元测试覆盖率 91.47%（214 个测试） | ✅ 完成 |
| E2E 测试 | ⏳ 待完成 |

## 发货前 OTA 记录

本轮针对 beta 发货场景完成了普通应用/配置 OTA 能力复核、可靠性优化和真实 `printer-gui` 包测试。结论、包格式、测试记录、已知问题、GUI 切换方案和系统包升级策略见：

- [docs/SHIPMENT_OTA_NOTES.md](docs/SHIPMENT_OTA_NOTES.md)

## 快速开始

### 环境要求

- Python 3.11+
- Linux with systemd
- 生产设备推荐使用 arm64 Debian/Ubuntu 系发行版
- `printer-gui` runtime 已安装在 `/opt/tope/services/printer-gui/.venv`
  （updater-gui 复用该 PySide6 runtime）

### 生产安装（推荐）

生产设备优先使用 GitHub Release 里的 fat deb 包。deb 内置 updater 源码、
Python `.venv`、systemd unit、display-switcher、救援 TTY 热键和 console quiet
配置，避免在设备上逐个联网安装 Python 依赖。

```bash
# 1. 下载最新 release 里的 arm64 deb，例如：
wget https://github.com/cuihuir/tope_updater/releases/download/v0.1.1/tope-updater_0.1.1-1_arm64.deb

# 2. 使用当前登录用户安装。安装脚本会检测 SUDO_USER，
#    并把该用户 home 加入 tope-updater.service 的 ReadWritePaths。
sudo apt install ./tope-updater_0.1.1-1_arm64.deb

# 3. 确认服务
systemctl status tope-updater.service
curl -sS http://127.0.0.1:12315/api/v1.0/progress
```

安装后主要文件：

```text
/opt/tope/updater/                         # updater 程序、.venv、日志和临时目录
/etc/systemd/system/tope-updater.service   # OTA HTTP 服务，端口 12315
/etc/systemd/system/tope-updater-gui.service
/usr/local/bin/tope-display-switcher       # GUI/console 显示切换
/usr/local/bin/tope-console-hotkey         # Ctrl+Alt+F9 救援口 toggle
```

deb 安装会启用并启动：

- `tope-updater.service`
- `tope-console-quiet.service`
- `tope-console-hotkey.service`
- `getty@tty9.service`（救援口）

### 生产安装（源码脚本）

仅在没有 deb 包或需要临时调试时使用源码安装脚本。该方式会在目标设备上用 `uv`
创建 updater 自己的 `.venv`，因此依赖设备网络和 Python 包源。

```bash
git clone git@github.com:cuihuir/tope_updater.git
cd tope_updater
sudo ./deploy/install.sh
sudo systemctl start tope-updater.service
curl -sS http://127.0.0.1:12315/api/v1.0/progress
```

### 开发安装

```bash
# 安装依赖（uv 自动创建虚拟环境）
uv sync

# 开发环境（含测试工具）
uv sync --extra dev
```

### 运行服务

```bash
uv run src/updater/main.py
```

服务启动在 `http://localhost:12315`。

### 升级 updater 自身

下载新版本 deb 后直接覆盖安装：

```bash
sudo apt install ./tope-updater_<version>-1_arm64.deb
systemctl status tope-updater.service
curl -sS http://127.0.0.1:12315/api/v1.0/progress
```

如果使用源码安装：

```bash
git pull
sudo ./deploy/install.sh
sudo systemctl restart tope-updater.service
```

### 构建离线 deb

本仓库 tag 推送会自动触发 GitHub Actions 构建 arm64 deb 并上传到 Release：

```bash
git tag -a v0.1.2 -m "Release updater v0.1.2"
git push origin v0.1.2
```

本地构建需要准备包含 `.venv` 的 source root：

```bash
python3 scripts/build_updater_deb.py \
  --source-root /path/to/staged/tope-updater \
  --version 0.1.2 \
  --package-revision 1 \
  --arch arm64 \
  --output-dir dist
```

### API 使用示例

```bash
# 1. 触发下载
curl -X POST http://localhost:12315/api/v1.0/download \
  -H "Content-Type: application/json" \
  -d '{
    "version": "1.2.3",
    "package_url": "http://your-server/update.zip",
    "package_name": "update.zip",
    "package_size": 1048576,
    "package_md5": "abc123..."
  }'

# 2. 查询进度
curl http://localhost:12315/api/v1.0/progress

# 3. 触发安装（下载完成后）
curl -X POST http://localhost:12315/api/v1.0/update \
  -H "Content-Type: application/json" \
  -d '{"version": "1.2.3"}'
```

**进度响应示例：**
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "stage": "downloading",
    "progress": 45,
    "message": "Downloading package... 47.2 MB / 104.9 MB",
    "error": null
  }
}
```

**阶段枚举：** `idle` → `downloading` → `verifying` → `toInstall` → `installing` → `success` / `failed`

## 架构概览

### OTA 流程

```
POST /download ──→ downloading ──→ verifying ──→ toInstall
POST /update   ──→ installing  ──→ success / failed ──→ (65s) idle
```

### 版本快照目录结构

```
/opt/tope/versions/
├── v1.0.0/          # 出厂版本（只读 0555/0444）
├── v1.1.0/          # 历史版本
├── v1.2.0/          # 当前版本
├── current -> v1.2.0
├── previous -> v1.1.0
└── factory -> v1.0.0  # 最后防线，只读保护
```

符号链接使用 `temp + rename` 原子更新，切换延迟 < 1ms。

### 两级自动回滚

```
部署失败 → Level 1: rollback to previous
           Level 1 失败 → Level 2: rollback to factory
                          两级均失败 → 记录错误，需人工介入
```

### GUI 子进程

安装触发时启动独立 updater-gui systemd 服务，使用 Qt/QML + EGLFS 显示进度条、
终态倒计时和确认按钮。终态页面可手动确认进入系统，或等待倒计时自动返回。

## 测试

```bash
# 运行所有单元测试（含覆盖率）
uv run pytest tests/unit/ -v

# 运行全套测试
uv run pytest

# 代码检查
uv run ruff check src/ tests/
```

**当前测试状态：**
- 214 个单元测试，全部通过
- 覆盖率：**91.47%**（目标 80%）

| 文件 | 覆盖率 |
|------|--------|
| `routes.py` | 100% |
| `main.py` | 100% |
| `utils/logging.py` | 100% |
| `utils/verification.py` | 100% |
| `services/process.py` | 100% |
| `services/state_manager.py` | 95% |
| `services/version_manager.py` | 97% |
| `services/deploy.py` | 82% |
| `services/download.py` | 86% |
| GUI（已排除） | — |

## 项目结构

```
src/updater/
├── main.py                  # FastAPI 入口 + lifespan（端口 12315）
├── api/
│   ├── routes.py            # /download /update /progress
│   └── models.py            # Pydantic 请求/响应模型
├── services/
│   ├── download.py          # 异步下载（三层验证）
│   ├── deploy.py            # 版本快照部署（两级回滚）
│   ├── process.py           # systemd 管理
│   ├── reporter.py          # device-api 回调（单例）
│   ├── state_manager.py     # 状态持久化（单例）
│   └── version_manager.py   # 符号链接版本管理
├── models/
│   ├── manifest.py          # Manifest 数据模型
│   ├── state.py             # StateFile 数据模型
│   └── status.py            # StageEnum 枚举
├── gui/
│   ├── launcher.py          # GUI 子进程管理
│   ├── progress_window.py   # SDL2 主窗口 + 事件循环
│   ├── renderer.py          # 渲染（进度条/完成按钮/倒计时）
│   ├── layout.py            # 自适应布局配置
│   ├── assets/              # Logo PNG（多分辨率）
│   └── fonts/               # NotoSansCJKsc 字体
└── utils/
    ├── logging.py           # 轮转日志（10MB × 3）
    └── verification.py      # MD5 工具

tests/
├── conftest.py
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
├── e2e/                     # E2E 测试（待完成）
└── manual/                  # 手动测试脚本

docs/
├── DEPLOYMENT.md
└── ROLLBACK.md

deploy/                      # 部署脚本（symlink 设置、出厂版本等）
```

## 配置

所有配置均硬编码（嵌入式设备设计）：

| 参数 | 值 |
|------|----|
| 服务端口 | 12315 |
| device-api 端口 | 9080 |
| 下载临时目录 | `./tmp/` |
| 日志目录 | `./logs/` |
| 备份目录 | `./backups/` |
| 版本快照根目录 | `/opt/tope/versions/` |

## 已知限制

- **断点续传**：服务重启后重新下载（不自动续传），属于可选功能
- **E2E 测试**：单元测试完整，集成/E2E 测试待完成
- **systemd 服务文件**：`deploy/install.sh` 存在但需在目标设备验证

## License

Proprietary
