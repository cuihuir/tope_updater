"""Manifest data models for OTA package."""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class ManifestModule(BaseModel):
    """Module entry in manifest.json.

    Represents a single software component to be updated.
    """

    name: str = Field(..., description="Module identifier (e.g., 'device-api')")
    src: str = Field(
        ...,
        pattern=r"^[^/].*$",
        description="Relative path within ZIP (no leading /)",
    )
    dst: str = Field(
        ..., pattern=r"^/.*$", description="Absolute target path on device"
    )
    process_name: Optional[str] = Field(
        None, description="Process name to terminate before deployment"
    )
    restart_order: Optional[int] = Field(
        None, description="Service restart sequence (lower = earlier)"
    )
    post_cmds: Optional[list[str]] = Field(
        None,
        description=(
            "Shell commands to run after file deployment, in order. "
            "Examples: 'systemctl daemon-reload', 'sysctl -p /etc/sysctl.d/myapp.conf', "
            "'ufw reload'. Each command must exit 0 or deployment fails."
        ),
    )

    @field_validator("src")
    @classmethod
    def no_directory_traversal_src(cls, v: str) -> str:
        """Prevent directory traversal attacks in source path."""
        if ".." in v:
            raise ValueError("Source path must not contain '..'")
        return v

    @field_validator("dst")
    @classmethod
    def no_directory_traversal_dst(cls, v: str) -> str:
        """Prevent directory traversal attacks in destination path."""
        if ".." in v:
            raise ValueError("Destination path must not contain '..'")
        return v


class Manifest(BaseModel):
    """Root manifest.json schema.

    Embedded in package root, defines version and modules to deploy.
    """

    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$", description="Semantic version")
    modules: list[ManifestModule] = Field(
        ..., min_length=1, description="Modules to deploy"
    )

    @field_validator("modules")
    @classmethod
    def unique_module_names(cls, v: list[ManifestModule]) -> list[ManifestModule]:
        """Ensure module names are unique."""
        names = [m.name for m in v]
        if len(names) != len(set(names)):
            raise ValueError("Module names must be unique")
        return v
