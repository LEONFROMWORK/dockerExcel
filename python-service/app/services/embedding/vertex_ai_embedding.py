"""
Google Vertex AI Embedding Service Implementation
SOLID 원칙을 준수하는 Vertex AI 임베딩 서비스 구현
"""

import os
import asyncio
import logging
from typing import List, Dict, Any
from google.cloud import aiplatform
from google.oauth2 import service_account
from app.core.embedding_interfaces.embedding_interface import (
    IEmbeddingService,
    IEmbeddingUsageTracker,
)

logger = logging.getLogger(__name__)


class VertexAIEmbeddingService(IEmbeddingService, IEmbeddingUsageTracker):
    """Vertex AI 임베딩 서비스 구현"""

    def __init__(self, model_name: str = "text-embedding-004"):
        """
        서비스 초기화

        Args:
            model_name: 사용할 Vertex AI 모델 이름
                - textembedding-gecko@001: 768차원, 레거시
                - textembedding-gecko@002: 768차원
                - text-embedding-004: 768차원, 최신
        """
        self.model_name = model_name
        self._embedding_dimension = 768
        self._max_text_length = 10000

        # 사용량 추적
        self._monthly_chars = 0
        self._free_tier_limit = 5_000_000  # 5M characters

        # 초기화
        self._initialize_client()

    def _initialize_client(self):
        """Vertex AI 클라이언트 초기화"""
        try:
            # 환경 변수에서 설정 가져오기
            credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            project_id = os.getenv("GCP_PROJECT_ID", "excel-unified")
            location = os.getenv("GCP_LOCATION", "us-central1")

            if not credentials_path:
                logger.warning(
                    "GOOGLE_APPLICATION_CREDENTIALS 환경 변수가 설정되지 않았습니다"
                )
                # 테스트 환경에서는 초기화를 건너뜁니다
                self.model = None
                return

            # 서비스 계정 인증
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )

            # Vertex AI 초기화
            aiplatform.init(
                project=project_id, location=location, credentials=credentials
            )

            # 텍스트 임베딩 모델 로드
            from vertexai.language_models import TextEmbeddingModel

            self.model = TextEmbeddingModel.from_pretrained(self.model_name)

            logger.info(
                f"Vertex AI 임베딩 서비스 초기화 완료 (프로젝트: {project_id}, 리전: {location}, 모델: {self.model_name})"
            )

        except Exception as e:
            logger.error(f"Vertex AI 임베딩 서비스 초기화 실패: {str(e)}")
            raise

    async def create_embedding(self, text: str) -> List[float]:
        """단일 텍스트를 임베딩 벡터로 변환"""
        try:
            # 텍스트 길이 확인 및 조정
            if len(text) > self._max_text_length:
                text = text[: self._max_text_length]
                logger.warning(
                    f"텍스트가 너무 길어 잘렸습니다 ({self._max_text_length}자)"
                )

            # 빈 텍스트 처리
            if not text.strip():
                logger.warning("빈 텍스트는 임베딩할 수 없습니다")
                return [0.0] * self._embedding_dimension

            # 사용량 추적
            self.track_usage(text)

            # Vertex AI는 동기 API이므로 executor 사용
            loop = asyncio.get_event_loop()

            # ThreadPoolExecutor를 사용하여 비동기 처리
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                embeddings = await loop.run_in_executor(
                    executor, lambda: self.model.get_embeddings([text])
                )

            # 임베딩 벡터 반환
            return embeddings[0].values

        except Exception as e:
            logger.error(f"Vertex AI 임베딩 생성 오류: {str(e)}")
            raise

    async def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """여러 텍스트를 배치로 임베딩"""
        try:
            # 빈 리스트 처리
            if not texts:
                return []

            # 텍스트 길이 조정 및 빈 텍스트 처리
            processed_texts = []
            for text in texts:
                if not text.strip():
                    processed_texts.append("empty")  # 빈 텍스트 대체
                else:
                    processed_texts.append(
                        text[: self._max_text_length]
                        if len(text) > self._max_text_length
                        else text
                    )

            # 사용량 추적
            for text in processed_texts:
                self.track_usage(text)

            # Vertex AI 배치 크기 제한 (최대 5개)
            batch_size = 5
            all_embeddings = []

            loop = asyncio.get_event_loop()

            # 동시 실행을 위한 executor
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                for i in range(0, len(processed_texts), batch_size):
                    batch = processed_texts[i : i + batch_size]
                    embeddings = await loop.run_in_executor(
                        executor, lambda b=batch: self.model.get_embeddings(b)
                    )
                    all_embeddings.extend([e.values for e in embeddings])

            return all_embeddings

        except Exception as e:
            logger.error(f"Vertex AI 배치 임베딩 오류: {str(e)}")
            raise

    def get_embedding_dimension(self) -> int:
        """임베딩 벡터의 차원 반환"""
        return self._embedding_dimension

    def get_max_text_length(self) -> int:
        """최대 텍스트 길이 반환"""
        return self._max_text_length

    def track_usage(self, text: str) -> None:
        """사용량 추적"""
        if not text:
            return

        self._monthly_chars += len(text)

        # 사용량 경고
        usage_percentage = (self._monthly_chars / self._free_tier_limit) * 100

        if self._monthly_chars > self._free_tier_limit:
            logger.warning(
                f"Vertex AI 무료 티어 초과: {self._monthly_chars:,} / {self._free_tier_limit:,} "
                f"characters ({usage_percentage:.1f}%)"
            )
        elif self._monthly_chars > self._free_tier_limit * 0.8:
            logger.info(
                f"Vertex AI 무료 티어 80% 사용: {self._monthly_chars:,} / {self._free_tier_limit:,} "
                f"characters ({usage_percentage:.1f}%)"
            )

    def get_usage_stats(self) -> Dict[str, Any]:
        """사용량 통계 반환"""
        return {
            "service": "Vertex AI",
            "model": self.model_name,
            "monthly_characters": self._monthly_chars,
            "free_tier_limit": self._free_tier_limit,
            "usage_percentage": (self._monthly_chars / self._free_tier_limit) * 100,
            "remaining_characters": max(0, self._free_tier_limit - self._monthly_chars),
        }
