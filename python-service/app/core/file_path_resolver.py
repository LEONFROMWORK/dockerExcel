"""
File Path Resolver
파일 ID와 실제 경로 매핑 관리
"""

import os
from typing import Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class FilePathResolver:
    """파일 ID와 실제 경로 매핑"""

    # 메모리 캐시 (실제로는 DB나 Redis 사용 권장)
    _mappings: Dict[str, Dict[str, any]] = {}

    @classmethod
    async def save_file_mapping(
        cls, file_id: str, file_path: str, metadata: Optional[Dict] = None
    ) -> None:
        """
        파일 ID와 경로 매핑 저장

        Args:
            file_id: 파일 고유 ID
            file_path: 실제 파일 경로
            metadata: 추가 메타데이터
        """
        cls._mappings[file_id] = {
            "file_path": file_path,
            "created_at": datetime.now().isoformat(),
            "metadata": metadata or {},
        }
        logger.info(f"파일 매핑 저장: {file_id} -> {file_path}")

    @classmethod
    async def get_file_path(cls, file_id: str) -> Optional[str]:
        """
        파일 ID로 실제 경로 조회

        Args:
            file_id: 파일 고유 ID

        Returns:
            파일 경로 또는 None
        """
        mapping = cls._mappings.get(file_id)
        if mapping:
            file_path = mapping["file_path"]
            # 파일 존재 확인
            if os.path.exists(file_path):
                return file_path
            else:
                logger.warning(f"매핑된 파일이 존재하지 않음: {file_path}")
                # 매핑 제거
                del cls._mappings[file_id]

        # 폴백: 규칙 기반 경로 생성
        default_path = f"/tmp/excel_files/{file_id}.xlsx"
        if os.path.exists(default_path):
            # 발견된 경로 자동 매핑
            await cls.save_file_mapping(file_id, default_path)
            return default_path

        return None

    @classmethod
    async def generate_file_id(cls, filename: str) -> str:
        """
        파일명으로 고유 ID 생성

        Args:
            filename: 원본 파일명

        Returns:
            고유 파일 ID
        """
        import hashlib
        from datetime import datetime

        # 타임스탬프와 파일명을 조합하여 고유 ID 생성
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        hash_input = f"{filename}_{timestamp}"
        file_id = hashlib.md5(hash_input.encode()).hexdigest()[:12]

        return f"excel_{file_id}"

    @classmethod
    async def cleanup_old_mappings(cls, max_age_hours: int = 24) -> int:
        """
        오래된 매핑 정리

        Args:
            max_age_hours: 최대 보관 시간

        Returns:
            정리된 매핑 수
        """
        from datetime import datetime, timedelta

        current_time = datetime.now()
        cutoff_time = current_time - timedelta(hours=max_age_hours)

        to_remove = []
        for file_id, mapping in cls._mappings.items():
            created_at = datetime.fromisoformat(mapping["created_at"])
            if created_at < cutoff_time:
                # 파일도 함께 삭제
                file_path = mapping["file_path"]
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        logger.error(f"파일 삭제 실패: {file_path}, {str(e)}")
                to_remove.append(file_id)

        # 매핑 제거
        for file_id in to_remove:
            del cls._mappings[file_id]

        logger.info(f"오래된 매핑 {len(to_remove)}개 정리됨")
        return len(to_remove)

    @classmethod
    def get_all_mappings(cls) -> Dict[str, Dict]:
        """모든 매핑 조회 (디버깅용)"""
        return cls._mappings.copy()
