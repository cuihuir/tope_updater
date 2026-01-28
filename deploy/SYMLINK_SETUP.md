# TOP.E OTA Updater - 符号链接配置指南

## 概述

本指南说明如何配置服务使用版本快照符号链接，实现快速版本切换和回滚。

## 目录结构

```
/opt/tope/
├── versions/                      # 版本快照目录
│   ├── v1.0.0/                   # 版本 1.0.0
│   │   ├── bin/
│   │   │   ├── device-api         # 服务二进制文件
│   │   │   └── web-server
│   │   └── services/
│   │       ├── device-api/        # 服务数据目录
│   │       └── web-server/
│   ├── v1.1.0/                   # 版本 1.1.0
│   ├── current -> v1.1.0/         # 当前运行版本（符号链接）
│   ├── previous -> v1.0.0/        # 上一版本（符号链接）
│   └── factory -> v1.0.0/         # 出厂版本（符号链接，只读）
└── services/                     # 服务符号链接目录
    ├── device-api -> ../versions/current/services/device-api
    └── web-server -> ../versions/current/services/web-server

/usr/local/bin/                   # 二进制符号链接目录
├── device-api -> /opt/tope/versions/current/bin/device-api
└── web-server -> /opt/tope/versions/current/bin/web-server
```

## 安装步骤

### 1. 创建版本快照

首次安装后，创建初始版本快照：

```bash
# 创建版本目录
sudo mkdir -p /opt/tope/versions/v1.0.0/bin
sudo mkdir -p /opt/tope/versions/v1.0.0/services

# 复制服务二进制文件
sudo cp /path/to/device-api /opt/tope/versions/v1.0.0/bin/
sudo cp /path/to/web-server /opt/tope/versions/v1.0.0/bin/

# 复制服务数据（如果有）
sudo cp -r /path/to/device-api-data /opt/tope/versions/v1.0.0/services/device-api

# 设置 current 符号链接
sudo ln -s /opt/tope/versions/v1.0.0 /opt/tope/versions/current
```

### 2. 运行符号链接设置脚本

```bash
cd /home/tope/project_py/tope_updater/deploy
sudo ./setup_symlinks.sh
```

此脚本会创建以下符号链接：
- `/usr/local/bin/*` → `/opt/tope/versions/current/bin/*`
- `/opt/tope/services/*` → `/opt/tope/versions/current/services/*`

### 3. 配置 systemd 服务

复制 `device-api.service.example` 到 systemd 目录：

```bash
# 复制服务文件
sudo cp deploy/device-api.service.example /etc/systemd/system/device-api.service

# 重新加载 systemd
sudo systemctl daemon-reload

# 启用服务
sudo systemctl enable device-api

# 启动服务
sudo systemctl start device-api
```

### 4. 设置出厂版本

```bash
cd /home/tope/project_py/tope_updater/deploy
sudo ./create_factory_version.sh 1.0.0
```

## 版本切换

### 切换到新版本

```bash
# 1. 部署新版本到独立目录（通过 OTA Updater）
# /opt/tope/versions/v1.1.0/

# 2. 更新 current 符号链接（原子操作）
sudo ln -sfn /opt/tope/versions/v1.1.0 /opt/tope/versions/current

# 3. 重启服务
sudo systemctl restart device-api
```

### 回滚到上一版本

```bash
# 方式 1: 使用回滚脚本（推荐）
python -c 'from updater.services.version_manager import VersionManager; \
           vm = VersionManager(); vm.rollback_to_previous()'

# 方式 2: 手动更新符号链接
sudo ln -sfn /opt/tope/versions/v1.0.0 /opt/tope/versions/current
sudo systemctl restart device-api
```

### 回滚到出厂版本

