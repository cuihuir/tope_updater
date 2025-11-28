"""MD5 verification utilities for package integrity checking."""

import hashlib
from pathlib import Path
from typing import Optional
import logging


def compute_md5(file_path: Path, chunk_size: int = 8192) -> str:
    """Compute MD5 hash of a file.

    Args:
        file_path: Path to file to hash
        chunk_size: Read buffer size (default 8KB for memory efficiency)

    Returns:
        32-character hex MD5 hash string

    Raises:
        FileNotFoundError: If file doesn't exist
        IOError: If file read fails
    """
    logger = logging.getLogger("updater.verification")
    md5_hash = hashlib.md5()

    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                md5_hash.update(chunk)

        result = md5_hash.hexdigest()
        logger.debug(f"Computed MD5 for {file_path.name}: {result}")
        return result

    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        raise
    except IOError as e:
        logger.error(f"Failed to read file {file_path}: {e}")
        raise


def verify_md5(file_path: Path, expected_md5: str) -> bool:
    """Verify file MD5 hash matches expected value.

    Args:
        file_path: Path to file to verify
        expected_md5: Expected MD5 hash (32-char hex string)

    Returns:
        True if MD5 matches, False otherwise

    Raises:
        FileNotFoundError: If file doesn't exist
        IOError: If file read fails
        ValueError: If expected_md5 format is invalid
    """
    logger = logging.getLogger("updater.verification")

    # Validate expected_md5 format
    if not isinstance(expected_md5, str) or len(expected_md5) != 32:
        raise ValueError(f"Invalid MD5 format: {expected_md5} (must be 32-char hex)")

    expected_md5 = expected_md5.lower()

    # Compute actual MD5
    actual_md5 = compute_md5(file_path)

    # Compare
    match = actual_md5 == expected_md5
    if match:
        logger.info(f"MD5 verification passed for {file_path.name}")
    else:
        logger.error(
            f"MD5 mismatch for {file_path.name}: "
            f"expected {expected_md5}, got {actual_md5}"
        )

    return match


def verify_md5_or_raise(file_path: Path, expected_md5: str) -> None:
    """Verify file MD5 hash, raise exception if mismatch.

    Args:
        file_path: Path to file to verify
        expected_md5: Expected MD5 hash (32-char hex string)

    Raises:
        ValueError: If MD5 verification fails or format invalid
        FileNotFoundError: If file doesn't exist
        IOError: If file read fails
    """
    if not verify_md5(file_path, expected_md5):
        actual_md5 = compute_md5(file_path)
        raise ValueError(
            f"MD5_MISMATCH: expected {expected_md5}, got {actual_md5}"
        )
