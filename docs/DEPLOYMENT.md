# TOP.E OTA Updater 部署指南

**版本**: 2.0.0 (版本快照架构)
**更新日期**: 2026-01-28
**适用环境**: 生产环境、测试环境

---

## 目录

1. [系统要求](#系统要求)
2. [初始部署](#初始部署)
3. [版本快照架构配置](#版本快照架构配置)
4. [出厂版本创建](#出厂版本创建)
5. [服务配置](#服务配置)
6. [验证部署](#验证部署)
7. [故障排查](#故障排查)

---

## 系统要求

### 硬件要求

- **CPU**: ARM/x86_64
- **内存**: 最小 512MB，推荐 1GB+
- **磁盘空间**: 最小 2GB 可用空间（用于版本快照）

### 软件要求

- **操作系统**: Linux (systemd)
- **Python**: 3.10+
- **systemd**: 版本 230+
- **权限**: root 或 sudo 权限

### 网络要求

- **Updater 端口**: 12315 (HTTP)
- **device-api 端口**: 9080 (HTTP)
- **出站连接**: 访问 OTA 包服务器

---

## 初始部署

### 1. 安装依赖

```bash
# 使用 uv 包管理器
curl -LsSf https://astral.sh/uv/install.sh | sh

# 克隆项目
git clone <repository-url> /opt/tope_updater
cd /opt/tope_updater

# 安装依赖
uv sync
```

### 2. 创建运行时目录

```bash
# 创建必要的目录
sudo mkdir -p /opt/tope/versions
sudo mkdir -p /opt/tope/services
sudo mkdir -p /usr/local/bin

# 创建 updater 工作目录
mkdir -p ./tmp
mkdir -p ./logs
mkdir -p ./backups

# 设置权限
sudo chown -R $USER:$USER /opt/tope
chmod 755 /opt/tope/versions
```

### 3. 部署初始版本

假设初始版本为 v1.0.0：

```bash
# 创建版本目录
sudo mkdir -p /opt/tope/versions/v1.0.0

# 部署应用文件（示例）
sudo cp -r /path/to/device-api /opt/tope/versions/v1.0.0/bin/
sudo cp -r /path/to/web-server /opt/tope/versions/v1.0.0/bin/
sudo cp -r /path/to/services /opt/tope/versions/v1.0.0/services/

# 设置权限
sudo chmod -R 755 /opt/tope/versions/v1.0.0
```

---

## 版本快照架构配置

### 1. 设置符号链接

使用提供的脚本自动配置：

```bash
cd /opt/tope_updater
sudo ./deploy/setup_symlinks.sh
```

或手动配置：

```bash
# 设置版本符号链接
cd /opt/tope/versions
sudo ln -sf v1.0.0 current
sudo ln -sf v1.0.0 previous

# 设置服务符号链接
cd /opt/tope/services
sudo ln -sf ../versions/current/services/device-api device-api
sudo ln -sf ../versions/current/services/web-server web-server

# 设置可执行文件符号链接
cd /usr/local/bin
sudo ln -sf /opt/tope/versions/current/bin/device-api device-api
sudo ln -sf /opt/tope/versions/current/bin/web-server web-server
```

### 2. 验证符号链接

```bash
# 检查版本链接
ls -la /opt/tope/versions/
# 应该看到：
# current -> v1.0.0
# previous -> v1.0.0

# 检查服务链接
ls -la /opt/tope/services/
# 应该看到：
# device-api -> ../versions/current/services/device-api

# 检查可执行文件链接
ls -la /usr/local/bin/device-api
# 应该看到：
# /usr/local/bin/device-api -> /opt/tope/versions/current/bin/device-api
```

### 3. 目录结构示例

完成后的目录结构：

```
/opt/tope/
├── versions/
│   ├── v1.0.0/              # 实际版本目录
│   │   ├── bin/
│   │   │   ├── device-api
│   │   │   └── web-server
│   │   └── services/
│   │       ├── device-api/
│   │       └── web-server/
│   ├── current -> v1.0.0/   # 当前版本
│   ├── previous -> v1.0.0/  # 上一版本
│   └── factory -> v1.0.0/   # 出厂版本（稍后创建）
└── services/
    ├── device-api -> ../versions/current/services/device-api
    └── web-server -> ../versions/current/services/web-server

/usr/local/bin/
├── device-api -> /opt/tope/versions/current/bin/device-api
└── web-server -> /opt/tope/versions/current/bin/web-server
```

### 4. 旧 GUI 设备迁移注意事项

2026-06-05 在 `192.168.123.227` 部署新版 updater 时确认：

- `tope-updater.service` 可以直接更新并重启，健康检查应返回 `stage=idle`。
- 新版 `tope-updater-gui.service` 按规范从
  `/opt/tope/services/printer-gui/.venv/bin/python` 启动。
- 如果设备尚未完成 GUI 规范迁移，`/opt/tope/services/printer-gui` 可能不存在。
  这种情况下首次迁移 OTA 开始前 updater-gui 可能无法显示，但 updater 会继续
  执行 OTA。
- 首次规范 GUI OTA 成功 promote 后，updater 会：
  1. 创建 `/opt/tope/services/<service>` 到
     `/opt/tope/versions/current/services/<service>` 的稳定链接；
  2. 从旧目录 `/home/tope/printer-gui-qml/.venv` 或
     `/home/tope/printer-gui/.venv` 迁移 `printer-gui` runtime；
  3. 安装 GUI 包内的 `deploy/printer-gui-eglfs.service` 到
     `/etc/systemd/system/printer-gui-eglfs.service`；
  4. 安装 GUI 包内的 `deploy/printer-gui-eglfs-start.sh` 到
     `/usr/local/bin/printer-gui-eglfs-start.sh`；
  5. 执行 `systemctl daemon-reload`，然后再启动服务。

部署新版 updater 后，确认以下项目：

```bash
curl -sS http://127.0.0.1:12315/api/v1.0/progress
systemctl cat tope-updater.service | grep ReadWritePaths
systemctl cat tope-updater-gui.service | grep /opt/tope/services/printer-gui
grep -R "def sync_service_links\|_normalize_runtime_environment" \
  /opt/tope/updater/src/updater/services
```

预期 `tope-updater.service` 的 `ReadWritePaths` 包含：

```text
/opt/tope /home/tope /etc/systemd/system /usr/local/bin
```

已知坑：

- `printer-gui-kol` 的 `v0.4.2` tag 包 manifest 已经部署到
  `/opt/tope/services/printer-gui`，但包内 `deploy/printer-gui-eglfs.service`
  和 `deploy/printer-gui-eglfs-start.sh` 仍是旧路径
  `/home/tope/printer-gui-qml`。updater 会按包内容安装这些 deploy 文件，
  因此服务会被覆盖回旧目录，表现为 OTA 成功但界面无变化。
- 修复方式是使用包含 `30db789 Normalize printer GUI OTA deploy paths`
  或之后提交的新 tag 包，或者手工安装已修正的 GUI service/start script 后
  `systemctl daemon-reload && systemctl restart printer-gui-eglfs.service`。
- `printer-gui-kol` 的 `v0.4.5` 增量包只包含 5 个变更文件。旧 updater 会把
  这个稀疏目录直接 promote 为 `/opt/tope/versions/current`，导致运行时缺少
  `api_client.py`、`main.qml` 等完整文件，GUI 进入 crash-loop。新版 updater
  会识别包内 `incremental.json`，先从 current 完整快照铺底，再覆盖变更文件和
  应用删除列表。
- systemd 服务如果配置了自动重启，`systemctl start` 后可能短暂显示 `active`，
  随后才因 Python import/QML 等错误退出。新版 updater 在启动服务后要求服务
  连续保持 active 一个稳定窗口；未通过会触发部署失败和回退。

### 5. 隐藏物理 console 文字

GUI 使用 EGLFS 独占显示设备，`printer-gui` 和 `updater-gui` 切换期间可能短暂
露出底层 Linux console。2026-06-05 在 `192.168.123.227` 上确认的处理方式：

- 禁用 `getty@tty1.service` 到 `getty@tty6.service`，避免常见
  `Ctrl+Alt+F1..F6` 试探出登录提示；
- 保留 `getty@tty9.service` 作为物理救援入口，可用 `Ctrl+Alt+F9` 切换到本机
  CLI。有些键盘需要按 `Ctrl+Alt+Fn+F9`；
- EGLFS 可能会关闭终端键盘模式，导致内核自己的 VT 快捷键不能直接切换。
  因此安装并启用 `tope-console-hotkey.service`，由它读取 `/dev/input/event*`：
  `Ctrl+Alt+F9` 在 GUI 和 console 之间往返切换，
  `Ctrl+Alt+F10` 显式执行 `tope-display-switcher show printer`；
- 安装 `/etc/systemd/logind.conf.d/99-tope-rescue-tty.conf`，关闭自动 VT 分配，
  只保留显式启用的 `tty9`；
- 安装并启用 `tope-console-quiet.service`，启动时清理 tty1/tty3/tty4/tty5/tty6、
  隐藏光标，并把 kernel printk 降到 `1 1 1 1`；
- 安装 `/etc/sysctl.d/99-tope-console-quiet.conf`，持久化 printk 设置；
- `tope-display-switcher` 在每次 `show updater`、`show printer`、`blank` 前后都会
  再清一次 tty，降低 EGLFS 交接空窗暴露 console 的概率。
- SSH 后台登录不受这套配置影响，GUI 故障时优先通过 SSH 登录排查。
- 如果已经能通过 SSH 登录，也可以执行 `sudo tope-display-switcher show console`。
  该命令会停止两个 EGLFS GUI 服务，恢复 tty 光标/printk，并确保
  `getty@tty9.service` 可用。
- 排查完成后执行 `sudo tope-display-switcher show printer` 回到生产 GUI。该命令
  会再次隐藏 tty1/tty3/tty4/tty5/tty6，并保留 tty9 救援入口。

验证命令：

```bash
systemctl is-enabled getty@tty1.service
systemctl is-active getty@tty1.service
systemctl is-enabled getty@tty9.service
systemctl is-active getty@tty9.service
systemctl is-enabled tope-console-hotkey.service
systemctl is-active tope-console-hotkey.service
systemctl is-enabled tope-console-quiet.service
systemctl is-active tope-console-quiet.service
cat /proc/sys/kernel/printk
sudo tope-display-switcher show updater
sudo tope-display-switcher show printer
sudo tope-display-switcher show console
sudo tope-display-switcher show printer
```

预期：

```text
getty@tty1.service: disabled
getty@tty1.service: inactive
getty@tty9.service: enabled
getty@tty9.service: active
tope-console-hotkey.service: enabled
tope-console-hotkey.service: active
tope-console-quiet.service: enabled
tope-console-quiet.service: active
/proc/sys/kernel/printk: 1 1 1 1
```

---

## 出厂版本创建

出厂版本是系统的最后防线，必须在生产部署前创建。

### 1. 创建出厂版本

```bash
cd /opt/tope_updater
sudo ./deploy/create_factory_version.sh
```

脚本会执行以下操作：
1. 检查当前版本
2. 创建 factory 符号链接
3. 设置只读权限（0555 目录，0444 文件）
4. 验证出厂版本

### 2. 手动创建（可选）

```bash
# 创建 factory 符号链接
cd /opt/tope/versions
sudo ln -sf v1.0.0 factory

# 设置只读权限
sudo chmod -R 0555 v1.0.0/  # 目录：r-xr-xr-x
sudo find v1.0.0/ -type f -exec chmod 0444 {} \;  # 文件：r--r--r--
```

### 3. 验证出厂版本

```bash
# 使用验证脚本
sudo ./deploy/verify_setup.sh

# 或手动验证
ls -la /opt/tope/versions/factory
# 应该看到：factory -> v1.0.0

# 检查权限
ls -ld /opt/tope/versions/v1.0.0
# 应该看到：dr-xr-xr-x (0555)
```

### 4. 出厂版本保护

⚠️ **重要**: 出厂版本设置为只读后，无法修改或删除。如需更新出厂版本：

```bash
# 1. 移除只读保护
sudo chmod -R 0755 /opt/tope/versions/v1.0.0

# 2. 更新文件
sudo cp new_files /opt/tope/versions/v1.0.0/

# 3. 重新设置只读
sudo chmod -R 0555 /opt/tope/versions/v1.0.0
sudo find /opt/tope/versions/v1.0.0 -type f -exec chmod 0444 {} \;
```

---

## 服务配置

### 1. 配置 systemd 服务

为每个服务创建 systemd 单元文件：

**device-api.service**:
```ini
[Unit]
Description=TOP.E Device API Service
After=network.target

[Service]
Type=simple
User=tope
Group=tope
WorkingDirectory=/opt/tope/services/device-api
ExecStart=/usr/local/bin/device-api
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**web-server.service**:
```ini
[Unit]
Description=TOP.E Web Server
After=network.target device-api.service
Requires=device-api.service

[Service]
Type=simple
User=tope
Group=tope
WorkingDirectory=/opt/tope/services/web-server
ExecStart=/usr/local/bin/web-server
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2. 安装服务

```bash
# 复制服务文件
sudo cp deploy/device-api.service.example /etc/systemd/system/device-api.service
sudo cp deploy/web-server.service.example /etc/systemd/system/web-server.service

# 重新加载 systemd
sudo systemctl daemon-reload

# 启用服务
sudo systemctl enable device-api.service
sudo systemctl enable web-server.service

# 启动服务
sudo systemctl start device-api.service
sudo systemctl start web-server.service
```

### 3. 验证服务

```bash
# 检查服务状态
sudo systemctl status device-api.service
sudo systemctl status web-server.service

# 查看日志
sudo journalctl -u device-api.service -f
```

### 4. 配置 OTA Updater 服务

**tope-updater.service**:
```ini
[Unit]
Description=TOP.E OTA Updater Service
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/tope_updater
ExecStart=/usr/bin/uv run src/updater/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# 安装 updater 服务
sudo cp deploy/tope-updater.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable tope-updater.service
sudo systemctl start tope-updater.service
```

---

## 验证部署

### 1. 运行验证脚本

```bash
cd /opt/tope_updater
sudo ./deploy/verify_setup.sh
```

验证脚本会检查：
- ✅ 版本目录结构
- ✅ 符号链接完整性
- ✅ 出厂版本配置
- ✅ 服务状态
- ✅ 文件权限

### 2. 手动验证清单

- [ ] 版本目录存在：`/opt/tope/versions/v1.0.0/`
- [ ] current 链接正确：`current -> v1.0.0`
- [ ] previous 链接正确：`previous -> v1.0.0`
- [ ] factory 链接正确：`factory -> v1.0.0`
- [ ] 出厂版本只读：`ls -ld /opt/tope/versions/v1.0.0` 显示 `dr-xr-xr-x`
- [ ] 服务链接正确：`ls -la /opt/tope/services/`
- [ ] 可执行文件链接正确：`ls -la /usr/local/bin/device-api`
- [ ] systemd 服务运行：`systemctl status device-api.service`
- [ ] updater 服务运行：`systemctl status tope-updater.service`
- [ ] API 端点响应：`curl http://localhost:12315/api/v1.0/progress`

### 3. 测试版本切换

```bash
# 测试符号链接切换
cd /opt/tope_updater
sudo ./deploy/test_symlink_switch.sh
```

---

## 故障排查

### 问题 1: 符号链接损坏

**症状**: 服务无法启动，提示文件不存在

**解决方案**:
```bash
# 检查符号链接
ls -la /opt/tope/versions/current
ls -la /usr/local/bin/device-api

# 重新创建符号链接
sudo ./deploy/setup_symlinks.sh
```

### 问题 2: 出厂版本无法创建

**症状**: `create_factory_version.sh` 失败

**解决方案**:
```bash
# 检查当前版本
ls -la /opt/tope/versions/current

# 确保版本目录存在
ls -la /opt/tope/versions/v1.0.0

# 手动创建
cd /opt/tope/versions
sudo ln -sf v1.0.0 factory
sudo chmod -R 0555 v1.0.0
```

### 问题 3: 服务无法启动

**症状**: `systemctl start` 失败

**解决方案**:
```bash
# 查看详细错误
sudo journalctl -u device-api.service -n 50

# 检查工作目录
ls -la /opt/tope/services/device-api

# 检查可执行文件
ls -la /usr/local/bin/device-api
file /usr/local/bin/device-api

# 检查权限
sudo chmod +x /opt/tope/versions/v1.0.0/bin/device-api
```

### 问题 4: 磁盘空间不足

**症状**: 部署失败，提示磁盘空间不足

**解决方案**:
```bash
# 检查磁盘使用
df -h /opt/tope

# 清理旧版本
cd /opt/tope/versions
sudo rm -rf v0.9.0  # 删除不需要的旧版本

# 保留规则：
# - 保留 current 指向的版本
# - 保留 previous 指向的版本
# - 保留 factory 指向的版本
# - 删除其他版本
```

### 问题 5: 权限错误

**症状**: 部署时提示权限被拒绝

**解决方案**:
```bash
# 检查目录所有者
ls -ld /opt/tope/versions

# 修复权限
sudo chown -R root:root /opt/tope/versions
sudo chmod 755 /opt/tope/versions

# updater 需要 root 权限运行
sudo systemctl restart tope-updater.service
```

---

## 生产环境检查清单

部署到生产环境前，请确认：

- [ ] 所有依赖已安装
- [ ] 版本目录结构正确
- [ ] 符号链接配置完成
- [ ] 出厂版本已创建并设置只读
- [ ] systemd 服务已配置并启用
- [ ] 服务依赖关系正确（web-server 依赖 device-api）
- [ ] 防火墙规则已配置（端口 12315, 9080）
- [ ] 日志轮转已配置
- [ ] 磁盘空间充足（至少 2GB 可用）
- [ ] 备份策略已制定
- [ ] 回滚流程已测试
- [ ] 监控告警已配置

---

## 相关文档

- [回滚指南](ROLLBACK.md) - 版本回滚操作指南
- [符号链接配置](../deploy/SYMLINK_SETUP.md) - 详细的符号链接配置说明
- [测试报告](../tests/reports/version_snapshot_test_report.md) - 版本快照测试结果

---

**维护者**: TOP.E 开发团队
**最后更新**: 2026-01-28
