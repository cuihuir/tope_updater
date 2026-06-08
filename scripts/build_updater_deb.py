#!/usr/bin/env python3
"""Build offline fat deb for TOPE updater."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


PACKAGE_NAME = "tope-updater"
INSTALL_ROOT = Path("/opt/tope/updater")
LOCAL_BIN = Path("/usr/local/bin")
SYSTEMD_DIR = Path("/etc/systemd/system")
SYSCTL_DIR = Path("/etc/sysctl.d")
LOGIND_DIR = Path("/etc/systemd/logind.conf.d")
EXCLUDE_DIRS = {"tmp", "logs", "backups", "__pycache__", ".pytest_cache"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}
DEBIAN_CONTROL = "DEBIAN/control"
DEBIAN_POSTINST = "DEBIAN/postinst"
DEBIAN_PRERM = "DEBIAN/prerm"


@dataclass(frozen=True)
class BuildOptions:
    source_root: Path
    version: str
    output_dir: Path
    arch: str
    package_revision: str


def copy_tree_filtered(src: Path, dst: Path) -> None:
    def ignore(_dir: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        for name in names:
            path = Path(name)
            if name in EXCLUDE_DIRS or path.suffix in EXCLUDE_SUFFIXES:
                ignored.add(name)
        return ignored

    shutil.copytree(src, dst, symlinks=True, ignore=ignore)


def copy_required_path(source_root: Path, rel_path: str, package_root: Path) -> None:
    src = source_root / rel_path
    if not src.exists():
        raise FileNotFoundError(f"required path missing: {src}")

    dst = package_root / INSTALL_ROOT.relative_to("/") / rel_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        copy_tree_filtered(src, dst)
    else:
        shutil.copy2(src, dst)


def normalize_venv_python_links(package_root: Path) -> None:
    venv_bin = package_root / INSTALL_ROOT.relative_to("/") / ".venv" / "bin"
    if not venv_bin.exists():
        raise FileNotFoundError(f"required venv bin missing: {venv_bin}")

    links = {
        "python": Path("python3"),
        "python3": Path("/usr/bin/python3"),
        "python3.11": Path("python3"),
    }
    for name, target in links.items():
        path = venv_bin / name
        if path.exists() or path.is_symlink():
            path.unlink()
        path.symlink_to(target)


def install_deploy_file(
    package_root: Path,
    source_root: Path,
    rel_path: str,
    dst_path: Path,
    mode: int,
) -> None:
    src = source_root / "deploy" / rel_path
    if not src.exists():
        raise FileNotFoundError(f"required deploy file missing: {src}")
    dst = package_root / dst_path.relative_to("/")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    dst.chmod(mode)


def write_control(package_root: Path, options: BuildOptions) -> None:
    debian = package_root / "DEBIAN"
    debian.mkdir(parents=True, exist_ok=True)
    version = f"{options.version}-{options.package_revision}"
    installed_size_kb = max(1, directory_size(package_root) // 1024)
    control = f"""Package: {PACKAGE_NAME}
Version: {version}
Section: admin
Priority: optional
Architecture: {options.arch}
Maintainer: TOP.E <support@tope.local>
Installed-Size: {installed_size_kb}
Depends: python3 (>= 3.11), systemd
Description: TOPE device OTA updater
 Offline fat package for the TOPE OTA updater, including its Python venv,
 systemd units, display switcher, and physical console hotkey service.
"""
    (debian / "control").write_text(control, encoding="utf-8")


def write_maintainer_scripts(package_root: Path) -> None:
    debian = package_root / "DEBIAN"
    debian.mkdir(parents=True, exist_ok=True)
    postinst = """#!/bin/sh
set -e

DEVICE_USER="${SUDO_USER:-}"
if [ -z "$DEVICE_USER" ] || [ "$DEVICE_USER" = "root" ]; then
  DEVICE_USER="$(getent passwd | awk -F: '$3 >= 1000 && $3 < 60000 {print $1; exit}')"
fi
DEVICE_HOME=""
if [ -n "$DEVICE_USER" ]; then
  DEVICE_HOME="$(getent passwd "$DEVICE_USER" | cut -d: -f6)"
fi
if [ -z "$DEVICE_HOME" ]; then
  DEVICE_HOME="/root"
fi

