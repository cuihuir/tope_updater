# 192.168.5.44 OTA 手工测试指南

本文档以测试设备 `192.168.5.44` 为例，记录从本机打包、上传、启动 HTTP 文件服务器，到手工调用 `/download` 和 `/update` 的完整流程。

## 约定

- 本机 updater 项目路径：`/home/tope/project/tope_updater`
- 本机 printer GUI 源码路径：`/home/tope/project/printer-gui-polist`
- 测试设备：`192.168.5.44`
- 测试设备用户：`tope`
- 测试设备 OTA 包目录：`/tmp/tope_ota_test`
- 测试设备本地 HTTP 文件服务端口：`18888`
- updater API 地址：`http://127.0.0.1:12315`
- printer GUI 实际启动目录：`/home/tope/printer-gui-qml`

> 注意：当前 `printer-gui-eglfs.service` 实际从 `/home/tope/printer-gui-qml/main.py` 启动。完整升级 printer GUI 时，打包命令里的 `--dst-root` 必须使用 `/home/tope/printer-gui-qml`，否则包可能只进入版本快照但实际 GUI 不会变化。

## 1. 在本机制作 OTA 包

进入 updater 项目：

```bash
cd /home/tope/project/tope_updater
```

设置本次测试版本号：

```bash
VERSION=0.1.7
PACKAGE_NAME="printer-gui-${VERSION}-polist-20260529.zip"
```

执行打包：

```bash
./scripts/build_ota_package.py \
  --source-dir /home/tope/project/printer-gui-polist \
  --version "${VERSION}" \
  --component printer-gui \
  --dst-root /home/tope/printer-gui-qml \
  --service printer-gui-eglfs.service \
  --restart-order 10 \
  --output-dir /tmp/tope_ota \
  --package-name "${PACKAGE_NAME}" \
  --package-url "http://127.0.0.1:18888/${PACKAGE_NAME}"
```

脚本会输出类似内容：

```text
package=/tmp/tope_ota/printer-gui-0.1.7-polist-20260529.zip
size=30666491
md5=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
download_payload=
{
  "version": "0.1.7",
  "package_url": "http://127.0.0.1:18888/printer-gui-0.1.7-polist-20260529.zip",
  "package_name": "printer-gui-0.1.7-polist-20260529.zip",
  "package_size": 30666491,
  "package_md5": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

记录 `size` 和 `md5`，后面调用 `/download` 要用。

## 2. 上传 OTA 包到 192.168.5.44

```bash
SSHPASS='Gnsz12#$' sshpass -e ssh -o StrictHostKeyChecking=no tope@192.168.5.44 \
  'mkdir -p /tmp/tope_ota_test'
```

```bash
SSHPASS='Gnsz12#$' sshpass -e scp -o StrictHostKeyChecking=no \
  "/tmp/tope_ota/${PACKAGE_NAME}" \
  "tope@192.168.5.44:/tmp/tope_ota_test/${PACKAGE_NAME}"
```

在设备上确认文件：

```bash
SSHPASS='Gnsz12#$' sshpass -e ssh -o StrictHostKeyChecking=no tope@192.168.5.44 \
  "ls -lh /tmp/tope_ota_test/${PACKAGE_NAME} && md5sum /tmp/tope_ota_test/${PACKAGE_NAME}"
```

## 3. 在 192.168.5.44 上启动本地 HTTP 文件服务器

updater 在设备上下载包时使用 `http://127.0.0.1:18888/...`。所以 HTTP 文件服务器要运行在设备本机。

```bash
SSHPASS='Gnsz12#$' sshpass -e ssh -o StrictHostKeyChecking=no tope@192.168.5.44 '
set -e
cd /tmp/tope_ota_test
if [ -f http.pid ] && kill -0 "$(cat http.pid)" 2>/dev/null; then
  echo "http server already running pid $(cat http.pid)"
else
  nohup python3 -m http.server 18888 --bind 127.0.0.1 > http.log 2>&1 &
  echo $! > http.pid
  sleep 1
  echo "http server started pid $(cat http.pid)"
fi
'
```

检查 HTTP 是否可访问：

