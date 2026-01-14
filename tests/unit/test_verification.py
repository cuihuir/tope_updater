"""Unit tests for verification utilities."""

import hashlib
import pytest
from pathlib import Path
from unittest.mock import mock_open, patch

from updater.utils.verification import (
    compute_md5,
    verify_md5,
    verify_md5_or_raise,
)


@pytest.mark.unit
class TestVerification:
    """Test verification utilities in isolation."""

    def calculate_md5(self, content: bytes) -> str:
        """Helper to calculate MD5 hash."""
        return hashlib.md5(content).hexdigest()

    def test_compute_md5_success(self, tmp_path):
        """Test successful MD5 computation."""
        # Arrange
        test_content = b"test file content for MD5 verification"
        expected_md5 = self.calculate_md5(test_content)
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(test_content)

        # Act
        result = compute_md5(test_file)

        # Assert
        assert result == expected_md5
        assert len(result) == 32  # MD5 is always 32 hex chars
        assert result.islower()  # Should be lowercase hex

    def test_compute_md5_large_file(self, tmp_path):
        """Test MD5 computation with large file using chunked reading."""
        # Arrange
        # Create a file larger than default chunk size (8KB)
        test_content = b"x" * (64 * 1024)  # 64KB
        expected_md5 = self.calculate_md5(test_content)
        test_file = tmp_path / "large.bin"
        test_file.write_bytes(test_content)

        # Act
        result = compute_md5(test_file, chunk_size=8192)

        # Assert
        assert result == expected_md5

    def test_compute_md5_custom_chunk_size(self, tmp_path):
        """Test MD5 computation with custom chunk size."""
        # Arrange
        test_content = b"small file"
        expected_md5 = self.calculate_md5(test_content)
        test_file = tmp_path / "small.bin"
        test_file.write_bytes(test_content)

        # Act - use very small chunk size
        result = compute_md5(test_file, chunk_size=2)

        # Assert - should still get correct MD5 regardless of chunk size
        assert result == expected_md5

    def test_compute_md5_empty_file(self, tmp_path):
        """Test MD5 computation on empty file."""
        # Arrange
        test_file = tmp_path / "empty.bin"
        test_file.write_bytes(b"")
        expected_md5 = self.calculate_md5(b"")  # MD5 of empty content

        # Act
        result = compute_md5(test_file)

        # Assert
        assert result == expected_md5
        assert result == "d41d8cd98f00b204e9800998ecf8427e"  # Known MD5 of empty file

    def test_compute_md5_file_not_found(self):
        """Test compute_md5 raises FileNotFoundError for non-existent file."""
        # Arrange
        non_existent_file = Path("/nonexistent/path/file.bin")

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            compute_md5(non_existent_file)

    def test_compute_md5_io_error(self):
        """Test compute_md5 raises IOError on read failure."""
        # Arrange
        test_file = Path("/some/file.bin")

        # Mock open to raise IOError
        with patch('builtins.open', side_effect=IOError("Disk read error")):
            # Act & Assert
            with pytest.raises(IOError, match="Disk read error"):
                compute_md5(test_file)

    def test_verify_md5_success(self, tmp_path):
        """Test successful MD5 verification."""
        # Arrange
        test_content = b"verified content"
        expected_md5 = self.calculate_md5(test_content)
        test_file = tmp_path / "verified.bin"
        test_file.write_bytes(test_content)

        # Act
        result = verify_md5(test_file, expected_md5)

        # Assert
        assert result is True

    def test_verify_md5_case_insensitive(self, tmp_path):
        """Test MD5 verification is case-insensitive."""
        # Arrange
        test_content = b"case test"
        expected_md5 = self.calculate_md5(test_content)
        test_file = tmp_path / "case.bin"
        test_file.write_bytes(test_content)

        # Act - use uppercase MD5
        result = verify_md5(test_file, expected_md5.upper())

        # Assert
        assert result is True

    def test_verify_md5_mismatch(self, tmp_path):
        """Test MD5 verification returns False on mismatch."""
        # Arrange
        test_content = b"actual content"
        wrong_md5 = "a" * 32  # Wrong MD5
        test_file = tmp_path / "mismatch.bin"
        test_file.write_bytes(test_content)

        # Act
        result = verify_md5(test_file, wrong_md5)

        # Assert
        assert result is False

    def test_verify_md5_invalid_format_short(self):
        """Test verify_md5 raises ValueError for short MD5."""
        # Arrange
        test_file = Path("/some/file.bin")
        invalid_md5 = "abc123"  # Too short

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid MD5 format.*must be 32-char"):
            verify_md5(test_file, invalid_md5)

    def test_verify_md5_invalid_format_long(self):
        """Test verify_md5 raises ValueError for long MD5."""
        # Arrange
        test_file = Path("/some/file.bin")
        invalid_md5 = "a" * 33  # Too long

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid MD5 format.*must be 32-char"):
            verify_md5(test_file, invalid_md5)

    def test_verify_md5_invalid_format_not_string(self):
        """Test verify_md5 raises ValueError for non-string MD5."""
        # Arrange
        test_file = Path("/some/file.bin")
        invalid_md5 = 12345  # Not a string

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid MD5 format"):
            verify_md5(test_file, invalid_md5)

    def test_verify_md5_file_not_found(self):
        """Test verify_md5 raises FileNotFoundError."""
        # Arrange
        non_existent_file = Path("/nonexistent/file.bin")
        valid_md5 = "a" * 32

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            verify_md5(non_existent_file, valid_md5)

    def test_verify_md5_or_raise_success(self, tmp_path):
        """Test verify_md5_or_raise succeeds without exception."""
        # Arrange
        test_content = b"correct content"
        expected_md5 = self.calculate_md5(test_content)
        test_file = tmp_path / "correct.bin"
        test_file.write_bytes(test_content)

        # Act - should not raise
        verify_md5_or_raise(test_file, expected_md5)

        # Assert - if no exception, test passes

    def test_verify_md5_or_raise_mismatch(self, tmp_path):
        """Test verify_md5_or_raise raises ValueError on mismatch."""
        # Arrange
        test_content = b"wrong content"
        actual_md5 = self.calculate_md5(test_content)
        wrong_md5 = "b" * 32
        test_file = tmp_path / "wrong.bin"
        test_file.write_bytes(test_content)

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            verify_md5_or_raise(test_file, wrong_md5)

        # Verify error message contains both expected and actual MD5
        assert "MD5_MISMATCH" in str(exc_info.value)
        assert wrong_md5 in str(exc_info.value)
        assert actual_md5 in str(exc_info.value)

    def test_verify_md5_or_raise_invalid_format(self):
        """Test verify_md5_or_raise raises ValueError for invalid format."""
        # Arrange
        test_file = Path("/some/file.bin")
        invalid_md5 = "invalid"

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid MD5 format"):
            verify_md5_or_raise(test_file, invalid_md5)

    def test_verify_md5_or_raise_file_not_found(self):
        """Test verify_md5_or_raise raises FileNotFoundError."""
        # Arrange
        non_existent_file = Path("/nonexistent/file.bin")
        valid_md5 = "c" * 32

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            verify_md5_or_raise(non_existent_file, valid_md5)

    def test_compute_md5_consistent_results(self, tmp_path):
        """Test compute_md5 returns consistent results for same file."""
        # Arrange
        test_content = b"consistency test"
        test_file = tmp_path / "consistent.bin"
        test_file.write_bytes(test_content)

        # Act - compute MD5 multiple times
        result1 = compute_md5(test_file)
        result2 = compute_md5(test_file)
        result3 = compute_md5(test_file)

        # Assert - all results should be identical
        assert result1 == result2 == result3

    def test_verify_md5_with_known_values(self, tmp_path):
        """Test verify_md5 with well-known MD5 values."""
        # Arrange - use known test vectors
        test_cases = [
            (b"", "d41d8cd98f00b204e9800998ecf8427e"),  # Empty
            (b"a", "0cc175b9c0f1b6a831c399e269772661"),  # Single char
            (b"abc", "900150983cd24fb0d6963f7d28e17f72"),  # "abc"
            (b"The quick brown fox jumps over the lazy dog",
             "9e107d9d372bb6826bd81d3542a419d6"),  # Common test string
        ]

        for content, expected_md5 in test_cases:
            test_file = tmp_path / f"test_{expected_md5[:8]}.bin"
            test_file.write_bytes(content)

            # Act
            result = verify_md5(test_file, expected_md5)

            # Assert
            assert result is True, f"Failed for content: {content}"
