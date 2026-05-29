# OTA Package Builder

Use `scripts/build_ota_package.py` to create OTA ZIP packages that match the
current updater `manifest.json` schema.

## Printer GUI Full Update

The current shipped device starts printer GUI from `/home/tope/printer-gui-qml`.
For a full GUI update that takes effect immediately, set `--dst-root` to that
real startup directory:

```bash
./scripts/build_ota_package.py \
  --source-dir /home/tope/project/printer-gui-polist \
  --version 0.1.6 \
  --component printer-gui \
  --dst-root /home/tope/printer-gui-qml \
  --service printer-gui-eglfs.service \
  --restart-order 10 \
  --output-dir /tmp/tope_ota \
  --package-name printer-gui-0.1.6.zip
```

The script prints the package path, size, MD5, and a `/download` payload.

## Generic Component Update

```bash
./scripts/build_ota_package.py \
  --source-dir ./dist/device-api \
  --version 1.2.3 \
  --component device-api \
  --dst-root /opt/tope/services/device-api \
  --service device-api.service \
  --restart-order 20 \
  --output-dir /tmp/tope_ota
```

## Config-Only Update

Omit `--service` if no service should be restarted:

```bash
./scripts/build_ota_package.py \
  --source-dir ./ota-config/printer \
  --version 1.2.4 \
  --component printer-config \
  --dst-root /home/tope/printer_data/config \
  --output-dir /tmp/tope_ota
```

## Defaults

The builder excludes these runtime/local directories by default:

- `.git`
- `.venv`
- `__pycache__`
- `.pytest_cache`
- `tmp`
- `logs`

Add more exclusions with repeated `--exclude` arguments.
