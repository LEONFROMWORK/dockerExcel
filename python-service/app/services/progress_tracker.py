"""
사용자 파일 처리 진행률 추적 서비스
User File Processing Progress Tracker
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ProcessingStage(Enum):
    """파일 처리 단계"""

    UPLOADED = "uploaded"
    ANALYZING = "analyzing"
    DETECTING_ERRORS = "detecting_errors"
    FIXING_FORMULAS = "fixing_formulas"
    CLEANING_DATA = "cleaning_data"
    OPTIMIZING_STRUCTURE = "optimizing_structure"
    APPLYING_AI_FIXES = "applying_ai_fixes"
    GENERATING_INSIGHTS = "generating_insights"
    SAVING_FILE = "saving_file"
    COMPLETED = "completed"
    FAILED = "failed"


class ProgressTracker:
    """파일 처리 진행률 추적 관리자"""

    def __init__(self):
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
        self.completed_tasks: Dict[str, Dict[str, Any]] = {}
        self.websocket_connections: Dict[str, Any] = {}

    def create_task(
        self, task_id: str, filename: str, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """새로운 처리 작업 생성"""

        task_info = {
            "task_id": task_id,
            "filename": filename,
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "current_stage": ProcessingStage.UPLOADED.value,
            "progress_percentage": 0,
            "stages_completed": [],
            "current_operation": "파일 업로드 완료",
            "estimated_total_time": None,
            "elapsed_time": 0,
            "remaining_time": None,
            "error_message": None,
            "metadata": {
                "file_size": None,
                "total_stages": 9,
                "stages_info": self._get_stages_info(),
            },
        }

        self.active_tasks[task_id] = task_info
        logger.info(f"새 작업 생성: {task_id} - {filename}")

        return task_info

    def update_progress(
        self,
        task_id: str,
        stage: ProcessingStage,
        operation: str = None,
        progress_detail: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """진행률 업데이트"""

        if task_id not in self.active_tasks:
            logger.warning(f"존재하지 않는 작업 ID: {task_id}")
            return None

        task = self.active_tasks[task_id]

        # 시간 계산
        created_time = datetime.fromisoformat(task["created_at"])
        current_time = datetime.now()
        elapsed_seconds = (current_time - created_time).total_seconds()

        # 단계별 진행률 계산
        stage_progress = self._calculate_stage_progress(stage)

        # 예상 소요 시간 계산
        if stage_progress > 0:
            estimated_total = elapsed_seconds / (stage_progress / 100)
            remaining_time = max(0, estimated_total - elapsed_seconds)
        else:
            estimated_total = None
            remaining_time = None

        # 작업 정보 업데이트
        task.update(
            {
                "current_stage": stage.value,
                "progress_percentage": stage_progress,
                "current_operation": operation or self._get_stage_description(stage),
                "elapsed_time": elapsed_seconds,
                "estimated_total_time": estimated_total,
                "remaining_time": remaining_time,
                "updated_at": current_time.isoformat(),
            }
        )

        # 단계 완료 기록
        if stage.value not in task["stages_completed"]:
            task["stages_completed"].append(stage.value)

        # 세부 진행 정보 추가
        if progress_detail:
            task["current_detail"] = progress_detail

        logger.info(f"진행률 업데이트: {task_id} - {stage.value} ({stage_progress}%)")

        return task

    def complete_task(
        self, task_id: str, result: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """작업 완료 처리"""

        if task_id not in self.active_tasks:
            return None

        task = self.active_tasks[task_id]

        # 완료 정보 업데이트
        task.update(
            {
                "current_stage": ProcessingStage.COMPLETED.value,
                "progress_percentage": 100,
                "current_operation": "처리 완료",
                "completed_at": datetime.now().isoformat(),
                "result": result,
            }
        )

        # 완료된 작업으로 이동
        self.completed_tasks[task_id] = task
        del self.active_tasks[task_id]

        logger.info(f"작업 완료: {task_id}")

        return task

    def fail_task(
        self, task_id: str, error_message: str, error_detail: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """작업 실패 처리"""

        if task_id not in self.active_tasks:
            return None

        task = self.active_tasks[task_id]

        # 실패 정보 업데이트
        task.update(
            {
                "current_stage": ProcessingStage.FAILED.value,
                "current_operation": "처리 실패",
                "error_message": error_message,
                "error_detail": error_detail,
                "failed_at": datetime.now().isoformat(),
            }
        )

        # 완료된 작업으로 이동 (실패도 완료로 간주)
        self.completed_tasks[task_id] = task
        del self.active_tasks[task_id]

        logger.error(f"작업 실패: {task_id} - {error_message}")

        return task

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """작업 상태 조회"""

        # 활성 작업에서 먼저 찾기
        if task_id in self.active_tasks:
            return self.active_tasks[task_id]

        # 완료된 작업에서 찾기
        if task_id in self.completed_tasks:
            return self.completed_tasks[task_id]

        return None

    def get_user_tasks(self, user_id: str) -> List[Dict[str, Any]]:
        """사용자의 모든 작업 조회"""

        user_tasks = []

        # 활성 작업
        for task in self.active_tasks.values():
            if task.get("user_id") == user_id:
                user_tasks.append(task)

        # 완료된 작업 (최근 10개만)
        completed_user_tasks = [
            task
            for task in self.completed_tasks.values()
            if task.get("user_id") == user_id
        ]

        # 완료 시간 기준으로 정렬하여 최신 10개만
        completed_user_tasks.sort(
            key=lambda x: x.get("completed_at", x.get("failed_at", "")), reverse=True
        )

        user_tasks.extend(completed_user_tasks[:10])

        return user_tasks

    def cleanup_old_tasks(self, hours: int = 24):
        """오래된 완료 작업 정리"""

        cutoff_time = datetime.now().timestamp() - (hours * 3600)
        tasks_to_remove = []

        for task_id, task in self.completed_tasks.items():
            completed_time = task.get("completed_at") or task.get("failed_at")
            if completed_time:
                task_time = datetime.fromisoformat(completed_time).timestamp()
                if task_time < cutoff_time:
                    tasks_to_remove.append(task_id)

        for task_id in tasks_to_remove:
            del self.completed_tasks[task_id]

        logger.info(f"오래된 작업 {len(tasks_to_remove)}개 정리 완료")

    def _calculate_stage_progress(self, stage: ProcessingStage) -> int:
        """단계별 진행률 계산"""

        stage_progress_map = {
            ProcessingStage.UPLOADED: 5,
            ProcessingStage.ANALYZING: 15,
            ProcessingStage.DETECTING_ERRORS: 25,
            ProcessingStage.FIXING_FORMULAS: 40,
            ProcessingStage.CLEANING_DATA: 55,
            ProcessingStage.OPTIMIZING_STRUCTURE: 70,
            ProcessingStage.APPLYING_AI_FIXES: 85,
            ProcessingStage.GENERATING_INSIGHTS: 92,
            ProcessingStage.SAVING_FILE: 98,
            ProcessingStage.COMPLETED: 100,
            ProcessingStage.FAILED: 0,
        }

        return stage_progress_map.get(stage, 0)

    def _get_stage_description(self, stage: ProcessingStage) -> str:
        """단계별 설명 문구"""

        descriptions = {
            ProcessingStage.UPLOADED: "파일 업로드 완료",
            ProcessingStage.ANALYZING: "파일 구조 분석 중...",
            ProcessingStage.DETECTING_ERRORS: "오류 감지 중...",
            ProcessingStage.FIXING_FORMULAS: "수식 오류 수정 중...",
            ProcessingStage.CLEANING_DATA: "데이터 정리 중...",
            ProcessingStage.OPTIMIZING_STRUCTURE: "구조 최적화 중...",
            ProcessingStage.APPLYING_AI_FIXES: "AI 기반 지능형 수정 적용 중...",
            ProcessingStage.GENERATING_INSIGHTS: "데이터 인사이트 생성 중...",
            ProcessingStage.SAVING_FILE: "수정된 파일 저장 중...",
            ProcessingStage.COMPLETED: "처리 완료",
            ProcessingStage.FAILED: "처리 실패",
        }

        return descriptions.get(stage, "처리 중...")

    def _get_stages_info(self) -> Dict[str, str]:
        """모든 단계 정보"""

        return {
            ProcessingStage.UPLOADED.value: "파일 업로드",
            ProcessingStage.ANALYZING.value: "파일 분석",
            ProcessingStage.DETECTING_ERRORS.value: "오류 감지",
            ProcessingStage.FIXING_FORMULAS.value: "수식 수정",
            ProcessingStage.CLEANING_DATA.value: "데이터 정리",
            ProcessingStage.OPTIMIZING_STRUCTURE.value: "구조 최적화",
            ProcessingStage.APPLYING_AI_FIXES.value: "AI 수정",
            ProcessingStage.GENERATING_INSIGHTS.value: "인사이트 생성",
            ProcessingStage.SAVING_FILE.value: "파일 저장",
        }


# 전역 진행률 추적기 인스턴스
progress_tracker = ProgressTracker()


class ProgressContextManager:
    """진행률 추적을 위한 컨텍스트 매니저"""

    def __init__(self, task_id: str, stage: ProcessingStage, operation: str = None):
        self.task_id = task_id
        self.stage = stage
        self.operation = operation

    def __enter__(self):
        progress_tracker.update_progress(self.task_id, self.stage, self.operation)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # 예외 발생 시 실패 처리
            error_msg = f"{self.stage.value} 단계에서 오류 발생: {str(exc_val)}"
            progress_tracker.fail_task(self.task_id, error_msg)
        return False  # 예외 전파


def track_progress(task_id: str, stage: ProcessingStage, operation: str = None):
    """진행률 추적 데코레이터"""

    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            progress_tracker.update_progress(task_id, stage, operation)
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                error_msg = f"{stage.value} 단계 실패: {str(e)}"
                progress_tracker.fail_task(task_id, error_msg)
                raise

        def sync_wrapper(*args, **kwargs):
            progress_tracker.update_progress(task_id, stage, operation)
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error_msg = f"{stage.value} 단계 실패: {str(e)}"
                progress_tracker.fail_task(task_id, error_msg)
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator
