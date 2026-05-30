"""Unit tests for OTA version formatting helpers."""

import pytest

from updater.utils.version import format_report_version, normalize_version


@pytest.mark.unit
class TestVersionUtils:
    """Version strings have one external form and one internal form."""

    def test_normalize_version_strips_v_prefix(self):
        assert normalize_version("v0.1.1") == "0.1.1"

    def test_normalize_version_preserves_plain_semver(self):
        assert normalize_version("0.1.1") == "0.1.1"

    def test_normalize_version_rejects_invalid_value(self):
        with pytest.raises(ValueError, match="Invalid OTA version"):
            normalize_version("version-0.1.1")

    def test_format_report_version_adds_v_prefix(self):
        assert format_report_version("0.1.1") == "v0.1.1"

    def test_format_report_version_does_not_double_prefix(self):
        assert format_report_version("v0.1.1") == "v0.1.1"
