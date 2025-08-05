"""
Session Context Store
세션별 컨텍스트 저장소 - Redis 기반 영구 저장
"""

import json
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import redis.asyncio as redis
from app.services.context.workbook_context import WorkbookContext
from app.core.config import settings
from app.core.integrated_cache import integrated_cache
import logging

logger = logging.getLogger(__name__)


class SessionContextStore:
    """세션별 컨텍스트 저장소"""

    def __init__(self, redis_url: Optional[str] = None):
        """
        초기화

        Args:
            redis_url: Redis 연결 URL (기본값: settings.REDIS_URL)
        """
        self.redis_url = redis_url or getattr(
            settings, "REDIS_URL", "redis://localhost:6379"
        )
        self._redis: Optional[redis.Redis] = None
        # 로컬 캐시를 integrated_cache로 대체
        self._lock = asyncio.Lock()

        # 설정
        self.ttl = 3600 * 24  # 24시간
        self.max_history_per_session = 100
        self.key_prefix = "excel_unified:session:"

    async def _get_redis(self) -> redis.Redis:
        """Redis 연결 획득"""
        if self._redis is None:
            self._redis = await redis.from_url(
                self.redis_url, decode_responses=True, max_connections=10
            )
        return self._redis

    async def save_session_context(
        self, session_id: str, context_data: Dict[str, Any]
    ) -> bool:
        """
        세션 컨텍스트 저장

        Args:
            session_id: 세션 ID
            context_data: 저장할 컨텍스트 데이터

        Returns:
            성공 여부
        """
        try:
            async with self._lock:
                # 타임스탬프 추가
                context_data["last_updated"] = datetime.now().isoformat()

                # Redis에 저장
                redis_client = await self._get_redis()
                key = f"{self.key_prefix}{session_id}"

                # JSON 직렬화
                json_data = json.dumps(context_data, ensure_ascii=False)

                # 저장 및 TTL 설정
                await redis_client.setex(key, self.ttl, json_data)

                # 통합 캐시에도 저장 (빠른 접근을 위해)
                await integrated_cache.set(key, context_data, ttl=self.ttl)

                # 세션 목록에 추가
                await self._add_to_active_sessions(session_id)

                logger.info(f"세션 컨텍스트 저장됨: {session_id}")
                return True

        except Exception as e:
            logger.error(f"세션 컨텍스트 저장 실패: {str(e)}")
            return False

    async def get_session_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        세션 컨텍스트 조회

        Args:
            session_id: 세션 ID

        Returns:
            컨텍스트 데이터 또는 None
        """
        try:
            # 통합 캐시에서 먼저 확인
            key = f"{self.key_prefix}{session_id}"
            cached_data = await integrated_cache.get(key)
            if cached_data:
                return cached_data

            # Redis에서 조회
            redis_client = await self._get_redis()

            json_data = await redis_client.get(key)
            if json_data:
                context_data = json.loads(json_data)

                # 통합 캐시에 저장
                await integrated_cache.set(
                    key, context_data, ttl=300
                )  # 5분 메모리 캐시

                return context_data

            return None

        except Exception as e:
            logger.error(f"세션 컨텍스트 조회 실패: {str(e)}")
            return None

    async def update_workbook_context(
        self, session_id: str, workbook_context: WorkbookContext
    ) -> bool:
        """
        워크북 컨텍스트 업데이트

        Args:
            session_id: 세션 ID
            workbook_context: 워크북 컨텍스트

        Returns:
            성공 여부
        """
        try:
            # 현재 세션 컨텍스트 가져오기
            context_data = await self.get_session_context(session_id) or {}

            # 워크북 컨텍스트 업데이트
            context_data["workbook_context"] = {
                "file_id": workbook_context.file_id,
                "file_name": workbook_context.file_name,
                "summary": workbook_context.get_summary(),
                "updated_at": workbook_context.updated_at.isoformat(),
            }

            # 저장
            return await self.save_session_context(session_id, context_data)

        except Exception as e:
            logger.error(f"워크북 컨텍스트 업데이트 실패: {str(e)}")
            return False

    async def add_chat_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        채팅 메시지 추가

        Args:
            session_id: 세션 ID
            role: 메시지 역할 (user/assistant/system)
            content: 메시지 내용
            metadata: 추가 메타데이터

        Returns:
            성공 여부
        """
        try:
            # 현재 컨텍스트 가져오기
            context_data = await self.get_session_context(session_id) or {}

            # 채팅 히스토리 초기화
            if "chat_history" not in context_data:
                context_data["chat_history"] = []

            # 메시지 추가
            message = {
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {},
            }

            context_data["chat_history"].append(message)

            # 최대 크기 유지
            if len(context_data["chat_history"]) > self.max_history_per_session:
                context_data["chat_history"] = context_data["chat_history"][
                    -self.max_history_per_session :
                ]

            # 저장
            return await self.save_session_context(session_id, context_data)

        except Exception as e:
            logger.error(f"채팅 메시지 추가 실패: {str(e)}")
            return False

    async def update_selected_cells(
        self, session_id: str, cells: List[Dict[str, Any]]
    ) -> bool:
        """
        선택된 셀 업데이트

        Args:
            session_id: 세션 ID
            cells: 선택된 셀 정보 리스트

        Returns:
            성공 여부
        """
        try:
            # 현재 컨텍스트 가져오기
            context_data = await self.get_session_context(session_id) or {}

            # 선택된 셀 업데이트
            context_data["selected_cells"] = cells
            context_data["selection_timestamp"] = datetime.now().isoformat()

            # 선택 히스토리 추가
            if "selection_history" not in context_data:
                context_data["selection_history"] = []

            context_data["selection_history"].append(
                {"cells": cells, "timestamp": datetime.now().isoformat()}
            )

            # 최대 10개 유지
            if len(context_data["selection_history"]) > 10:
                context_data["selection_history"] = context_data["selection_history"][
                    -10:
                ]

            # 저장
            return await self.save_session_context(session_id, context_data)

        except Exception as e:
            logger.error(f"선택된 셀 업데이트 실패: {str(e)}")
            return False

    async def get_active_sessions(self) -> List[str]:
        """
        활성 세션 목록 조회

        Returns:
            세션 ID 리스트
        """
        try:
            redis_client = await self._get_redis()
            key = f"{self.key_prefix}active_sessions"

            # 만료된 세션 제거
            now = datetime.now().timestamp()
            await redis_client.zremrangebyscore(key, 0, now - self.ttl)

            # 활성 세션 조회
            sessions = await redis_client.zrange(key, 0, -1)
            return list(sessions)

        except Exception as e:
            logger.error(f"활성 세션 조회 실패: {str(e)}")
            return []

    async def cleanup_expired_sessions(self):
        """만료된 세션 정리"""
        try:
            active_sessions = await self.get_active_sessions()
            redis_client = await self._get_redis()

            for session_id in active_sessions:
                key = f"{self.key_prefix}{session_id}"
                exists = await redis_client.exists(key)

                if not exists:
                    # 활성 세션 목록에서 제거
                    await self._remove_from_active_sessions(session_id)

                    # 로컬 캐시에서 제거
                    self._local_cache.pop(session_id, None)

            logger.info("만료된 세션 정리 완료")

        except Exception as e:
            logger.error(f"세션 정리 실패: {str(e)}")

    async def _add_to_active_sessions(self, session_id: str):
        """활성 세션 목록에 추가"""
        try:
            redis_client = await self._get_redis()
            key = f"{self.key_prefix}active_sessions"
            score = datetime.now().timestamp()

            await redis_client.zadd(key, {session_id: score})

        except Exception as e:
            logger.error(f"활성 세션 추가 실패: {str(e)}")

    async def _remove_from_active_sessions(self, session_id: str):
        """활성 세션 목록에서 제거"""
        try:
            redis_client = await self._get_redis()
            key = f"{self.key_prefix}active_sessions"

            await redis_client.zrem(key, session_id)

        except Exception as e:
            logger.error(f"활성 세션 제거 실패: {str(e)}")

    async def close(self):
        """연결 종료"""
        if self._redis:
            await self._redis.close()
            self._redis = None


# 싱글톤 인스턴스
_session_store: Optional[SessionContextStore] = None
_store_lock = asyncio.Lock()


async def get_session_store() -> SessionContextStore:
    """세션 스토어 싱글톤 인스턴스 반환"""
    global _session_store

    if _session_store is None:
        async with _store_lock:
            if _session_store is None:
                _session_store = SessionContextStore()

    return _session_store