```bash
# 方式 1: 使用回滚脚本（推荐）
python -c 'from updater.services.version_manager import VersionManager; \
           vm = VersionManager(); vm.rollback_to_factory()'

# 方式 2: 手动更新符号链接
sudo ln -sfn /opt/tope/versions/v1.0.0 /opt/tope/versions/factory
sudo ln -sfn /opt/tope/versions/factory /opt/tope/versions/current
sudo systemctl restart device-api
```

## 测试

### 测试符号链接切换

```bash
cd /home/tope/project_py/tope_updater/deploy
sudo ./test_symlink_switch.sh
```

此脚本会：
1. 显示当前版本状态
2. 演示符号链接切换
3. 验证切换后的正确性
4. 切换回原版本

### 验证服务状态

```bash
# 检查服务状态
sudo systemctl status device-api

# 查看服务日志
sudo journalctl -u device-api -f

# 验证二进制文件版本
/usr/local/bin/device-api --version
```

## 优势

### 1. 快速回滚
- 符号链接切换是原子操作（毫秒级）
- 无需重新安装或复制文件
- 服务重启即可完成回滚

### 2. 版本隔离
- 每个版本独立目录，互不影响
- 可以同时保存多个版本
- 节省磁盘空间（文件去重）

### 3. 安全可靠
- 原子操作，避免中间状态
- 出厂版本只读保护
- 两级回滚策略（previous → factory）

### 4. 易于管理
- 集中化版本管理
- 清晰的版本历史
- 自动化脚本支持

## 故障排查

### 问题：服务启动失败

**症状**：
```bash
sudo systemctl start device-api
# Job failed. See "journalctl -xe" for details.
```

**解决方案**：
1. 检查符号链接是否正确：
   ```bash
   ls -l /usr/local/bin/device-api
   ls -l /opt/tope/services/device-api
   ```

2. 检查目标文件是否存在：
   ```bash
   readlink -f /usr/local/bin/device-api
   ls -l $(readlink -f /usr/local/bin/device-api)
   ```

3. 检查文件权限：
   ```bash
   ls -l /opt/tope/versions/current/bin/device-api
   ```

4. 查看详细日志：
   ```bash
   sudo journalctl -u device-api -n 50 --no-pager
   ```

### 问题：符号链接指向错误的版本

**症状**：
```bash
/usr/local/bin/device-api --version
# 显示版本 1.0.0，但期望 1.1.0
```

**解决方案**：
1. 检查 current 符号链接：
   ```bash
   readlink /opt/tope/versions/current
   ```

2. 更新 current 符号链接：
   ```bash
   sudo ln -sfn /opt/tope/versions/v1.1.0 /opt/tope/versions/current
   ```

3. 重新运行符号链接设置脚本：
   ```bash
   sudo ./deploy/setup_symlinks.sh
   ```

### 问题：权限被拒绝

**症状**：
```bash
/usr/local/bin/device-api: Permission denied
```

**解决方案**：
1. 检查文件权限：
   ```bash
   ls -l /opt/tope/versions/current/bin/device-api
   ```

2. 修复权限：
   ```bash
   sudo chmod 755 /opt/tope/versions/current/bin/device-api
   ```

3. 检查用户/组：
   ```bash
   sudo chown tope:tope /opt/tope/versions/current/bin/device-api
   ```

## 最佳实践

### 1. 定期备份
- 保留最近 3-5 个版本
- 定期清理旧版本
- 保持出厂版本不变

### 2. 测试新版本
- 在测试环境先验证
- 使用 previous 版本作为备份
- 保留回滚路径

### 3. 监控服务健康
- 使用 `systemctl` 监控服务状态
- 配置自动重启策略
- 设置告警规则

### 4. 文档记录
- 记录每个版本的变更
- 标注已知问题
- 记录回滚操作

## 相关文档

- [VersionManager API](../src/updater/services/version_manager.py)
- [DeployService 文档](../src/updater/services/deploy.py)
- [测试基础设施指南](../specs/001-updater-core/testing-guide.md)
- [快速开始指南](../specs/001-updater-core/quickstart.md)
