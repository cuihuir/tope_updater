"""Tests for the generic OTA package builder script."""

import json
import stat
import zipfile
from pathlib import Path

from scripts.build_ota_package import BuildOptions, build_package


def test_build_package_creates_manifest_and_download_payload(tmp_path):
    source_dir = tmp_path / "printer-gui"
    source_dir.mkdir()
    (source_dir / "main.py").write_text("print('new gui')\n", encoding="utf-8")
    (source_dir / "pages").mkdir()
    (source_dir / "pages" / "MainPage.qml").write_text("Item {}\n", encoding="utf-8")

    result = build_package(
        BuildOptions(
            source_dir=source_dir,
            version="1.2.3",
            component="printer-gui",
            dst_root=Path("/home/tope/printer-gui-qml"),
            service="printer-gui-eglfs.service",
            restart_order=10,
            output_dir=tmp_path / "out",
        )
    )

    assert result.package_path.exists()
    assert result.package_size == result.package_path.stat().st_size
    assert len(result.package_md5) == 32
    assert result.download_payload == {
        "version": "1.2.3",
        "package_url": "",
        "package_name": result.package_path.name,
        "package_size": result.package_size,
        "package_md5": result.package_md5,
    }

    with zipfile.ZipFile(result.package_path) as zf:
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert manifest == {
            "version": "1.2.3",
            "modules": [
                {
                    "name": "printer-gui-0001",
                    "src": "modules/printer-gui/main.py",
                    "dst": "/home/tope/printer-gui-qml/main.py",
                    "process_name": "printer-gui-eglfs.service",
                    "restart_order": 10,
                },
                {
                    "name": "printer-gui-0002",
                    "src": "modules/printer-gui/pages/MainPage.qml",
                    "dst": "/home/tope/printer-gui-qml/pages/MainPage.qml",
                    "process_name": "printer-gui-eglfs.service",
                    "restart_order": 10,
                },
            ],
        }
        assert zf.read("modules/printer-gui/main.py") == b"print('new gui')\n"


def test_build_package_excludes_runtime_files(tmp_path):
    source_dir = tmp_path / "app"
    source_dir.mkdir()
    (source_dir / "keep.txt").write_text("keep\n", encoding="utf-8")
    (source_dir / ".git").mkdir()
    (source_dir / ".git" / "config").write_text("ignore\n", encoding="utf-8")
    (source_dir / "tmp").mkdir()
    (source_dir / "tmp" / "cache.txt").write_text("ignore\n", encoding="utf-8")
    (source_dir / "custom.skip").write_text("ignore\n", encoding="utf-8")

    result = build_package(
        BuildOptions(
            source_dir=source_dir,
            version="1.0.0",
            component="device-api",
            dst_root=Path("/opt/tope/services/device-api"),
            output_dir=tmp_path,
            excludes=("custom.skip",),
        )
    )

    with zipfile.ZipFile(result.package_path) as zf:
        names = set(zf.namelist())
        assert "modules/device-api/keep.txt" in names
        assert "modules/device-api/.git/config" not in names
        assert "modules/device-api/tmp/cache.txt" not in names
        assert "modules/device-api/custom.skip" not in names


def test_build_package_preserves_executable_mode(tmp_path):
    source_dir = tmp_path / "app"
    source_dir.mkdir()
    executable = source_dir / "bin.sh"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)

    result = build_package(
        BuildOptions(
            source_dir=source_dir,
            version="1.0.0",
            component="udev-deploy",
            dst_root=Path("/opt/tope/services/udev-deploy"),
            output_dir=tmp_path,
        )
    )

    with zipfile.ZipFile(result.package_path) as zf:
        mode = (zf.getinfo("modules/udev-deploy/bin.sh").external_attr >> 16) & 0o777
        assert stat.S_IMODE(mode) == 0o755