mkdir -p /opt/tope "$DEVICE_HOME" /etc/systemd/system/tope-updater.service.d
cat >/etc/systemd/system/tope-updater.service.d/10-device-home.conf <<EOF
[Service]
ReadWritePaths=-${DEVICE_HOME}
EOF

systemctl daemon-reload || true
systemctl disable --now \
  getty@tty1.service getty@tty2.service getty@tty3.service \
  getty@tty4.service getty@tty5.service getty@tty6.service >/dev/null 2>&1 || true
systemctl enable --now getty@tty9.service || true
systemctl enable --now tope-console-quiet.service || true
systemctl enable --now tope-console-hotkey.service || true
systemctl enable tope-updater.service || true
systemctl restart tope-updater.service || true
systemctl restart systemd-logind.service || true
sysctl --system >/dev/null 2>&1 || true

exit 0
"""
    prerm = """#!/bin/sh
set -e

if [ "$1" = "remove" ] || [ "$1" = "deconfigure" ]; then
  systemctl disable --now tope-updater.service >/dev/null 2>&1 || true
  systemctl disable --now tope-console-hotkey.service >/dev/null 2>&1 || true
  systemctl disable --now tope-console-quiet.service >/dev/null 2>&1 || true
fi

exit 0
"""
    for name, content in {"postinst": postinst, "prerm": prerm}.items():
        path = debian / name
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)


def directory_size(path: Path) -> int:
    total = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file_name in files:
            file_path = Path(root) / file_name
            if file_path.suffix in EXCLUDE_SUFFIXES:
                continue
            try:
                total += file_path.stat().st_size
            except OSError:
                continue
    return total


def stage_package(options: BuildOptions, package_root: Path) -> None:
    for rel_path in (".venv", "src", "deploy", "requirements.txt", "pyproject.toml"):
        copy_required_path(options.source_root, rel_path, package_root)

    normalize_venv_python_links(package_root)

    install_deploy_file(
        package_root,
        options.source_root,
        "tope-display-switcher",
        LOCAL_BIN / "tope-display-switcher",
        0o755,
    )
    install_deploy_file(
        package_root,
        options.source_root,
        "tope-console-hotkey",
        LOCAL_BIN / "tope-console-hotkey",
        0o755,
    )

    for unit in (
        "tope-updater.service",
        "tope-updater-gui.service",
        "tope-console-quiet.service",
        "tope-console-hotkey.service",
    ):
        install_deploy_file(package_root, options.source_root, unit, SYSTEMD_DIR / unit, 0o644)

    install_deploy_file(
        package_root,
        options.source_root,
        "99-tope-console-quiet.conf",
        SYSCTL_DIR / "99-tope-console-quiet.conf",
        0o644,
    )
    install_deploy_file(
        package_root,
        options.source_root,
        "99-tope-rescue-tty.conf",
        LOGIND_DIR / "99-tope-rescue-tty.conf",
        0o644,
    )

    write_maintainer_scripts(package_root)
    write_control(package_root, options)


def build_deb(options: BuildOptions) -> Path:
    options.output_dir.mkdir(parents=True, exist_ok=True)
    deb_name = f"{PACKAGE_NAME}_{options.version}-{options.package_revision}_{options.arch}.deb"
    deb_path = options.output_dir / deb_name

    with tempfile.TemporaryDirectory(prefix="tope-updater-deb-") as tmp:
        package_root = Path(tmp) / "package"
        package_root.mkdir()
        stage_package(options, package_root)
        subprocess.run(
            [
                "dpkg-deb",
                "--build",
                "--root-owner-group",
                str(package_root),
                str(deb_path),
            ],
            check=True,
        )

    return deb_path


def parse_args(argv: list[str]) -> BuildOptions:
    parser = argparse.ArgumentParser(description="Build offline fat deb for TOPE updater.")
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--arch", default="arm64")
    parser.add_argument("--package-revision", default="1")
    args = parser.parse_args(argv)
    return BuildOptions(
        source_root=args.source_root.resolve(),
        version=args.version,
        output_dir=args.output_dir.resolve(),
        arch=args.arch,
        package_revision=args.package_revision,
    )


def main(argv: list[str] | None = None) -> int:
    options = parse_args(sys.argv[1:] if argv is None else argv)
    deb_path = build_deb(options)
    print(f"deb={deb_path}")
    print(f"size={deb_path.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
