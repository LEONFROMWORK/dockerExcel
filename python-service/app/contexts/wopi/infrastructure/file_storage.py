"""
File storage implementation for WOPI.
Handles actual file operations on the filesystem.
"""

import os
import aiofiles
from typing import Optional
from datetime import datetime
import logging

from ..domain.services import FileContentService
from ..domain.models import WOPIFile

logger = logging.getLogger(__name__)


class LocalFileStorage(FileContentService):
    """Local filesystem implementation of FileContentService."""
    
    def __init__(self, base_path: str = "/tmp/excel_files", max_file_size: int = 100 * 1024 * 1024):
        """Initialize with base storage path."""
        self.base_path = base_path
        self.max_file_size = max_file_size  # 100MB default
        self.allowed_extensions = {'.xlsx', '.xls', '.xlsm', '.ods'}
        os.makedirs(base_path, exist_ok=True)
    
    async def get_file_content(self, file_id: str, token: str) -> Optional[bytes]:
        """Get file content from filesystem."""
        try:
            file_path = await self.get_file_path(file_id)
            if not file_path or not os.path.exists(file_path):
                logger.warning(f"File not found: {file_id}")
                return None
            
            async with aiofiles.open(file_path, 'rb') as f:
                content = await f.read()
            
            logger.info(f"Successfully read file: {file_id}, size: {len(content)} bytes")
            return content
            
        except Exception as e:
            logger.error(f"Error reading file {file_id}: {str(e)}")
            return None
    
    async def save_file_content(
        self, 
        file_id: str, 
        content: bytes, 
        token: str
    ) -> bool:
        """Save file content to filesystem."""
        # Validate file size
        if len(content) > self.max_file_size:
            logger.error(f"File too large: {len(content)} bytes (max: {self.max_file_size})")
            return False
        try:
            file_path = await self.get_file_path(file_id)
            if not file_path:
                logger.error(f"Invalid file path for ID: {file_id}")
                return False
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Write file
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(content)
            
            logger.info(f"Successfully saved file: {file_id}, size: {len(content)} bytes")
            return True
            
        except Exception as e:
            logger.error(f"Error saving file {file_id}: {str(e)}")
            return False
    
    async def get_file_path(self, file_id: str) -> Optional[str]:
        """Get physical file path for given file ID."""
        # Simple implementation - in production, this would map to actual storage
        # For now, use file_id as filename
        if not file_id:
            return None
        
        # Sanitize file_id to prevent path traversal
        safe_id = file_id.replace('/', '_').replace('..', '_')
        return os.path.join(self.base_path, f"{safe_id}.xlsx")