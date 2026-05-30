# OTA Updater GUI 优化 TODO

日期：2026-05-30

## 背景

在 192.168.5.44 上完成了一轮完整 OTA 测试：云端 ota-service 上传版本包到 S3，printer-gui 检查新版本，通过 device-api 触发 download 和 install，tope_updater 完成安装并切回 printer-gui。

本项目只负责本机 updater 服务和独立 updater-gui。device-api 和 printer-gui 的适配项已分别记录到对应项目文档。

## 本项目需要处理

1. updater-gui 安装进度偶尔跳回 0%
   - 现象：安装过程中进度条短暂显示 0%，随后跳回正常百分比。
   - 判断：Qt updater-gui 轮询 `/api/v1.0/progress` 时，如果请求失败、超时或响应解析异常，当前逻辑会归一化为 `waiting + 0%`。
   - 优化：保留上一次有效进度；临时轮询失败时只更新提示，不回退进度。

2. 升级结束终态提示
   - 现象：升级完成后 updater-gui 没有明确的完成页提示。
   - 目标：进入 `success` 或 `failed` 后，updater-gui 停留 60 秒，显示成功或失败结果、倒计时和 OK 按钮。
   - 行为：用户点击 OK 立即退出 updater-gui；否则倒计时结束后自动退出，后端随后切回 printer-gui。

3. 与后端显示切换的配合
   - 当前 `_update_workflow` 成功后等待 65 秒再 reset 并切回 printer-gui。
   - updater-gui 终态倒计时建议保持 60 秒，给 systemd/display-switcher 留出少量余量。

## 非本项目问题

1. 第一次点击 Download 失败、第二次正常：倾向 device-api/printer-gui 状态竞态。
2. OTA check 页面 changelog 不显示：倾向 printer-gui 显示优先级问题。

