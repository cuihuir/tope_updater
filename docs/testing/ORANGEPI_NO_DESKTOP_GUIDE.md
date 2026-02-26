# Orange Pi 3B 无桌面环境 GUI 运行指南

## 概述

在没有 X11/Wayland 桌面环境的情况下，SDL2 可以使用以下后端：
1. **KMS/DRM** - 现代方式，直接访问 GPU（推荐）
2. **Framebuffer** - 传统方式，兼容性好

---

## 🚀 快速开始

### 方法 1: 使用测试脚本（推荐）

```bash
# 在 Orange Pi 上运行
cd ~/tope_updater
sudo bash test_orangepi_no_desktop.sh
```

脚本会自动：
- 检测可用的显示后端
- 选择最佳后端
- 运行测试
- 保存日志

---

### 方法 2: 手动配置

#### 使用 KMS/DRM 后端

```bash
# 1. 检查 DRM 设备
ls -l /dev/dri/

# 2. 设置环境变量
export SDL_VIDEODRIVER=kmsdrm

# 3. 运行测试（需要 root）
sudo -E uv run python test_orangepi_fullscreen.py

# 如果失败，尝试 legacy 模式
export SDL_VIDEODRIVER=kmsdrm_legacy
sudo -E uv run python test_orangepi_fullscreen.py
```

#### 使用 Framebuffer 后端

```bash
# 1. 检查 framebuffer 设备
ls -l /dev/fb0

# 2. 设置环境变量
export SDL_VIDEODRIVER=fbcon
export SDL_FBDEV=/dev/fb0

# 3. 运行测试（需要 root）
sudo -E uv run python test_orangepi_fullscreen.py
```

---

## 🔧 配置 Updater 服务

### 修改 systemd 服务文件

如果您使用 systemd 管理 updater 服务，需要添加环境变量：

```ini
# /etc/systemd/system/tope-updater.service

[Unit]
Description=TOP.E OTA Updater Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/tope/updater
Environment="SDL_VIDEODRIVER=kmsdrm"
ExecStart=/usr/local/bin/uv run python src/updater/main.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

重新加载服务：

```bash
sudo systemctl daemon-reload
sudo systemctl restart tope-updater
```

---

## 🐛 故障排除

### 问题 1: Permission denied

**错误**:
```
Permission denied: /dev/dri/card0
```

**解决**:
```bash
# 方式 1: 使用 root 运行
sudo -E uv run python test_orangepi_fullscreen.py

# 方式 2: 添加用户到 video 组
sudo usermod -a -G video tope
# 重新登录后生效
```

### 问题 2: Could not initialize SDL

**错误**:
```
Could not initialize SDL: No available video device
```

**解决**:
```bash
# 检查可用的后端
export SDL_VIDEODRIVER=kmsdrm
uv run python -c "import sdl2; sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO)"

# 如果失败，尝试其他后端
export SDL_VIDEODRIVER=kmsdrm_legacy
# 或
export SDL_VIDEODRIVER=fbcon
```

### 问题 3: 黑屏或无显示

**可能原因**:
1. TTY 被占用
2. 需要切换到正确的 TTY

**解决**:
```bash
# 切换到 TTY1
sudo chvt 1

# 然后运行测试
sudo -E uv run python test_orangepi_fullscreen.py
```

---

## 📊 性能对比

| 后端 | 性能 | 兼容性 | GPU 加速 |
|------|------|--------|----------|
| KMS/DRM | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ✅ |
| KMS/DRM Legacy | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ |
| Framebuffer | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ❌ |

---

## ✅ 验证清单

### 环境检查
- [ ] `/dev/dri/card0` 存在
- [ ] `/dev/fb0` 存在
- [ ] 用户在 `video` 组中
- [ ] 有 root 权限

### 功能测试
- [ ] GUI 窗口显示
- [ ] Logo 显示清晰
- [ ] 中文文字正常
- [ ] 进度条更新
- [ ] 全屏覆盖

---

## 🎯 生产环境配置

### 1. 创建专用用户

```bash
sudo useradd -r -s /bin/false tope-updater
sudo usermod -a -G video tope-updater
```

### 2. 配置服务

```bash
sudo cp deploy/tope-updater.service /etc/systemd/system/
sudo systemctl enable tope-updater
sudo systemctl start tope-updater
```

### 3. 测试 GUI 自动启动

```bash
# 触发更新
curl -X POST http://localhost:12315/api/v1.0/update \
  -H "Content-Type: application/json" \
  -d '{"version": "1.0.0"}'

# GUI 应该自动显示在屏幕上
```

---

## 📝 注意事项

1. **Root 权限**: KMS/DRM 通常需要 root 权限
2. **TTY 切换**: 确保在正确的 TTY 上运行
3. **GPU 驱动**: 确保 Mali GPU 驱动已安装
4. **性能**: KMS/DRM 性能最好，优先使用

---

**文档版本**: 1.0  
**最后更新**: 2026-01-29  
**适用设备**: Orange Pi 3B (RK3566)
