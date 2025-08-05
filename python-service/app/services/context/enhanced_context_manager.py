"""
Enhanced Context Manager
확장된 컨텍스트 매니저 - 워크북 및 세션 통합 관리
"""

from typing import Dict, Any, List, Optional
from app.core.interfaces import ExcelError

# IContextBuilder is not needed here as we're not using it
from app.services.context.workbook_context import (
    WorkbookContext,
    WorkbookContextBuilder,
)
from app.services.context.session_context_store import get_session_store
from app.services.ai_chat.context_manager import ContextManager
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class EnhancedContextManager(ContextManager):
    """확장된 컨텍스트 매니저 - 기존 ContextManager를 상속하여 확장"""

    def __init__(self):
        super().__init__()
        self.workbook_contexts: Dict[str, WorkbookContext] = (
            {}
        )  # session_id -> WorkbookContext
        self._session_store = None

    async def _get_session_store(self):
        """세션 스토어 인스턴스 획득"""
        if self._session_store is None:
            self._session_store = await get_session_store()
        return self._session_store

    async def initialize_workbook_context(
        self,
        session_id: str,
        file_id: str,
        file_name: str,
        analysis_result: Dict[str, Any],
    ) -> WorkbookContext:
        """
        워크북 컨텍스트 초기화

        Args:
            session_id: 세션 ID
            file_id: 파일 ID
            file_name: 파일명
            analysis_result: 분석 결과

        Returns:
            WorkbookContext 인스턴스
        """
        try:
            # WorkbookContext 생성
            workbook_context = WorkbookContextBuilder.build_from_analysis(
                file_id, file_name, analysis_result
            )

            # 메모리에 저장
            self.workbook_contexts[session_id] = workbook_context

            # 세션 스토어에 저장
            session_store = await self._get_session_store()
            await session_store.update_workbook_context(session_id, workbook_context)

            # 기본 Context도 업데이트
            context = self.get_context(session_id) or self.build_context(session_id)
            context.file_info = {
                "file_id": file_id,
                "file_name": file_name,
                "sheet_count": len(workbook_context.sheets),
                "total_cells": workbook_context.total_cells,
                "total_errors": workbook_context.total_errors,
            }

            logger.info(f"워크북 컨텍스트 초기화 완료: {session_id} - {file_name}")
            return workbook_context

        except Exception as e:
            logger.error(f"워크북 컨텍스트 초기화 실패: {str(e)}")
            raise

    async def update_multi_cell_selection(
        self, session_id: str, cells: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        멀티 셀 선택 업데이트

        Args:
            session_id: 세션 ID
            cells: 선택된 셀 정보 리스트

        Returns:
            컨텍스트 정보
        """
        try:
            # 워크북 컨텍스트 확인
            workbook_context = self.workbook_contexts.get(session_id)
            if not workbook_context:
                logger.warning(f"워크북 컨텍스트 없음: {session_id}")
                return {"error": "워크북 컨텍스트가 없습니다"}

            # 선택된 셀 정보 수집
            selected_cells_info = []
            for cell_data in cells:
                sheet_name = cell_data.get("sheetName", "Sheet1")
                address = cell_data.get("address")

                # WorkbookContext에서 셀 정보 조회
                cell_info = workbook_context.get_cell(sheet_name, address)
                if cell_info:
                    selected_cells_info.append(
                        {
                            "address": address,
                            "sheet": sheet_name,
                            "value": cell_info.value,
                            "formula": cell_info.formula,
                            "errors": cell_info.errors,
                            "dependencies": list(cell_info.dependencies),
                            "dependents": list(cell_info.dependents),
                        }
                    )
                else:
                    # 셀 정보가 없으면 기본 정보만 사용
                    selected_cells_info.append(
                        {
                            "address": address,
                            "sheet": sheet_name,
                            "value": cell_data.get("value"),
                            "formula": cell_data.get("formula"),
                        }
                    )

            # 세션 스토어에 업데이트
            session_store = await self._get_session_store()
            await session_store.update_selected_cells(session_id, selected_cells_info)

            # 기본 Context 업데이트
            context = self.get_context(session_id)
            if context:
                context.selected_cell = cells[0].get("address") if cells else None
                self.update_context(
                    context,
                    {
                        "user_action": {
                            "type": "multi_cell_selection",
                            "cell_count": len(cells),
                            "cells": [
                                c.get("address") for c in cells[:5]
                            ],  # 최대 5개만
                        }
                    },
                )

            # 컨텍스트 정보 반환
            return {
                "session_id": session_id,
                "selected_cells": selected_cells_info,
                "cell_count": len(selected_cells_info),
                "workbook_summary": workbook_context.get_summary(),
            }

        except Exception as e:
            logger.error(f"멀티 셀 선택 업데이트 실패: {str(e)}")
            return {"error": str(e)}

    async def get_enhanced_context(self, session_id: str) -> Dict[str, Any]:
        """
        확장된 컨텍스트 정보 조회

        Args:
            session_id: 세션 ID

        Returns:
            확장된 컨텍스트 정보
        """
        try:
            # 기본 컨텍스트
            base_context = self.get_context(session_id)
            if not base_context:
                return {"error": "컨텍스트가 없습니다"}

            # 워크북 컨텍스트
            workbook_context = self.workbook_contexts.get(session_id)

            # 세션 스토어에서 추가 정보 조회
            session_store = await self._get_session_store()
            session_data = await session_store.get_session_context(session_id) or {}

            # 통합 컨텍스트 구성
            enhanced_context = {
                "session_id": session_id,
                "base_context": self.get_relevant_context(base_context),
                "workbook_context": (
                    workbook_context.get_summary() if workbook_context else None
                ),
                "selected_cells": session_data.get("selected_cells", []),
                "chat_history": session_data.get("chat_history", [])[-10:],  # 최근 10개
                "selection_history": session_data.get("selection_history", [])[
                    -5:
                ],  # 최근 5개
                "last_updated": session_data.get("last_updated"),
            }

            return enhanced_context

        except Exception as e:
            logger.error(f"확장 컨텍스트 조회 실패: {str(e)}")
            return {"error": str(e)}

    async def add_ai_response(
        self, session_id: str, response: str, metadata: Optional[Dict[str, Any]] = None
    ):
        """
        AI 응답 추가

        Args:
            session_id: 세션 ID
            response: AI 응답
            metadata: 추가 메타데이터
        """
        try:
            # 세션 스토어에 저장
            session_store = await self._get_session_store()
            await session_store.add_chat_message(
                session_id, "assistant", response, metadata
            )

            # 기본 컨텍스트 업데이트
            context = self.get_context(session_id)
            if context:
                self.update_context(
                    context,
                    {
                        "user_action": {
                            "type": "ai_response",
                            "timestamp": datetime.now().isoformat(),
                        }
                    },
                )

        except Exception as e:
            logger.error(f"AI 응답 추가 실패: {str(e)}")

    async def update_from_detector_result(
        self, session_id: str, detector_result: Dict[str, Any]
    ):
        """
        IntegratedErrorDetector 결과로 컨텍스트 업데이트

        Args:
            session_id: 세션 ID
            detector_result: 감지 결과
        """
        try:
            # 워크북 컨텍스트 업데이트
            workbook_context = self.workbook_contexts.get(session_id)
            if workbook_context:
                # 오류 정보 업데이트
                if "errors" in detector_result:
                    for error_dict in detector_result["errors"]:
                        if isinstance(error_dict, dict):
                            sheet_name = error_dict.get("sheet", "Sheet1")
                            cell_address = error_dict.get("cell", "")

                            # 전역 오류 추가
                            workbook_context.global_errors.append(error_dict)

                            # 시트별 오류 추가
                            if sheet_name in workbook_context.sheets:
                                sheet_context = workbook_context.sheets[sheet_name]
                                if cell_address:
                                    # 셀 특정 오류
                                    if cell_address in sheet_context.cells:
                                        sheet_context.cells[cell_address].errors.append(
                                            error_dict
                                        )

                # 요약 정보 업데이트
                if "summary" in detector_result:
                    workbook_context.analysis_summary.update(detector_result["summary"])

                # 패턴 분석 정보 추가
                if "pattern_analysis" in detector_result:
                    workbook_context.analysis_summary["patterns"] = detector_result[
                        "pattern_analysis"
                    ]

                # 세션 스토어에 저장
                session_store = await self._get_session_store()
                await session_store.update_workbook_context(
                    session_id, workbook_context
                )

                logger.info(
                    f"워크북 컨텍스트 업데이트 완료: {len(detector_result.get('errors', []))} 오류"
                )

            # 기본 컨텍스트 업데이트
            context = self.get_context(session_id)
            if context and "errors" in detector_result:
                context.detected_errors = [
                    ExcelError(**error) if isinstance(error, dict) else error
                    for error in detector_result["errors"]
                ]
                # 컨텍스트에 감지 결과 요약 추가
                self.update_context(
                    context,
                    {
                        "error_detection": {
                            "total_errors": len(detector_result["errors"]),
                            "summary": detector_result.get("summary", {}),
                            "timestamp": datetime.now().isoformat(),
                        }
                    },
                )

        except Exception as e:
            logger.error(f"감지 결과 업데이트 실패: {str(e)}", exc_info=True)

    async def cleanup_old_sessions(self):
        """오래된 세션 정리"""
        try:
            # 세션 스토어 정리
            session_store = await self._get_session_store()
            await session_store.cleanup_expired_sessions()

            # 메모리에서 제거
            active_sessions = await session_store.get_active_sessions()
            sessions_to_remove = []

            for session_id in self.active_contexts.keys():
                if session_id not in active_sessions:
                    sessions_to_remove.append(session_id)

            for session_id in sessions_to_remove:
                self.remove_context(session_id)
                self.workbook_contexts.pop(session_id, None)

            logger.info(f"정리된 세션 수: {len(sessions_to_remove)}")

        except Exception as e:
            logger.error(f"세션 정리 실패: {str(e)}")


# 싱글톤 인스턴스
_enhanced_context_manager: Optional[EnhancedContextManager] = None


def get_enhanced_context_manager() -> EnhancedContextManager:
    """확장된 컨텍스트 매니저 싱글톤 인스턴스 반환"""
    global _enhanced_context_manager

    if _enhanced_context_manager is None:
        _enhanced_context_manager = EnhancedContextManager()

    return _enhanced_context_manager
