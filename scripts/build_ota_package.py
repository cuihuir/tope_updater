#!/usr/bin/env python3
"""Build a TOPE OTA ZIP package from a source directory."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_EXCLUDES = (
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "tmp",
    "logs",
)
DEFAULT_EXCLUDE_SUFFIXES = (".pyc", ".pyo")


@dataclass(frozen=True)
class BuildOptions:
    """Options for building one OTA package."""

    source_dir: Path
    version: str
    component: str
    dst_root: Path
    output_dir: Path
    service: str | None = None
    restart_order: int | None = None
    excludes: tuple[str, ...] = ()
    package_name: str | None = None
    package_url: str = ""


@dataclass(frozen=True)
class BuildResult:
    """Result metadata for a built OTA package."""

    package_path: Path
    package_size: int
    package_md5: str
    download_payload: dict[str, str | int]


def _is_excluded(path: Path, excludes: Iterable[str]) -> bool:
    rel = path.as_posix()
    parts = path.parts
    for pattern in excludes:
        if pattern in parts:
            return True
        if fnmatch.fnmatch(rel, pattern):
            return True
    return path.suffix in DEFAULT_EXCLUDE_SUFFIXES


def _iter_source_files(source_dir: Path, excludes: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    all_excludes = (*DEFAULT_EXCLUDES, *tuple(excludes))

    for path in source_dir.rglob("*"):
        rel = path.relative_to(source_dir)
        if _is_excluded(rel, all_excludes):
            continue
        if path.is_file():
            files.append(rel)

    return sorted(files, key=lambda item: item.as_posix())


def _file_md5(path: Path) -> str:
    md5_hash = hashlib.md5()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


def _module_entry(options: BuildOptions, rel_path: Path, index: int) -> dict[str, str | int]:
    rel_posix = rel_path.as_posix()
    entry: dict[str, str | int] = {
        "name": f"{options.component}-{index:04d}",
        "src": f"modules/{options.component}/{rel_posix}",
        "dst": (options.dst_root / rel_path).as_posix(),
    }
    if options.service:
        entry["process_name"] = options.service
    if options.restart_order is not None:
        entry["restart_order"] = options.restart_order
    return entry


def build_package(options: BuildOptions) -> BuildResult:
    """Build an OTA ZIP package and return its metadata."""

    source_dir = options.source_dir.resolve()
    if not source_dir.is_dir():
        raise ValueError(f"source directory does not exist: {source_dir}")

    files = _iter_source_files(source_dir, options.excludes)
    if not files:
        raise ValueError(f"source directory has no packageable files: {source_dir}")

    options.output_dir.mkdir(parents=True, exist_ok=True)
    package_name = (
        options.package_name
        if options.package_name
        else f"{options.component}-{options.version}.zip"
    )
    package_path = options.output_dir / package_name

    manifest = {
        "version": options.version,
        "modules": [
            _module_entry(options, rel_path, index)
            for index, rel_path in enumerate(files, start=1)
        ],
    }

    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        for rel_path in files:
            source_path = source_dir / rel_path
            archive_name = f"modules/{options.component}/{rel_path.as_posix()}"
            zip_info = zipfile.ZipInfo.from_file(source_path, arcname=archive_name)
            zip_info.compress_type = zipfile.ZIP_DEFLATED
            with source_path.open("rb") as source_file:
                zf.writestr(zip_info, source_file.read())

    package_md5 = _file_md5(package_path)
    package_size = package_path.stat().st_size
    download_payload: dict[str, str | int] = {
        "version": options.version,
        "package_url": options.package_url,
        "package_name": package_path.name,
        "package_size": package_size,
        "package_md5": package_md5,
    }
    return BuildResult(
        package_path=package_path,
        package_size=package_size,
        package_md5=package_md5,
        download_payload=download_payload,
    )


def _parse_args(argv: list[str]) -> BuildOptions:
    parser = argparse.ArgumentParser(
        description="Build a TOPE OTA package from a source directory."
    )
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--component", required=True)
    parser.add_argument("--dst-root", required=True, type=Path)
    parser.add_argument("--output-dir", default=Path("."), type=Path)
    parser.add_argument("--service")
    parser.add_argument("--restart-order", type=int)
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--package-name")
    parser.add_argument("--package-url", default="")
    args = parser.parse_args(argv)

    return BuildOptions(
        source_dir=args.source_dir,
        version=args.version,
        component=args.component,
        dst_root=args.dst_root,
        output_dir=args.output_dir,
        service=args.service,
        restart_order=args.restart_order,
        excludes=tuple(args.exclude),
        package_name=args.package_name,
        package_url=args.package_url,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""

    options = _parse_args(sys.argv[1:] if argv is None else argv)
    result = build_package(options)

    print(f"package={result.package_path}")
    print(f"size={result.package_size}")
    print(f"md5={result.package_md5}")
    print("download_payload=")
    print(json.dumps(result.download_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
