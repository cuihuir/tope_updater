"""Tests for the offline updater deb builder."""

from pathlib import Path
import subprocess
import sys

import importlib.util

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build_updater_deb.py"
WORKFLOW = ROOT / ".github" / "workflows" / "build-updater-deb.yml"


def test_deb_builder_script_exists_and_has_expected_contract():
    script = SCRIPT.read_text(encoding="utf-8")

    assert "--source-root" in script
    assert "--version" in script
    assert "--output-dir" in script
    assert "tope-updater" in script
    assert "DEBIAN/control" in script
    assert "DEBIAN/postinst" in script
    assert "DEBIAN/prerm" in script
    assert "tope-console-hotkey.service" in script
    assert "tope-console-quiet.service" in script
    assert "tope-updater.service" in script
    assert "getty@tty9.service" in script
    assert "SUDO_USER" in script
    assert "getent passwd" in script
    assert "10-device-home.conf" in script
    assert "ReadWritePaths=-${DEVICE_HOME}" in script
    assert "__pycache__" in script
    assert "backups" in script
    assert "dpkg-deb" in script


def test_deb_builder_help_runs():
    result = subprocess.run(
        [str(SCRIPT), "--help"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Build offline fat deb" in result.stdout


def test_github_action_builds_arm64_deb_for_tags():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "tags:" in workflow
    assert "v*" in workflow
    assert "docker/setup-qemu-action" in workflow
    assert "arm64v8/python:3.11-bookworm" in workflow
    assert "scripts/build_updater_deb.py" in workflow
    assert "--arch arm64" in workflow
    assert "softprops/action-gh-release" in workflow
    assert "dist/*.deb" in workflow


def test_deb_builder_stages_package_tree(tmp_path):
    spec = importlib.util.spec_from_file_location("build_updater_deb", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    source = tmp_path / "source"
    deploy = source / "deploy"
    (source / ".venv" / "bin").mkdir(parents=True)
    (source / ".venv" / "bin" / "python").write_text("#!/bin/sh\n")
    (source / "src" / "updater").mkdir(parents=True)
    (source / "src" / "updater" / "__init__.py").write_text("")
    (source / "tmp").mkdir()
    (source / "tmp" / "runtime.zip").write_text("skip")
    deploy.mkdir()
    for name in (
        "tope-display-switcher",
        "tope-console-hotkey",
        "tope-updater.service",
        "tope-updater-gui.service",
        "tope-console-quiet.service",
        "tope-console-hotkey.service",
        "99-tope-console-quiet.conf",
        "99-tope-rescue-tty.conf",
    ):
        (deploy / name).write_text(name)
    (source / "requirements.txt").write_text("fastapi\n")
    (source / "pyproject.toml").write_text("[project]\n")

    package_root = tmp_path / "package"
    package_root.mkdir()
    options = module.BuildOptions(
        source_root=source,
        version="1.2.3",
        output_dir=tmp_path,
        arch="arm64",
        package_revision="1",
    )

    module.stage_package(options, package_root)

    assert (package_root / "DEBIAN" / "control").exists()
    assert (package_root / "DEBIAN" / "postinst").exists()
    assert (package_root / "DEBIAN" / "prerm").exists()
    assert (package_root / "opt/tope/updater/.venv/bin/python").exists()
    assert (package_root / "usr/local/bin/tope-display-switcher").exists()
    assert not (package_root / "opt/tope/updater/tmp/runtime.zip").exists()
