"""Unit tests for DownloadService."""

import hashlib
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch, mock_open, call
import httpx

from updater.services.download import DownloadService
from updater.models.status import StageEnum
from updater.models.state import StateFile


# Helper to create async iterator
async def async_iterator(items):
    """Create an async iterator from a list of items."""
    for item in items:
        yield item


@pytest.mark.unit
class TestDownloadService:
    """Test DownloadService in isolation."""

    @pytest.fixture
    def mock_state_manager(self):
        """Mock StateManager for tests."""
        manager = MagicMock()
        manager.update_status = MagicMock()
        manager.get_status = MagicMock(return_value=MagicMock(
            stage=StageEnum.IDLE,
            progress=0,
            message="Test",
            error=None
        ))
        manager.get_persistent_state = MagicMock(return_value=None)
        manager.save_state = MagicMock()
        manager.delete_state = MagicMock()
        return manager

    @pytest.fixture
    def download_service(self, mock_state_manager):
        """Create DownloadService instance with mocked state manager."""
        return DownloadService(state_manager=mock_state_manager)

    def calculate_md5(self, content: bytes) -> str:
        """Helper to calculate MD5 hash."""
        return hashlib.md5(content).hexdigest()

    @pytest.mark.asyncio
    async def test_download_package_success(self, download_service, mock_state_manager, tmp_path):
        """Test successful package download and verification."""
        # Arrange
        test_content = b"test package content"
        test_md5 = self.calculate_md5(test_content)
        package_url = "http://example.com/package.zip"
        package_name = "test-package.zip"
        package_size = len(test_content)
        
        # Mock HTTP response with async iterator
        mock_response = AsyncMock()
        mock_response.headers = {"Content-Length": str(package_size)}
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_bytes = lambda chunk_size: async_iterator([test_content])
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()
        
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        
        # Mock aiofiles
        mock_file_handle = AsyncMock()
        mock_file_handle.write = AsyncMock()
        mock_file_handle.__aenter__ = AsyncMock(return_value=mock_file_handle)
        mock_file_handle.__aexit__ = AsyncMock()
        
        with patch('httpx.AsyncClient', return_value=mock_client), \
             patch('aiofiles.open', return_value=mock_file_handle), \
             patch('updater.services.download.verify_md5_or_raise') as mock_verify, \
             patch.object(Path, 'exists', return_value=False):
            
            # Act
            result = await download_service.download_package(
                version="1.0.0",
                package_url=package_url,
                package_name=package_name,
                package_size=package_size,
                package_md5=test_md5
            )
            
            # Assert
            assert result == Path("./tmp") / package_name
            mock_verify.assert_called_once()
            mock_file_handle.write.assert_called_once_with(test_content)
            
            # Verify final status is TO_INSTALL
            final_call = mock_state_manager.update_status.call_args_list[-1]
            assert final_call[1]['stage'] == StageEnum.TO_INSTALL
            assert final_call[1]['progress'] == 100

    @pytest.mark.asyncio
    async def test_download_package_md5_mismatch(self, download_service, mock_state_manager):
        """Test MD5 verification failure."""
        # Arrange
        test_content = b"test package content"
        wrong_md5 = "a" * 32  # Wrong MD5
        package_url = "http://example.com/package.zip"
        package_name = "test-package.zip"
        package_size = len(test_content)
        
        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.headers = {"Content-Length": str(package_size)}
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_bytes = lambda chunk_size: async_iterator([test_content])
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()
        
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        
        # Mock aiofiles
        mock_file_handle = AsyncMock()
        mock_file_handle.write = AsyncMock()
        mock_file_handle.__aenter__ = AsyncMock(return_value=mock_file_handle)
        mock_file_handle.__aexit__ = AsyncMock()
        
        with patch('httpx.AsyncClient', return_value=mock_client), \
             patch('aiofiles.open', return_value=mock_file_handle), \
             patch('updater.services.download.verify_md5_or_raise', side_effect=ValueError("MD5_MISMATCH")), \
             patch.object(Path, 'exists', return_value=False), \
             patch.object(Path, 'unlink'):
            
            # Act & Assert
            with pytest.raises(ValueError, match="MD5_MISMATCH"):
                await download_service.download_package(
                    version="1.0.0",
                    package_url=package_url,
                    package_name=package_name,
                    package_size=package_size,
                    package_md5=wrong_md5
                )
            
            # Verify status updated to FAILED
            final_call = mock_state_manager.update_status.call_args_list[-1]
            assert final_call[1]['stage'] == StageEnum.FAILED
            assert "MD5" in final_call[1]['message']

    @pytest.mark.asyncio
    async def test_download_package_size_mismatch(self, download_service, mock_state_manager):
        """Test package size mismatch detection."""
        # Arrange
        test_content = b"test"
        declared_size = 1000  # Wrong size
        actual_size = len(test_content)
        test_md5 = self.calculate_md5(test_content)
        
        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.headers = {"Content-Length": str(actual_size)}
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_bytes = lambda chunk_size: async_iterator([test_content])
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()
        
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        
        # Mock aiofiles
        mock_file_handle = AsyncMock()
        mock_file_handle.write = AsyncMock()
        mock_file_handle.__aenter__ = AsyncMock(return_value=mock_file_handle)
        mock_file_handle.__aexit__ = AsyncMock()
        
        with patch('httpx.AsyncClient', return_value=mock_client), \
             patch('aiofiles.open', return_value=mock_file_handle), \
             patch.object(Path, 'exists', return_value=False), \
             patch.object(Path, 'unlink'):
            
            # Act & Assert
            with pytest.raises(ValueError, match="PACKAGE_SIZE_MISMATCH"):
                await download_service.download_package(
                    version="1.0.0",
                    package_url="http://example.com/package.zip",
                    package_name="test.zip",
                    package_size=declared_size,
                    package_md5=test_md5
                )
            
            # Verify status updated to FAILED
            final_call = mock_state_manager.update_status.call_args_list[-1]
            assert final_call[1]['stage'] == StageEnum.FAILED

    @pytest.mark.asyncio
    async def test_download_progress_updates(self, download_service, mock_state_manager):
        """Test that progress updates are reported correctly."""
        # Arrange
        # Create content large enough to trigger multiple progress updates
        chunk_size = 64 * 1024  # 64KB
        test_content = b"x" * (chunk_size * 20)  # 20 chunks
        test_md5 = self.calculate_md5(test_content)
        package_size = len(test_content)
        
        # Split into chunks
        chunks = [test_content[i:i+chunk_size] for i in range(0, len(test_content), chunk_size)]
        
        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.headers = {"Content-Length": str(package_size)}
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_bytes = lambda chunk_size: async_iterator(chunks)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()
        
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        
        # Mock aiofiles
        mock_file_handle = AsyncMock()
        mock_file_handle.write = AsyncMock()
        mock_file_handle.__aenter__ = AsyncMock(return_value=mock_file_handle)
        mock_file_handle.__aexit__ = AsyncMock()
        
        with patch('httpx.AsyncClient', return_value=mock_client), \
             patch('aiofiles.open', return_value=mock_file_handle), \
             patch('updater.services.download.verify_md5_or_raise'), \
             patch.object(Path, 'exists', return_value=False):
            
            # Act
            await download_service.download_package(
                version="1.0.0",
                package_url="http://example.com/package.zip",
                package_name="test.zip",
                package_size=package_size,
                package_md5=test_md5
            )
            
            # Assert - check that update_status was called with DOWNLOADING stage
            downloading_calls = [
                call for call in mock_state_manager.update_status.call_args_list
                if call[1]['stage'] == StageEnum.DOWNLOADING
            ]
            assert len(downloading_calls) > 1  # Should have multiple progress updates
            
            # Verify progress values are increasing
            progress_values = [call[1]['progress'] for call in downloading_calls]
            assert progress_values[0] >= 0
            assert progress_values[-1] > progress_values[0]

    @pytest.mark.asyncio
    async def test_download_orphaned_file_deleted(self, download_service, mock_state_manager):
        """Test that orphaned files without state.json are deleted."""
        # Arrange
        test_content = b"test"
        test_md5 = self.calculate_md5(test_content)
        package_name = "test-package.zip"
        
        # Mock: file exists but no persistent state
        mock_state_manager.get_persistent_state.return_value = None
        
        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.headers = {"Content-Length": str(len(test_content))}
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_bytes = lambda chunk_size: async_iterator([test_content])
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()
        
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        
        # Mock aiofiles
        mock_file_handle = AsyncMock()
        mock_file_handle.write = AsyncMock()
        mock_file_handle.__aenter__ = AsyncMock(return_value=mock_file_handle)
        mock_file_handle.__aexit__ = AsyncMock()
        
        with patch('httpx.AsyncClient', return_value=mock_client), \
             patch('aiofiles.open', return_value=mock_file_handle), \
             patch('updater.services.download.verify_md5_or_raise'), \
             patch.object(Path, 'exists', return_value=True), \
             patch.object(Path, 'unlink') as mock_unlink:
            
            # Act
            await download_service.download_package(
                version="1.0.0",
                package_url="http://example.com/package.zip",
                package_name=package_name,
                package_size=len(test_content),
                package_md5=test_md5
            )
            
            # Assert - orphaned file should be deleted
            mock_unlink.assert_called()

    @pytest.mark.asyncio
    async def test_download_resume_with_range_header(self, download_service, mock_state_manager):
        """Test that Range header is used when resuming download."""
        # Arrange
        test_content = b"test package content"
        test_md5 = self.calculate_md5(test_content)
        package_url = "http://example.com/package.zip"
        package_name = "test-package.zip"
        package_size = len(test_content)
        bytes_already_downloaded = 10
        
        # Mock persistent state (same package)
        persistent_state = StateFile(
            version="1.0.0",
            package_url=package_url,
            package_name=package_name,
            package_size=package_size,
            package_md5=test_md5,
            bytes_downloaded=bytes_already_downloaded,
            stage=StageEnum.DOWNLOADING
        )
        mock_state_manager.get_persistent_state.return_value = persistent_state
        
        # Mock HTTP response (remaining bytes)
        remaining_content = test_content[bytes_already_downloaded:]
        mock_response = AsyncMock()
        mock_response.headers = {"Content-Length": str(len(remaining_content))}
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_bytes = lambda chunk_size: async_iterator([remaining_content])
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()
        
        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        
        # Mock aiofiles
        mock_file_handle = AsyncMock()
        mock_file_handle.write = AsyncMock()
        mock_file_handle.__aenter__ = AsyncMock(return_value=mock_file_handle)
        mock_file_handle.__aexit__ = AsyncMock()
        
        # Mock path methods
        mock_stat = MagicMock()
        mock_stat.st_size = bytes_already_downloaded
        
        with patch('httpx.AsyncClient', return_value=mock_client), \
             patch('aiofiles.open', return_value=mock_file_handle), \
             patch('updater.services.download.verify_md5_or_raise'), \
             patch.object(Path, 'exists', return_value=True), \
             patch.object(Path, 'stat', return_value=mock_stat):
            
            # Act
            await download_service.download_package(
                version="1.0.0",
                package_url=package_url,
                package_name=package_name,
                package_size=package_size,
                package_md5=test_md5
            )
            
            # Assert - verify Range header was used
            stream_call = mock_client.stream.call_args
            assert "Range" in stream_call[1]["headers"]
            assert stream_call[1]["headers"]["Range"] == f"bytes={bytes_already_downloaded}-"

    @pytest.mark.asyncio
    async def test_download_different_package_restarts(self, download_service, mock_state_manager):
        """Test that download restarts when URL/version/MD5 changes."""
        # Arrange
        test_content = b"new package"
        new_md5 = self.calculate_md5(test_content)

        # Mock persistent state (different package)
        old_state = StateFile(
            version="0.9.0",  # Different version
            package_url="http://example.com/old-package.zip",  # Different URL
            package_name="test-package.zip",
            package_size=100,
            package_md5="b" * 32,  # Different MD5
            bytes_downloaded=50,
            stage=StageEnum.DOWNLOADING
        )
        mock_state_manager.get_persistent_state.return_value = old_state

        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.headers = {"Content-Length": str(len(test_content))}
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_bytes = lambda chunk_size: async_iterator([test_content])
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        # Mock aiofiles
        mock_file_handle = AsyncMock()
        mock_file_handle.write = AsyncMock()
        mock_file_handle.__aenter__ = AsyncMock(return_value=mock_file_handle)
        mock_file_handle.__aexit__ = AsyncMock()

        with patch('httpx.AsyncClient', return_value=mock_client), \
             patch('aiofiles.open', return_value=mock_file_handle), \
             patch('updater.services.download.verify_md5_or_raise'), \
             patch.object(Path, 'exists', return_value=True), \
             patch.object(Path, 'unlink') as mock_unlink:

            # Act
            await download_service.download_package(
                version="1.0.0",  # New version
                package_url="http://example.com/new-package.zip",  # New URL
                package_name="test-package.zip",
                package_size=len(test_content),
                package_md5=new_md5  # New MD5
            )

            # Assert - old file and state should be deleted
            mock_unlink.assert_called()
            mock_state_manager.delete_state.assert_called()

            # Verify download started from beginning (no Range header)
            stream_call = mock_client.stream.call_args
            assert "Range" not in stream_call[1]["headers"]

    @pytest.mark.asyncio
    async def test_download_without_content_length_header(self, download_service, mock_state_manager):
        """Test download when server doesn't provide Content-Length header.

        This covers two branches:
        - Line 208: if content_length_header (else branch)
        - Line 254: if expected_from_server is not None (else branch, skips size validation)
        """
        # Arrange
        test_content = b"test package without content-length"
        test_md5 = self.calculate_md5(test_content)
        package_url = "http://example.com/package.zip"
        package_name = "test-package.zip"
        package_size = len(test_content)

        # Mock HTTP response WITHOUT Content-Length header
        mock_response = AsyncMock()
        mock_response.headers = {}  # No Content-Length header
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_bytes = lambda chunk_size: async_iterator([test_content])
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        # Mock aiofiles
        mock_file_handle = AsyncMock()
        mock_file_handle.write = AsyncMock()
        mock_file_handle.__aenter__ = AsyncMock(return_value=mock_file_handle)
        mock_file_handle.__aexit__ = AsyncMock()

        with patch('httpx.AsyncClient', return_value=mock_client), \
             patch('aiofiles.open', return_value=mock_file_handle), \
             patch('updater.services.download.verify_md5_or_raise') as mock_verify, \
             patch.object(Path, 'exists', return_value=False):

            # Act
            result = await download_service.download_package(
                version="1.0.0",
                package_url=package_url,
                package_name=package_name,
                package_size=package_size,
                package_md5=test_md5
            )

            # Assert
            assert result == Path("./tmp") / package_name
            mock_verify.assert_called_once()
            mock_file_handle.write.assert_called_once_with(test_content)

            # Verify final status is TO_INSTALL
            final_call = mock_state_manager.update_status.call_args_list[-1]
            assert final_call[1]['stage'] == StageEnum.TO_INSTALL
            assert final_call[1]['progress'] == 100

    @pytest.mark.asyncio
    async def test_download_fresh_start_no_range_header(self, download_service, mock_state_manager):
        """Test fresh download (bytes_downloaded=0) doesn't use Range header.

        This explicitly tests the else branch of: if bytes_downloaded > 0 (line 211)
        Most other tests already cover this implicitly, but this makes it explicit.
        """
        # Arrange
        test_content = b"fresh download test"
        test_md5 = self.calculate_md5(test_content)
        package_size = len(test_content)

        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.headers = {"Content-Length": str(package_size)}
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_bytes = lambda chunk_size: async_iterator([test_content])
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        # Mock aiofiles
        mock_file_handle = AsyncMock()
        mock_file_handle.write = AsyncMock()
        mock_file_handle.__aenter__ = AsyncMock(return_value=mock_file_handle)
        mock_file_handle.__aexit__ = AsyncMock()

        with patch('httpx.AsyncClient', return_value=mock_client), \
             patch('aiofiles.open', return_value=mock_file_handle), \
             patch('updater.services.download.verify_md5_or_raise'), \
             patch.object(Path, 'exists', return_value=False):

            # Act
            await download_service.download_package(
                version="1.0.0",
                package_url="http://example.com/package.zip",
                package_name="test.zip",
                package_size=package_size,
                package_md5=test_md5
            )

            # Assert - verify NO Range header was used (fresh download)
            stream_call = mock_client.stream.call_args
            headers = stream_call[1].get("headers", {})
            assert "Range" not in headers, "Fresh download should not use Range header"

    @pytest.mark.asyncio
    async def test_download_incomplete_transfer(self, download_service, mock_state_manager):
        """Test detection when server sends fewer bytes than Content-Length declares.

        This covers the true branch of: if bytes_downloaded != expected_from_server (line 258)
        Simulates network interruption where server declared X bytes but only sent Y bytes.
        """
        # Arrange
        declared_size = 1000  # Server declares 1000 bytes
        actual_content = b"incomplete"  # But only sends 10 bytes
        actual_size = len(actual_content)  # 10 bytes
        test_md5 = self.calculate_md5(actual_content)

        # Mock HTTP response - Content-Length says 1000, but only 10 bytes sent
        mock_response = AsyncMock()
        mock_response.headers = {"Content-Length": str(declared_size)}  # Declares 1000
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_bytes = lambda chunk_size: async_iterator([actual_content])  # Sends 10
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        # Mock aiofiles
        mock_file_handle = AsyncMock()
        mock_file_handle.write = AsyncMock()
        mock_file_handle.__aenter__ = AsyncMock(return_value=mock_file_handle)
        mock_file_handle.__aexit__ = AsyncMock()

        with patch('httpx.AsyncClient', return_value=mock_client), \
             patch('aiofiles.open', return_value=mock_file_handle), \
             patch.object(Path, 'exists', return_value=False), \
             patch.object(Path, 'unlink'):

            # Act & Assert
            with pytest.raises(ValueError, match="INCOMPLETE_DOWNLOAD"):
                await download_service.download_package(
                    version="1.0.0",
                    package_url="http://example.com/package.zip",
                    package_name="test.zip",
                    package_size=declared_size,
                    package_md5=test_md5
                )

            # Verify status updated to FAILED
            final_call = mock_state_manager.update_status.call_args_list[-1]
            assert final_call[1]['stage'] == StageEnum.FAILED
