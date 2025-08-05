"""
Embedding Service Factory
임베딩 서비스 팩토리 - SOLID 원칙 (Dependency Inversion Principle)
"""

import asyncio
import logging
from typing import Optional
from app.core.embedding_interfaces.embedding_interface import IEmbeddingService
from app.services.embedding.vertex_ai_embedding import VertexAIEmbeddingService
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingServiceFactory:
    """임베딩 서비스 팩토리"""

    _instance: Optional[IEmbeddingService] = None
    _lock = asyncio.Lock()

    @classmethod
    async def get_embedding_service(cls) -> IEmbeddingService:
        """
        임베딩 서비스 인스턴스 반환 (싱글톤)

        Returns:
            IEmbeddingService: 임베딩 서비스 인스턴스
        """
        if cls._instance is None:
            async with cls._lock:
                # 더블 체크 패턴
                if cls._instance is None:
                    cls._instance = cls._create_service()

        return cls._instance

    @classmethod
    def get_embedding_service_sync(cls) -> IEmbeddingService:
        """
        동기 버전 - 기존 코드 호환성을 위해 유지

        Returns:
            IEmbeddingService: 임베딩 서비스 인스턴스
        """
        if cls._instance is None:
            cls._instance = cls._create_service()

        return cls._instance

    @classmethod
    def _create_service(cls) -> IEmbeddingService:
        """
        설정에 따라 적절한 임베딩 서비스 생성

        Returns:
            IEmbeddingService: 생성된 임베딩 서비스
        """
        try:
            # 환경 변수 또는 설정에서 서비스 타입 결정
            service_type = getattr(settings, "EMBEDDING_SERVICE", "vertex_ai")

            if service_type == "vertex_ai":
                logger.info("Google Vertex AI 임베딩 서비스를 사용합니다")
                model_name = getattr(
                    settings, "VERTEX_AI_EMBEDDING_MODEL", "text-embedding-004"
                )
                return VertexAIEmbeddingService(model_name=model_name)
            else:
                raise ValueError(f"지원하지 않는 임베딩 서비스 타입: {service_type}")

        except Exception as e:
            logger.error(f"임베딩 서비스 생성 실패: {str(e)}")
            raise

    @classmethod
    def reset(cls):
        """서비스 인스턴스 리셋 (주로 테스트용)"""
        cls._instance = None
