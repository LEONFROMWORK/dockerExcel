"""
Streaming file storage implementation for large files.
"""

import os
import aiofiles
from typing import Optional, AsyncIterator
from datetime import datetime
import hashlib
import logging
from pathlib import Path

from ..domain.services import FileContentService
from ..domain.models import WOPIFile
from .structured_logger import wopi_logger

logger = logging.getLogger(__name__)


class StreamingFileStorage(FileContentService):
    """Streaming file storage for handling large files efficiently."""

    def __init__(
        self,
        base_path: str = "/tmp/excel_files",
        chunk_size: int = 1024 * 1024,  # 1MB chunks
        max_file_size: int = 500 * 1024 * 1024,  # 500MB
    ):
        """Initialize streaming storage."""
        self.base_path = Path(base_path)
        self.chunk_size = chunk_size
        self.max_file_size = max_file_size
        self.allowed_extensions = {".xlsx", ".xls", ".xlsm", ".ods", ".csv"}

        # Create base directory
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _validate_file_id(self, file_id: str) -> bool:
        """Validate file ID to prevent path traversal."""
        # Remove any path components
        clean_id = os.path.basename(file_id)
        return clean_id == file_id and clean_id != ""

    def _get_file_path(self, file_id: str) -> Optional[Path]:
        """Get safe file path."""
        if not self._validate_file_id(file_id):
            return None

        # Use subdirectories to avoid too many files in one directory
        sub_dir = file_id[:2] if len(file_id) >= 2 else "00"
        file_dir = self.base_path / sub_dir
        file_dir.mkdir(exist_ok=True)

        return file_dir / file_id

    async def get_file_content(self, file_id: str, token: str) -> Optional[bytes]:
        """Get complete file content (for small files)."""
        file_path = self._get_file_path(file_id)
        if not file_path or not file_path.exists():
            logger.warning(f"File not found: {file_id}")
            return None

        try:
            # Check file size
            file_size = file_path.stat().st_size
            if file_size > 50 * 1024 * 1024:  # 50MB limit for direct read
                logger.warning(
                    f"File too large for direct read: {file_id} ({file_size} bytes)"
                )
                return None

            async with aiofiles.open(file_path, "rb") as f:
                content = await f.read()

            wopi_logger.log_file_accessed(
                file_id=file_id,
                user_id="system",
                operation="read_full",
                success=True,
                size_bytes=len(content),
            )

            return content

        except Exception as e:
            logger.error(f"Error reading file {file_id}: {str(e)}")
            wopi_logger.log_file_accessed(
                file_id=file_id, user_id="system", operation="read_full", success=False
            )
            return None

    async def get_file_stream(
        self,
        file_id: str,
        token: str,
        start_byte: int = 0,
        end_byte: Optional[int] = None,
    ) -> AsyncIterator[bytes]:
        """Stream file content in chunks."""
        file_path = self._get_file_path(file_id)
        if not file_path or not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_id}")

        file_size = file_path.stat().st_size

        # Validate byte range
        if start_byte < 0:
            start_byte = 0
        if end_byte is None or end_byte >= file_size:
            end_byte = file_size - 1

        if start_byte > end_byte:
            raise ValueError("Invalid byte range")

        bytes_to_read = end_byte - start_byte + 1

        try:
            async with aiofiles.open(file_path, "rb") as f:
                await f.seek(start_byte)

                bytes_read = 0
                while bytes_read < bytes_to_read:
                    chunk_size = min(self.chunk_size, bytes_to_read - bytes_read)
                    chunk = await f.read(chunk_size)

                    if not chunk:
                        break

                    bytes_read += len(chunk)
                    yield chunk

            wopi_logger.log_file_accessed(
                file_id=file_id,
                user_id="system",
                operation="read_stream",
                success=True,
                size_bytes=bytes_read,
            )

        except Exception as e:
            logger.error(f"Error streaming file {file_id}: {str(e)}")
            wopi_logger.log_file_accessed(
                file_id=file_id,
                user_id="system",
                operation="read_stream",
                success=False,
            )
            raise

    async def save_file_content(self, file_id: str, content: bytes, token: str) -> bool:
        """Save complete file content."""
        # Validate file size
        if len(content) > self.max_file_size:
            logger.error(f"File too large: {len(content)} bytes")
            return False

        file_path = self._get_file_path(file_id)
        if not file_path:
            logger.error(f"Invalid file ID: {file_id}")
            return False

        try:
            # Write to temporary file first
            temp_path = file_path.with_suffix(".tmp")

            async with aiofiles.open(temp_path, "wb") as f:
                await f.write(content)

            # Atomic rename
            temp_path.replace(file_path)

            wopi_logger.log_file_accessed(
                file_id=file_id,
                user_id="system",
                operation="write_full",
                success=True,
                size_bytes=len(content),
            )

            return True

        except Exception as e:
            logger.error(f"Error saving file {file_id}: {str(e)}")
            wopi_logger.log_file_accessed(
                file_id=file_id, user_id="system", operation="write_full", success=False
            )
            # Clean up temp file if exists
            try:
                temp_path.unlink()
            except Exception:
                pass
            return False

    async def save_file_stream(
        self,
        file_id: str,
        content_stream: AsyncIterator[bytes],
        token: str,
        expected_size: Optional[int] = None,
    ) -> bool:
        """Save file from async stream."""
        file_path = self._get_file_path(file_id)
        if not file_path:
            logger.error(f"Invalid file ID: {file_id}")
            return False

        temp_path = file_path.with_suffix(".tmp")
        total_size = 0
        checksum = hashlib.sha256()

        try:
            async with aiofiles.open(temp_path, "wb") as f:
                async for chunk in content_stream:
                    # Validate chunk
                    if not isinstance(chunk, bytes):
                        raise ValueError("Invalid chunk type")

                    # Check size limit
                    if total_size + len(chunk) > self.max_file_size:
                        raise ValueError(
                            f"File size exceeded: {total_size + len(chunk)}"
                        )

                    # Write chunk
                    await f.write(chunk)
                    total_size += len(chunk)
                    checksum.update(chunk)

            # Verify expected size if provided
            if expected_size is not None and total_size != expected_size:
                raise ValueError(
                    f"Size mismatch: expected {expected_size}, got {total_size}"
                )

            # Atomic rename
            temp_path.replace(file_path)

            wopi_logger.log_file_accessed(
                file_id=file_id,
                user_id="system",
                operation="write_stream",
                success=True,
                size_bytes=total_size,
            )

            logger.info(
                f"Saved file {file_id}: {total_size} bytes, checksum: {checksum.hexdigest()}"
            )
            return True

        except Exception as e:
            logger.error(f"Error saving file stream {file_id}: {str(e)}")
            wopi_logger.log_file_accessed(
                file_id=file_id,
                user_id="system",
                operation="write_stream",
                success=False,
            )
            # Clean up temp file
            try:
                temp_path.unlink()
            except Exception:
                pass
            return False

    async def get_file_info(self, file_id: str) -> Optional[WOPIFile]:
        """Get file metadata."""
        file_path = self._get_file_path(file_id)
        if not file_path or not file_path.exists():
            return None

        try:
            stat = file_path.stat()

            # Check file extension
            extension = file_path.suffix.lower()
            if extension not in self.allowed_extensions:
                logger.warning(f"Invalid file extension: {extension}")
                return None

            return WOPIFile(
                id=file_id,
                name=f"{file_id}{extension}",
                size=stat.st_size,
                owner_id="system",
                last_modified=datetime.fromtimestamp(stat.st_mtime),
                version="1.0",
            )

        except Exception as e:
            logger.error(f"Error getting file info {file_id}: {str(e)}")
            return None

    async def delete_file(self, file_id: str, token: str) -> bool:
        """Delete file."""
        file_path = self._get_file_path(file_id)
        if not file_path or not file_path.exists():
            return False

        try:
            file_path.unlink()

            wopi_logger.log_file_accessed(
                file_id=file_id, user_id="system", operation="delete", success=True
            )

            return True

        except Exception as e:
            logger.error(f"Error deleting file {file_id}: {str(e)}")
            wopi_logger.log_file_accessed(
                file_id=file_id, user_id="system", operation="delete", success=False
            )
            return False
