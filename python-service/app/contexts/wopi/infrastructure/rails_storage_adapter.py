"""
Rails Active Storage adapter for WOPI file access.
Integrates with Rails to retrieve Excel files through Active Storage.
"""

import os
import logging
import httpx
from typing import Optional, AsyncIterator
from datetime import datetime
from pathlib import Path
import tempfile

from ..domain.services import FileContentService
from ..domain.models import WOPIFile
from .structured_logger import wopi_logger

logger = logging.getLogger(__name__)


class RailsStorageAdapter(FileContentService):
    """Adapter to access files from Rails Active Storage."""

    def __init__(self):
        """Initialize Rails storage adapter."""
        self.rails_api_url = os.getenv("RAILS_API_URL", "http://localhost:3000")
        self.rails_api_key = os.getenv("RAILS_INTERNAL_API_KEY", "development-key")
        self.cache_dir = Path("/tmp/excel_cache")
        self.cache_dir.mkdir(exist_ok=True)

    async def _fetch_from_rails(self, file_id: str) -> Optional[dict]:
        """Fetch file data from Rails API."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.rails_api_url}/api/v1/excel/files/{file_id}/download",
                    headers={
                        "X-Internal-Api-Key": self.rails_api_key,
                        "Accept": "application/json",
                    },
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(
                        f"Failed to fetch file from Rails: {response.status_code}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Error fetching file from Rails: {str(e)}")
            return None

    async def _download_file_content(self, download_url: str) -> Optional[bytes]:
        """Download file content from Active Storage URL."""
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(download_url)

                if response.status_code == 200:
                    return response.content
                else:
                    logger.error(
                        f"Failed to download file content: {response.status_code}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Error downloading file content: {str(e)}")
            return None

    def _get_cache_path(self, file_id: str) -> Path:
        """Get cache file path."""
        return self.cache_dir / f"{file_id}.xlsx"

    async def get_file_content(self, file_id: str, token: str) -> Optional[bytes]:
        """Get complete file content from Rails."""
        # Check cache first
        cache_path = self._get_cache_path(file_id)
        if cache_path.exists():
            try:
                with open(cache_path, "rb") as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"Cache read failed: {str(e)}")

        # Fetch from Rails
        file_data = await self._fetch_from_rails(file_id)
        if not file_data or "download_url" not in file_data:
            logger.error(f"No download URL for file {file_id}")
            return None

        # Download content
        content = await self._download_file_content(file_data["download_url"])
        if content:
            # Cache for future use
            try:
                with open(cache_path, "wb") as f:
                    f.write(content)
            except Exception as e:
                logger.warning(f"Cache write failed: {str(e)}")

            wopi_logger.log_file_accessed(
                file_id=file_id,
                user_id="system",
                operation="read_full",
                success=True,
                size_bytes=len(content),
            )

        return content

    async def get_file_stream(
        self,
        file_id: str,
        token: str,
        start_byte: int = 0,
        end_byte: Optional[int] = None,
    ) -> AsyncIterator[bytes]:
        """Stream file content in chunks."""
        # For now, get full content and stream from memory
        # In production, implement proper streaming from Rails
        content = await self.get_file_content(file_id, token)
        if not content:
            raise FileNotFoundError(f"File not found: {file_id}")

        # Validate byte range
        file_size = len(content)
        if start_byte < 0:
            start_byte = 0
        if end_byte is None or end_byte >= file_size:
            end_byte = file_size - 1

        if start_byte > end_byte:
            raise ValueError("Invalid byte range")

        # Stream the requested range
        chunk_size = 1024 * 1024  # 1MB chunks
        current = start_byte

        while current <= end_byte:
            chunk_end = min(current + chunk_size, end_byte + 1)
            yield content[current:chunk_end]
            current = chunk_end

    async def save_file_content(self, file_id: str, content: bytes, token: str) -> bool:
        """Save file content back to Rails."""
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
                tmp_file.write(content)
                tmp_path = tmp_file.name

            # Upload to Rails
            async with httpx.AsyncClient() as client:
                with open(tmp_path, "rb") as f:
                    files = {
                        "file": (
                            "updated.xlsx",
                            f,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    }
                    response = await client.put(
                        f"{self.rails_api_url}/api/v1/excel/files/{file_id}/update",
                        files=files,
                        headers={"X-Internal-Api-Key": self.rails_api_key},
                    )

                success = response.status_code == 200

                if success:
                    # Update cache
                    cache_path = self._get_cache_path(file_id)
                    try:
                        with open(cache_path, "wb") as f:
                            f.write(content)
                    except (IOError, OSError):
                        pass

                    wopi_logger.log_file_accessed(
                        file_id=file_id,
                        user_id="system",
                        operation="write_full",
                        success=True,
                        size_bytes=len(content),
                    )

                return success

        except Exception as e:
            logger.error(f"Error saving file to Rails: {str(e)}")
            return False
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except (KeyError, IndexError, AttributeError):
                pass

    async def save_file_stream(
        self,
        file_id: str,
        content_stream: AsyncIterator[bytes],
        token: str,
        expected_size: Optional[int] = None,
    ) -> bool:
        """Save file from async stream."""
        # Collect stream into bytes
        chunks = []
        total_size = 0

        async for chunk in content_stream:
            chunks.append(chunk)
            total_size += len(chunk)

        content = b"".join(chunks)

        # Verify size if provided
        if expected_size is not None and total_size != expected_size:
            logger.error(f"Size mismatch: expected {expected_size}, got {total_size}")
            return False

        return await self.save_file_content(file_id, content, token)

    async def get_file_info(self, file_id: str) -> Optional[WOPIFile]:
        """Get file metadata from Rails."""
        file_data = await self._fetch_from_rails(file_id)
        if not file_data:
            return None

        try:
            return WOPIFile(
                id=file_id,
                name=file_data.get("filename", f"file_{file_id}.xlsx"),
                size=file_data.get("size", 0),
                owner_id=str(file_data.get("user_id", "unknown")),
                last_modified=datetime.fromisoformat(
                    file_data.get("updated_at", datetime.now().isoformat())
                ),
                version=file_data.get("version", "1.0"),
            )
        except Exception as e:
            logger.error(f"Error parsing file info: {str(e)}")
            return None

    async def delete_file(self, file_id: str, token: str) -> bool:
        """Delete file cache."""
        # Only delete from cache, not from Rails
        cache_path = self._get_cache_path(file_id)
        try:
            if cache_path.exists():
                cache_path.unlink()
            return True
        except Exception as e:
            logger.error(f"Error deleting cache: {str(e)}")
            return False

    async def get_file_path(self, file_id: str) -> Optional[Path]:
        """Get file path - required by abstract base class."""
        # For Rails integration, we don't have a direct file path
        # Instead, we download and cache the file
        cache_path = self._get_cache_path(file_id)

        # Ensure file is cached
        if not cache_path.exists():
            content = await self.get_file_content(file_id, "system")
            if not content:
                return None

        return cache_path if cache_path.exists() else None