```bash
SSHPASS='Gnsz12#$' sshpass -e ssh -o StrictHostKeyChecking=no tope@192.168.5.44 \
  "curl -sI http://127.0.0.1:18888/${PACKAGE_NAME} | sed -n '1,8p'"
```

预期能看到：

```text
HTTP/1.0 200 OK
Content-Length: ...
```

## 4. 查询 updater 当前状态

```bash
SSHPASS='Gnsz12#$' sshpass -e ssh -o StrictHostKeyChecking=no tope@192.168.5.44 \
  'curl -s http://127.0.0.1:12315/api/v1.0/progress; echo'
```

如果空闲，预期包含：

```json
"stage":"idle"
```

## 5. 手工调用 download

把下面命令里的 `PACKAGE_SIZE` 和 `PACKAGE_MD5` 替换成第 1 步脚本输出的值。

```bash
VERSION=0.1.7
PACKAGE_NAME="printer-gui-${VERSION}-polist-20260529.zip"
PACKAGE_SIZE=30666491
PACKAGE_MD5=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

触发下载：

```bash
SSHPASS='Gnsz12#$' sshpass -e ssh -o StrictHostKeyChecking=no tope@192.168.5.44 "
curl -s -X POST http://127.0.0.1:12315/api/v1.0/download \
  -H 'Content-Type: application/json' \
  -d '{
    \"version\":\"${VERSION}\",
    \"package_url\":\"http://127.0.0.1:18888/${PACKAGE_NAME}\",
    \"package_name\":\"${PACKAGE_NAME}\",
    \"package_size\":${PACKAGE_SIZE},
    \"package_md5\":\"${PACKAGE_MD5}\"
  }'
