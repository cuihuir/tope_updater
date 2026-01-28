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
