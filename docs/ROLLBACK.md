# TOP.E OTA Updater 回滚指南

**版本**: 2.0.0 (两级回滚机制)
**更新日期**: 2026-01-28
**适用场景**: 部署失败、版本问题、紧急回退

---

## 目录

1. [回滚机制概述](#回滚机制概述)
2. [自动回滚](#自动回滚)
3. [手动回滚](#手动回滚)
4. [回滚验证](#回滚验证)
5. [故障排查](#故障排查)
6. [最佳实践](#最佳实践)

---

## 回滚机制概述

TOP.E OTA Updater 实现了两级自动回滚机制，确保系统在部署失败时能够自动恢复到可用状态。

### 回滚层级

```
部署失败
    ↓
Level 1: 回滚到上一版本 (previous)
    ↓ (如果失败)
Level 2: 回滚到出厂版本 (factory)
    ↓ (如果失败)
手动干预
```

### 版本状态

系统维护三个版本指针：

- **current**: 当前运行的版本
- **previous**: 上一个稳定版本
- **factory**: 出厂版本（最后防线）

```
/opt/tope/versions/
├── v1.0.0/              # 出厂版本
├── v1.1.0/              # 上一版本
├── v1.2.0/              # 当前版本（部署失败）
├── current -> v1.2.0    # 当前指针
├── previous -> v1.1.0   # 上一版本指针
└── factory -> v1.0.0    # 出厂版本指针
```

---

## 自动回滚

### Level 1: 回滚到上一版本

当部署失败时，系统自动执行 Level 1 回滚。

#### 触发条件

- 文件部署失败（权限错误、磁盘满等）
- MD5 校验失败
- 服务启动失败
- 任何部署过程中的异常

#### 回滚流程

```
1. 检测部署失败
   ↓
2. 清理失败的版本目录
   ↓
3. 切换 current -> previous
   ↓
4. 重启服务
   ↓
5. 验证服务健康（30s 超时）
   ↓
6. 上报回滚状态到 device-api
```

#### 日志示例

```
[ERROR] Deployment failed: Simulated deployment failure
[INFO] Cleaning up failed version directory: /opt/tope/versions/v1.2.0
[INFO] Deployment failed, initiating two-level rollback
[INFO] Starting Level 1 rollback: rolling back to previous version
[INFO] Stopping services: ['device-api.service']
[INFO] Rolling back to previous version: 1.1.0
[INFO] Updating current symlink to v1.1.0
[INFO] Starting services: ['device-api.service']
[INFO] Verifying service health...
[INFO] ✓ Rolled back to previous version 1.1.0
```

#### 预期结果

- ✅ current 指向 previous 版本
- ✅ 服务正常运行
- ✅ device-api 收到回滚通知
- ✅ 失败的版本目录被清理

---

### Level 2: 回滚到出厂版本

当 Level 1 回滚失败时（例如上一版本也有问题），系统自动执行 Level 2 回滚。

#### 触发条件

- Level 1 回滚后服务启动失败
- Level 1 回滚后服务健康检查失败
- previous 版本损坏或不可用

#### 回滚流程

```
1. Level 1 回滚失败
   ↓
2. 切换 current -> factory
   ↓
3. 重启服务
   ↓
4. 验证服务健康（30s 超时）
   ↓
5. 上报回滚状态到 device-api
```

#### 日志示例

```
[ERROR] Level 1 rollback failed: Service health check failed
[INFO] Starting Level 2 rollback: rolling back to factory version
[INFO] Stopping services: ['device-api.service']
[INFO] Rolling back to factory version: 1.0.0
[INFO] Updating current symlink to v1.0.0
[INFO] Starting services: ['device-api.service']
[INFO] Verifying service health...
[INFO] ✓ Rolled back to factory version 1.0.0
```

#### 预期结果

- ✅ current 指向 factory 版本
- ✅ 服务正常运行
- ✅ device-api 收到紧急回滚通知
- ⚠️ 系统运行在出厂版本（可能缺少新功能）

---

### 手动干预

如果两级回滚都失败，系统会记录错误并等待人工介入。

#### 错误日志

```
[CRITICAL] DEPLOYMENT_FAILED + ROLLBACK_LEVEL_1_FAILED + ROLLBACK_LEVEL_2_FAILED
[CRITICAL] Manual intervention required
[ERROR] All rollback attempts failed. System may be in inconsistent state.
```

#### 处理步骤

参见 [手动回滚](#手动回滚) 章节。

---

## 手动回滚

在某些情况下，可能需要手动执行回滚操作。

### 场景 1: 回滚到上一版本

```bash
# 1. 停止 updater 服务
sudo systemctl stop tope-updater.service

# 2. 检查当前版本
ls -la /opt/tope/versions/current
# current -> v1.2.0

ls -la /opt/tope/versions/previous
# previous -> v1.1.0

# 3. 停止应用服务
sudo systemctl stop device-api.service
sudo systemctl stop web-server.service

# 4. 切换版本（原子操作）
cd /opt/tope/versions
sudo ln -sfn v1.1.0 .current.tmp
sudo mv -f .current.tmp current

# 5. 启动应用服务
sudo systemctl start device-api.service
sudo systemctl start web-server.service

# 6. 验证服务
sudo systemctl status device-api.service
curl http://localhost:9080/health

# 7. 启动 updater 服务
sudo systemctl start tope-updater.service
```

### 场景 2: 回滚到出厂版本

```bash
# 1. 停止所有服务
sudo systemctl stop tope-updater.service
sudo systemctl stop device-api.service
sudo systemctl stop web-server.service

# 2. 检查出厂版本
ls -la /opt/tope/versions/factory
# factory -> v1.0.0

# 3. 切换到出厂版本
cd /opt/tope/versions
sudo ln -sfn v1.0.0 .current.tmp
sudo mv -f .current.tmp current

# 4. 启动服务
sudo systemctl start device-api.service
sudo systemctl start web-server.service
sudo systemctl start tope-updater.service

# 5. 验证
sudo systemctl status device-api.service
curl http://localhost:9080/health
```

### 场景 3: 回滚到指定版本

```bash
# 1. 列出可用版本
ls -la /opt/tope/versions/
# v1.0.0  v1.1.0  v1.2.0  v1.3.0

# 2. 选择目标版本（例如 v1.1.0）
TARGET_VERSION="v1.1.0"

# 3. 停止服务
sudo systemctl stop device-api.service
sudo systemctl stop web-server.service

# 4. 切换版本
cd /opt/tope/versions
sudo ln -sfn $TARGET_VERSION .current.tmp
sudo mv -f .current.tmp current

# 5. 更新 previous 指针（可选）
sudo ln -sfn v1.0.0 .previous.tmp
sudo mv -f .previous.tmp previous

# 6. 启动服务
sudo systemctl start device-api.service
sudo systemctl start web-server.service

# 7. 验证
sudo systemctl status device-api.service
```

---

## 回滚验证

### 1. 检查符号链接

```bash
# 查看当前版本
ls -la /opt/tope/versions/current
# 应该指向回滚后的版本

# 查看所有版本指针
ls -la /opt/tope/versions/ | grep "^l"
# current -> v1.1.0
# previous -> v1.0.0
# factory -> v1.0.0
```

### 2. 验证服务状态

```bash
# 检查服务运行状态
sudo systemctl status device-api.service
sudo systemctl status web-server.service

# 应该显示：Active: active (running)
```

### 3. 验证服务健康

```bash
# 测试 API 端点
curl http://localhost:9080/health
# 应该返回 200 OK

curl http://localhost:12315/api/v1.0/progress
# 应该返回当前状态
```

### 4. 检查日志

```bash
# 查看 updater 日志
tail -f /opt/tope_updater/logs/updater.log

# 查看服务日志
sudo journalctl -u device-api.service -f
sudo journalctl -u web-server.service -f
```

### 5. 验证版本信息

```bash
# 查询当前版本
curl http://localhost:9080/api/version
# 应该返回回滚后的版本号

# 或检查版本文件
cat /opt/tope/versions/current/VERSION
```

---

## 故障排查

### 问题 1: 回滚后服务无法启动

**症状**: `systemctl start` 失败

**诊断**:
```bash
# 查看详细错误
sudo journalctl -u device-api.service -n 50

# 检查符号链接
ls -la /opt/tope/versions/current
ls -la /usr/local/bin/device-api

# 检查文件权限
ls -la /opt/tope/versions/current/bin/device-api
```

**解决方案**:
```bash
# 重新创建符号链接
sudo /opt/tope_updater/deploy/setup_symlinks.sh

# 修复权限
sudo chmod +x /opt/tope/versions/current/bin/device-api

# 重启服务
sudo systemctl restart device-api.service
```

---

### 问题 2: 符号链接损坏

**症状**: 符号链接指向不存在的目录

**诊断**:
```bash
# 检查符号链接
ls -la /opt/tope/versions/current
# current -> v1.2.0 (红色，表示目标不存在)

# 列出可用版本
ls -d /opt/tope/versions/v*
```

**解决方案**:
```bash
# 手动修复符号链接
cd /opt/tope/versions
sudo rm current
sudo ln -sf v1.1.0 current

# 或使用脚本
sudo /opt/tope_updater/deploy/setup_symlinks.sh
```

---

### 问题 3: 出厂版本损坏

**症状**: Level 2 回滚失败

**诊断**:
```bash
# 检查出厂版本
ls -la /opt/tope/versions/factory
ls -la /opt/tope/versions/v1.0.0

# 验证文件完整性
find /opt/tope/versions/v1.0.0 -type f | wc -l
```

**解决方案**:
```bash
# 如果出厂版本损坏，需要从备份恢复
# 1. 从备份恢复出厂版本
sudo tar -xzf /backup/factory_v1.0.0.tar.gz -C /opt/tope/versions/

# 2. 重新创建出厂版本
sudo /opt/tope_updater/deploy/create_factory_version.sh

# 3. 验证
sudo /opt/tope_updater/deploy/verify_setup.sh
```

---

### 问题 4: 磁盘空间不足导致回滚失败

**症状**: 回滚时提示磁盘空间不足

**诊断**:
```bash
# 检查磁盘使用
df -h /opt/tope

# 查看版本目录大小
du -sh /opt/tope/versions/*
```

**解决方案**:
```bash
# 清理不需要的版本（保留 current, previous, factory）
cd /opt/tope/versions

# 列出所有版本
ls -d v*

# 删除旧版本（示例：删除 v0.9.0）
sudo rm -rf v0.9.0

# 清理 updater 临时文件
sudo rm -rf /opt/tope_updater/tmp/*
sudo rm -rf /opt/tope_updater/backups/*
```

---

### 问题 5: 服务依赖问题

**症状**: web-server 启动失败，因为 device-api 未运行

**诊断**:
```bash
# 检查服务依赖
systemctl list-dependencies web-server.service

# 检查 device-api 状态
sudo systemctl status device-api.service
```

**解决方案**:
```bash
# 按正确顺序启动服务
sudo systemctl start device-api.service
sleep 5
sudo systemctl start web-server.service

# 或使用 systemd 依赖自动处理
sudo systemctl restart web-server.service
# systemd 会自动先启动 device-api
```

---

## 最佳实践

### 1. 回滚前准备

- ✅ 确认出厂版本已创建并验证
- ✅ 定期备份关键版本
- ✅ 记录每个版本的变更日志
- ✅ 测试环境先验证回滚流程

### 2. 回滚操作

- ✅ 使用原子操作（ln -sfn + mv）
- ✅ 先停止服务，再切换版本
- ✅ 验证服务健康后再继续
- ✅ 记录回滚原因和时间

### 3. 回滚后验证

- ✅ 检查所有服务状态
- ✅ 测试关键功能
- ✅ 查看错误日志
- ✅ 通知相关人员

### 4. 版本管理

- ✅ 保留最近 3 个版本（current, previous, factory）
- ✅ 定期清理旧版本释放空间
- ✅ 不要删除 factory 指向的版本
- ✅ 不要删除 current 或 previous 指向的版本

### 5. 监控告警

- ✅ 监控回滚事件
- ✅ 设置回滚失败告警
- ✅ 跟踪回滚频率
- ✅ 分析回滚原因

---

## 回滚决策树

```
部署失败？
    ├─ 是 → 自动触发 Level 1 回滚
    │       ├─ 成功 → 完成
    │       └─ 失败 → 自动触发 Level 2 回滚
    │               ├─ 成功 → 完成（运行在出厂版本）
    │               └─ 失败 → 手动干预
    │
    └─ 否 → 部署成功
            └─ 发现问题？
                ├─ 是 → 手动回滚
                │       ├─ 回滚到上一版本
                │       ├─ 回滚到出厂版本
                │       └─ 回滚到指定版本
                │
                └─ 否 → 正常运行
```

---

## 紧急回滚快速参考

### 快速回滚到上一版本

```bash
sudo systemctl stop device-api.service web-server.service
cd /opt/tope/versions && sudo ln -sfn $(readlink previous) .tmp && sudo mv -f .tmp current
sudo systemctl start device-api.service web-server.service
```

### 快速回滚到出厂版本

```bash
sudo systemctl stop device-api.service web-server.service
cd /opt/tope/versions && sudo ln -sfn $(readlink factory) .tmp && sudo mv -f .tmp current
sudo systemctl start device-api.service web-server.service
```

---

## 相关文档

- [部署指南](DEPLOYMENT.md) - 初始部署和配置
- [符号链接配置](../deploy/SYMLINK_SETUP.md) - 符号链接详细说明
- [测试报告](../tests/reports/version_snapshot_test_report.md) - 回滚机制测试结果

---

**维护者**: TOP.E 开发团队
**最后更新**: 2026-01-28
**紧急联系**: [待填写]
