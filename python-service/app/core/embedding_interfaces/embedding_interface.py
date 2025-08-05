"""
Embedding Service Interface
임베딩 서비스를 위한 추상 인터페이스 (SOLID - Interface Segregation Principle)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class IEmbeddingService(ABC):
    """임베딩 서비스 인터페이스"""

    @abstractmethod
    async def create_embedding(self, text: str) -> List[float]:
        """단일 텍스트를 임베딩 벡터로 변환"""

    @abstractmethod
    async def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """여러 텍스트를 배치로 임베딩"""

    @abstractmethod
    def get_embedding_dimension(self) -> int:
        """임베딩 벡터의 차원 반환"""

    @abstractmethod
    def get_max_text_length(self) -> int:
        """최대 텍스트 길이 반환"""


class IEmbeddingUsageTracker(ABC):
    """임베딩 사용량 추적 인터페이스"""

    @abstractmethod
    def track_usage(self, text: str) -> None:
        """사용량 추적"""

    @abstractmethod
    def get_usage_stats(self) -> Dict[str, Any]:
        """사용량 통계 반환"""


class IEmbeddingCache(ABC):
    """임베딩 캐시 인터페이스"""

    @abstractmethod
    async def get_cached_embedding(self, text: str) -> Optional[List[float]]:
        """캐시된 임베딩 조회"""

    @abstractmethod
    async def cache_embedding(self, text: str, embedding: List[float]) -> None:
        """임베딩 캐시"""

    @abstractmethod
    async def clear_cache(self) -> None:
        """캐시 초기화"""