echo
"
```

轮询下载进度，直到 `stage=toInstall`：

```bash
SSHPASS='Gnsz12#$' sshpass -e ssh -o StrictHostKeyChecking=no tope@192.168.5.44 '
for i in $(seq 1 120); do
  body=$(curl -s http://127.0.0.1:12315/api/v1.0/progress)
  echo "$i $body"
  echo "$body" | grep -q "\"stage\":\"toInstall\"" && exit 0
  echo "$body" | grep -q "\"stage\":\"failed\"" && exit 2
  sleep 1
done
exit 3
'
```

## 6. 手工调用 update/install

触发安装：

```bash
SSHPASS='Gnsz12#$' sshpass -e ssh -o StrictHostKeyChecking=no tope@192.168.5.44 "
curl -s -X POST http://127.0.0.1:12315/api/v1.0/update \
  -H 'Content-Type: application/json' \
  -d '{\"version\":\"${VERSION}\"}'
echo
"
```

观察安装进度和 GUI 服务切换：

```bash
SSHPASS='Gnsz12#$' sshpass -e ssh -o StrictHostKeyChecking=no tope@192.168.5.44 '
for i in $(seq 1 240); do
  body=$(curl -s http://127.0.0.1:12315/api/v1.0/progress || true)
  printer=$(systemctl is-active printer-gui-eglfs.service || true)
  updater_gui=$(systemctl is-active tope-updater-gui.service || true)
  echo "$i printer=$printer updater_gui=$updater_gui progress=$body"
  echo "$body" | grep -q "\"stage\":\"success\"" && exit 0
  echo "$body" | grep -q "\"stage\":\"failed\"" && exit 2
  sleep 1
done
exit 3
'
```

预期过程：

- 安装开始后 `printer-gui-eglfs.service` 停止。
- `tope-updater-gui.service` 变为 `active`，屏幕显示 OTA 进度。
- 安装末尾 `printer-gui-eglfs.service` 恢复 `active`。
- `tope-updater-gui.service` 可能因 systemd `Conflicts` 显示 `failed` 或 `inactive`，这是当前切换方式下的预期现象。
- `/progress` 最终进入 `success`，约 65 秒后 reset 到 `idle`。

## 7. 安装后确认

等待 updater 自动 reset：

```bash
sleep 70
```

确认服务状态和版本链接：

```bash
SSHPASS='Gnsz12#$' sshpass -e ssh -o StrictHostKeyChecking=no tope@192.168.5.44 '
printf "progress="
curl -s http://127.0.0.1:12315/api/v1.0/progress
echo
printf "printer=%s\n" "$(systemctl is-active printer-gui-eglfs.service || true)"
printf "updater_gui=%s\n" "$(systemctl is-active tope-updater-gui.service || true)"
printf "updater=%s\n" "$(systemctl is-active tope-updater.service || true)"
printf "current="
readlink -f /opt/tope/versions/current || true
printf "previous="
readlink -f /opt/tope/versions/previous || true
'
```

确认实际运行目录已更新：

```bash
SSHPASS='Gnsz12#$' sshpass -e ssh -o StrictHostKeyChecking=no tope@192.168.5.44 '
md5sum \
  /home/tope/printer-gui-qml/main.py \
  /home/tope/printer-gui-qml/main.qml \
  2>/dev/null || true
ps -eo pid,args | grep -E "printer-gui|main.py" | grep -v grep || true
'
```

如果要和本机源码比对：

```bash
md5sum \
  /home/tope/project/printer-gui-polist/main.py \
  /home/tope/project/printer-gui-polist/main.qml
```

两边 MD5 一致，说明实际启动目录已经更新。

## 8. 常用排查命令

查看 updater 日志：

```bash
SSHPASS='Gnsz12#$' sshpass -e ssh -o StrictHostKeyChecking=no tope@192.168.5.44 \
  'journalctl -u tope-updater.service -n 160 --no-pager'
```

查看 updater GUI 日志：

```bash
SSHPASS='Gnsz12#$' sshpass -e ssh -o StrictHostKeyChecking=no tope@192.168.5.44 \
  'journalctl -u tope-updater-gui.service -n 120 --no-pager'
```

查看 printer GUI 日志：

```bash
SSHPASS='Gnsz12#$' sshpass -e ssh -o StrictHostKeyChecking=no tope@192.168.5.44 \
  'journalctl -u printer-gui-eglfs.service -n 120 --no-pager'
```

手动切换到 updater GUI：

```bash
SSHPASS='Gnsz12#$' sshpass -e ssh -o StrictHostKeyChecking=no tope@192.168.5.44 \
  'printf "%s\n" "Gnsz12#$" | sudo -S /usr/local/bin/tope-display-switcher show updater'
```

手动切回 printer GUI：

```bash
SSHPASS='Gnsz12#$' sshpass -e ssh -o StrictHostKeyChecking=no tope@192.168.5.44 \
  'printf "%s\n" "Gnsz12#$" | sudo -S /usr/local/bin/tope-display-switcher show printer'
```

停止测试 HTTP 文件服务器：

```bash
SSHPASS='Gnsz12#$' sshpass -e ssh -o StrictHostKeyChecking=no tope@192.168.5.44 '
if [ -f /tmp/tope_ota_test/http.pid ]; then
  kill "$(cat /tmp/tope_ota_test/http.pid)" 2>/dev/null || true
  rm -f /tmp/tope_ota_test/http.pid
fi
'
```

## 9. 常见问题

### 升级成功但 GUI 没变化

先确认 `printer-gui-eglfs.service` 实际启动路径：

```bash
SSHPASS='Gnsz12#$' sshpass -e ssh -o StrictHostKeyChecking=no tope@192.168.5.44 \
  'systemctl cat printer-gui-eglfs.service | sed -n "1,120p"; ps -eo pid,args | grep -E "printer-gui|main.py" | grep -v grep || true'
```

如果进程仍从 `/home/tope/printer-gui-qml/main.py` 启动，则打包时必须使用：

```bash
--dst-root /home/tope/printer-gui-qml
```

不要用 `/opt/tope/services/printer-gui-qml` 作为完整 GUI 更新的目标路径，除非 systemd service 已经改成从该路径启动。

### download 返回 404

通常是 package URL 不可访问。进入设备检查：

```bash
SSHPASS='Gnsz12#$' sshpass -e ssh -o StrictHostKeyChecking=no tope@192.168.5.44 \
  "curl -sI http://127.0.0.1:18888/${PACKAGE_NAME}"
```

### update 返回 Package not found

通常是还没有完成 `/download`，或 `/update` 的 `version` 与下载包版本不一致。先查询：

```bash
SSHPASS='Gnsz12#$' sshpass -e ssh -o StrictHostKeyChecking=no tope@192.168.5.44 \
  'curl -s http://127.0.0.1:12315/api/v1.0/progress; echo'
```
