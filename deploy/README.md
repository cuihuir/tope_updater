# TOP.E OTA Updater - 部署脚本

本目录包含用于配置和管理 TOP.E OTA Updater 版本快照的部署脚本。

## 📁 脚本列表

### 1. setup_symlinks.sh
设置服务符号链接，将二进制文件和服务目录指向版本快照目录。

**功能**：
- 创建 `/usr/local/bin/*` 符号链接
- 创建 `/opt/tope/services/*` 符号链接
- 验证链接正确性

**使用方法**：
```bash
sudo ./setup_symlinks.sh
```

**何时运行**：
- 首次安装后
- 添加新服务后
- 符号链接损坏时

### 2. create_factory_version.sh
创建出厂版本快照并设置只读保护。

**功能**：
- 从当前版本复制内容
- 设置 factory 符号链接
- 递归设置只读权限
- 验证完整性

**使用方法**：
```bash
sudo ./create_factory_version.sh 1.0.0
```

**何时运行**：
- 系统首次部署后
- 只需运行一次

**注意**：
- 出厂版本只能设置一次
- 确保在稳定版本上创建

### 3. test_symlink_switch.sh
测试符号链接切换功能。

**功能**：
- 演示版本切换
- 验证原子性
- 检查链接正确性

**使用方法**：
```bash
sudo ./test_symlink_switch.sh
```

**何时运行**：
- 验证配置是否正确
- 测试版本切换流程

## 🚀 快速开始

### 首次安装

```bash
# 1. 进入部署目录
cd /home/tope/project_py/tope_updater/deploy

# 2. 创建版本快照目录
sudo mkdir -p /opt/tope/versions/v1.0.0/{bin,services}

# 3. 复制服务文件
sudo cp /path/to/device-api /opt/tope/versions/v1.0.0/bin/
sudo cp /path/to/web-server /opt/tope/versions/v1.0.0/bin/

# 4. 设置 current 符号链接
sudo ln -s /opt/tope/versions/v1.0.0 /opt/tope/versions/current

# 5. 设置服务符号链接
sudo ./setup_symlinks.sh

# 6. 配置 systemd 服务
sudo cp device-api.service.example /etc/systemd/system/device-api.service
sudo systemctl daemon-reload
sudo systemctl enable device-api

# 7. 创建出厂版本
sudo ./create_factory_version.sh 1.0.0

# 8. 启动服务
sudo systemctl start device-api

# 9. 验证状态
sudo systemctl status device-api
```

### 升级到新版本

```bash
# 1. OTA Updater 会自动创建新版本目录
# /opt/tope/versions/v1.1.0/

# 2. 切换到新版本（原子操作）
sudo ln -sfn /opt/tope/versions/v1.1.0 /opt/tope/versions/current

# 3. 重启服务
sudo systemctl restart device-api
```

### 回滚到上一版本

```bash
# 使用 Python API（推荐）
python -c '
from updater.services.version_manager import VersionManager
vm = VersionManager()
vm.rollback_to_previous()
'

# 或手动更新符号链接
sudo ln -sfn /opt/tope/versions/v1.0.0 /opt/tope/versions/current
sudo systemctl restart device-api
```

### 回滚到出厂版本

```bash
# 使用 Python API（推荐）
python -c '
from updater.services.version_manager import VersionManager
vm = VersionManager()
vm.rollback_to_factory()
'

# 或手动更新符号链接
sudo ln -sfn /opt/tope/versions/factory /opt/tope/versions/current
sudo systemctl restart device-api
```

## 📋 验证清单

完成安装后，使用此清单验证配置：

- [ ] `/opt/tope/versions/current` 符号链接存在
- [ ] `/opt/tope/versions/previous` 符号链接存在（如果有上一版本）
- [ ] `/opt/tope/versions/factory` 符号链接存在
- [ ] `/usr/local/bin/device-api` 符号链接存在并指向 current
- [ ] `/opt/tope/services/device-api` 符号链接存在并指向 current
- [ ] systemd 服务正常运行：
  ```bash
  systemctl status device-api
  ```
- [ ] 服务可以正常重启：
  ```bash
  systemctl restart device-api
  systemctl status device-api
  ```

## 🔧 故障排查

### 符号链接问题

```bash
# 检查符号链接
ls -l /usr/local/bin/device-api
ls -l /opt/tope/services/device-api

# 查看链接目标
readlink -f /usr/local/bin/device-api

# 重新创建符号链接
sudo ./setup_symlinks.sh
```

### 版本切换问题

```bash
# 查看当前版本
readlink /opt/tope/versions/current

# 切换版本
sudo ln -sfn /opt/tope/versions/v1.0.0 /opt/tope/versions/current

# 重启服务
sudo systemctl restart device-api
```

### 服务启动失败

```bash
# 查看详细日志
sudo journalctl -u device-api -n 50 --no-pager

# 检查文件权限
ls -l /opt/tope/versions/current/bin/device-api

# 修复权限
sudo chmod 755 /opt/tope/versions/current/bin/device-api
```

## 📚 相关文档

- [符号链接配置详细指南](./SYMLINK_SETUP.md)
- [VersionManager API 文档](../src/updater/services/version_manager.py)
- [快速开始指南](../specs/001-updater-core/quickstart.md)
- [测试基础设施指南](../specs/001-updater-core/testing-guide.md)

## ⚠️ 注意事项

1. **权限要求**：所有脚本需要 root 权限运行
2. **一次性操作**：出厂版本只能设置一次
3. **原子性**：版本切换使用原子操作，安全可靠
4. **备份**：保留至少 previous 和 factory 版本用于回滚

## 🎯 最佳实践

1. **测试先行**：在测试环境验证新版本
2. **渐进升级**：先升级非关键服务
3. **监控日志**：升级后检查服务日志
4. **保留回滚路径**：始终保留 previous 版本
5. **定期清理**：删除不需要的旧版本

## 💡 提示

- 符号链接切换是原子操作（毫秒级）
- 服务重启通常在几秒内完成
- 两个版本可以共享相同文件节省空间
- 出厂版本应保持稳定不变
