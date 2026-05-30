"""Helpers for OTA version string boundaries."""

import re
from typing import Optional

VERSION_RE = re.compile(r"^v?(\d+\.\d+\.\d+)$")


def normalize_version(version: str) -> str:
    """Return internal OTA version without a leading v prefix."""
    value = version.strip()
    match = VERSION_RE.fullmatch(value)
    if not match:
        raise ValueError(f"Invalid OTA version: {version}")
    return match.group(1)


def format_report_version(version: Optional[str]) -> Optional[str]:
    """Return external report version with a leading v prefix."""
    if version is None:
        return None
    value = version.strip()
    if not value:
        return None
    return f"v{normalize_version(value)}"
