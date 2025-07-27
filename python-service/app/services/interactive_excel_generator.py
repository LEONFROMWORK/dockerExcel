"""
대화형 Excel 생성 시스템
Interactive Excel Generation with User Feedback Loop
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
from enum import Enum

from .ai_excel_generator import ai_excel_generator
from .openai_service import openai_service

logger = logging.getLogger(__name__)


class GenerationStage(Enum):
    """생성 단계"""
    INTENT_CLARIFICATION = "intent_clarification"
    STRUCTURE_DESIGN = "structure_design"
    DATA_REQUIREMENTS = "data_requirements"
    PREVIEW_GENERATION = "preview_generation"
    REFINEMENT = "refinement"
    FINAL_GENERATION = "final_generation"


class InteractiveExcelGenerator:
    """대화형 Excel 생성기"""
    
    def __init__(self):
        self.sessions = {}  # 사용자 세션 관리
        self.conversation_history = {}  # 대화 기록
    
    async def start_generation_session(
        self,
        user_id: str,
        initial_request: str,
        language: str = "ko"
    ) -> Dict[str, Any]:
        """생성 세션 시작"""
        
        session_id = f"{user_id}_{datetime.now().timestamp()}"
        
        self.sessions[session_id] = {
            "user_id": user_id,
            "stage": GenerationStage.INTENT_CLARIFICATION,
            "request": initial_request,
            "language": language,
            "context": {},
            "created_at": datetime.now()
        }
        
        self.conversation_history[session_id] = []
        
        # 초기 의도 파악 및 질문 생성
        clarification_needed = await self._analyze_and_clarify(session_id, initial_request)
        
        return {
            "session_id": session_id,
            "stage": GenerationStage.INTENT_CLARIFICATION.value,
            "needs_clarification": clarification_needed["needs_clarification"],
            "questions": clarification_needed.get("questions", []),
            "initial_understanding": clarification_needed.get("understanding", {})
        }
    
    async def process_user_response(
        self,
        session_id: str,
        user_response: str
    ) -> Dict[str, Any]:
        """사용자 응답 처리"""
        
        if session_id not in self.sessions:
            return {"error": "Invalid session ID"}
        
        session = self.sessions[session_id]
        current_stage = session["stage"]
        
        # 대화 기록 추가
        self.conversation_history[session_id].append({
            "role": "user",
            "content": user_response,
            "timestamp": datetime.now()
        })
        
        # 단계별 처리
        if current_stage == GenerationStage.INTENT_CLARIFICATION:
            return await self._process_intent_clarification(session_id, user_response)
        
        elif current_stage == GenerationStage.STRUCTURE_DESIGN:
            return await self._process_structure_feedback(session_id, user_response)
        
        elif current_stage == GenerationStage.DATA_REQUIREMENTS:
            return await self._process_data_requirements(session_id, user_response)
        
        elif current_stage == GenerationStage.PREVIEW_GENERATION:
            return await self._process_preview_feedback(session_id, user_response)
        
        elif current_stage == GenerationStage.REFINEMENT:
            return await self._process_refinement_request(session_id, user_response)
        
        else:
            return await self._finalize_generation(session_id)
    
    async def _analyze_and_clarify(
        self,
        session_id: str,
        request: str
    ) -> Dict[str, Any]:
        """요청 분석 및 명확화"""
        
        language = self.sessions[session_id]["language"]
        
        system_prompt = f"""You are an Excel assistant fluent in {language}.
        Analyze the user's request and determine:
        
        1. Is the request clear enough to proceed?
        2. What clarifying questions would help create a better Excel file?
        3. What is your current understanding of their needs?
        
        Generate 2-3 clarifying questions if needed.
        Return JSON with: needs_clarification (bool), questions (list), understanding (dict)"""
        
        user_prompt = f"User request: {request}"
        
        response = await openai_service.chat_completion([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])
        
        try:
            result = json.loads(response)
        except:
            result = {
                "needs_clarification": True,
                "questions": ["어떤 종류의 데이터를 다루시나요?", "Excel 파일의 주요 용도는 무엇인가요?"],
                "understanding": {"request": request}
            }
        
        # 대화 기록
        self.conversation_history[session_id].append({
            "role": "assistant",
            "content": result,
            "timestamp": datetime.now()
        })
        
        return result
    
    async def _process_intent_clarification(
        self,
        session_id: str,
        user_response: str
    ) -> Dict[str, Any]:
        """의도 명확화 처리"""
        
        session = self.sessions[session_id]
        
        # 컨텍스트 업데이트
        session["context"]["clarification_response"] = user_response
        
        # AI로 응답 분석
        enhanced_understanding = await self._enhance_understanding(session_id)
        session["context"]["understanding"] = enhanced_understanding
        
        # 다음 단계로 이동: 구조 설계
        session["stage"] = GenerationStage.STRUCTURE_DESIGN
        
        # 초기 구조 제안 생성
        structure_proposal = await self._propose_structure(session_id)
        
        return {
            "stage": GenerationStage.STRUCTURE_DESIGN.value,
            "structure_proposal": structure_proposal,
            "message": "제안된 Excel 구조입니다. 수정이 필요한 부분이 있나요?"
        }
    
    async def _enhance_understanding(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """이해도 향상"""
        
        session = self.sessions[session_id]
        history = self.conversation_history[session_id]
        
        system_prompt = f"""Based on the conversation history, create a comprehensive understanding
        of what the user wants in their Excel file. Include:
        
        1. Main purpose
        2. Data types and categories
        3. Required features (formulas, charts, etc.)
        4. Specific requirements mentioned
        
        Return as structured JSON."""
        
        conversation = "\n".join([
            f"{item['role']}: {item['content']}" 
            for item in history
        ])
        
        response = await openai_service.chat_completion([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": conversation}
        ])
        
        try:
            return json.loads(response)
        except:
            return {"purpose": session["request"]}
    
    async def _propose_structure(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """Excel 구조 제안"""
        
        session = self.sessions[session_id]
        understanding = session["context"].get("understanding", {})
        
        # AI 기반 구조 설계
        structure = await ai_excel_generator._design_excel_structure(
            understanding,
            session["language"]
        )
        
        # 시각적 표현을 위한 간소화
        simplified_structure = {
            "sheets": [
                {
                    "name": sheet.get("name", f"Sheet{i+1}"),
                    "description": sheet.get("description", ""),
                    "columns": [
                        {
                            "name": col.get("name"),
                            "type": col.get("type", "text"),
                            "description": col.get("description", "")
                        }
                        for col in sheet.get("columns", [])[:5]  # 처음 5개만 표시
                    ],
                    "features": sheet.get("features", [])
                }
                for i, sheet in enumerate(structure.get("sheets", []))
            ],
            "total_sheets": len(structure.get("sheets", [])),
            "includes_charts": any(sheet.get("charts") for sheet in structure.get("sheets", [])),
            "includes_formulas": any(
                col.get("formula") 
                for sheet in structure.get("sheets", []) 
                for col in sheet.get("columns", [])
            )
        }
        
        session["context"]["proposed_structure"] = structure
        
        return simplified_structure
    
    async def _process_structure_feedback(
        self,
        session_id: str,
        feedback: str
    ) -> Dict[str, Any]:
        """구조 피드백 처리"""
        
        session = self.sessions[session_id]
        
        # 피드백 분석
        if feedback.lower() in ["ok", "좋아", "네", "yes", "확인"]:
            # 다음 단계로
            session["stage"] = GenerationStage.DATA_REQUIREMENTS
            return await self._request_data_requirements(session_id)
        else:
            # 구조 수정
            modified_structure = await self._modify_structure(session_id, feedback)
            return {
                "stage": GenerationStage.STRUCTURE_DESIGN.value,
                "structure_proposal": modified_structure,
                "message": "구조를 수정했습니다. 이제 괜찮으신가요?"
            }
    
    async def _modify_structure(
        self,
        session_id: str,
        feedback: str
    ) -> Dict[str, Any]:
        """구조 수정"""
        
        session = self.sessions[session_id]
        current_structure = session["context"]["proposed_structure"]
        
        system_prompt = """Modify the Excel structure based on user feedback.
        Keep the changes focused and relevant.
        Return the modified structure in the same format."""
        
        user_prompt = f"""Current structure: {json.dumps(current_structure)}
        User feedback: {feedback}
        
        Modify the structure accordingly."""
        
        response = await openai_service.chat_completion([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])
        
        try:
            modified = json.loads(response)
            session["context"]["proposed_structure"] = modified
            return modified
        except:
            return current_structure
    
    async def _request_data_requirements(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """데이터 요구사항 요청"""
        
        session = self.sessions[session_id]
        structure = session["context"]["proposed_structure"]
        
        questions = []
        
        # 구조에 따른 질문 생성
        for sheet in structure.get("sheets", []):
            if any(col.get("type") == "number" for col in sheet.get("columns", [])):
                questions.append("숫자 데이터의 범위는 어느 정도인가요? (예: 0-100, 1000-10000)")
            
            if sheet.get("includes_dates"):
                questions.append("날짜 범위는 어떻게 설정할까요? (예: 최근 1년, 2024년)")
        
        if not questions:
            questions = ["샘플 데이터를 자동으로 생성해도 될까요?"]
        
        return {
            "stage": GenerationStage.DATA_REQUIREMENTS.value,
            "questions": questions[:2],  # 최대 2개 질문
            "message": "데이터에 대한 몇 가지 확인이 필요합니다."
        }
    
    async def _process_data_requirements(
        self,
        session_id: str,
        response: str
    ) -> Dict[str, Any]:
        """데이터 요구사항 처리"""
        
        session = self.sessions[session_id]
        session["context"]["data_requirements"] = response
        
        # 미리보기 생성
        session["stage"] = GenerationStage.PREVIEW_GENERATION
        
        preview = await self._generate_preview(session_id)
        
        return {
            "stage": GenerationStage.PREVIEW_GENERATION.value,
            "preview": preview,
            "message": "Excel 파일 미리보기입니다. 수정이 필요하신가요?"
        }
    
    async def _generate_preview(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """미리보기 생성"""
        
        session = self.sessions[session_id]
        
        # 간단한 미리보기 데이터 생성
        structure = session["context"]["proposed_structure"]
        
        preview = {
            "sheets": []
        }
        
        for sheet in structure.get("sheets", [])[:2]:  # 처음 2개 시트만
            sheet_preview = {
                "name": sheet["name"],
                "headers": [col["name"] for col in sheet.get("columns", [])[:5]],
                "sample_rows": [
                    [f"데이터{i}_{j}" for j in range(min(5, len(sheet.get("columns", []))))]
                    for i in range(3)
                ],
                "total_rows": "10 rows (샘플)",
                "charts": len(sheet.get("charts", [])),
                "formulas": sum(1 for col in sheet.get("columns", []) if col.get("formula"))
            }
            preview["sheets"].append(sheet_preview)
        
        return preview
    
    async def _process_preview_feedback(
        self,
        session_id: str,
        feedback: str
    ) -> Dict[str, Any]:
        """미리보기 피드백 처리"""
        
        session = self.sessions[session_id]
        
        if feedback.lower() in ["ok", "좋아", "네", "yes", "확인", "생성"]:
            # 최종 생성
            return await self._finalize_generation(session_id)
        else:
            # 수정 요청
            session["stage"] = GenerationStage.REFINEMENT
            return {
                "stage": GenerationStage.REFINEMENT.value,
                "message": "어떤 부분을 수정하고 싶으신가요?",
                "current_preview": await self._generate_preview(session_id)
            }
    
    async def _process_refinement_request(
        self,
        session_id: str,
        refinement: str
    ) -> Dict[str, Any]:
        """수정 요청 처리"""
        
        session = self.sessions[session_id]
        
        # 수정 사항 적용
        session["context"]["refinements"] = session["context"].get("refinements", [])
        session["context"]["refinements"].append(refinement)
        
        # 구조 업데이트
        await self._apply_refinements(session_id, refinement)
        
        # 새로운 미리보기 생성
        new_preview = await self._generate_preview(session_id)
        
        return {
            "stage": GenerationStage.PREVIEW_GENERATION.value,
            "preview": new_preview,
            "message": "수정사항을 반영했습니다. 이제 괜찮으신가요?"
        }
    
    async def _apply_refinements(
        self,
        session_id: str,
        refinement: str
    ):
        """수정사항 적용"""
        
        session = self.sessions[session_id]
        structure = session["context"]["proposed_structure"]
        
        # AI를 사용한 수정사항 해석 및 적용
        system_prompt = """Apply the user's refinement request to the Excel structure.
        Make minimal necessary changes.
        Return the updated structure."""
        
        user_prompt = f"""Current structure: {json.dumps(structure)}
        Refinement request: {refinement}
        
        Apply the changes."""
        
        response = await openai_service.chat_completion([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])
        
        try:
            updated_structure = json.loads(response)
            session["context"]["proposed_structure"] = updated_structure
        except:
            pass  # 구조 유지
    
    async def _finalize_generation(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """최종 생성"""
        
        session = self.sessions[session_id]
        
        try:
            # 전체 컨텍스트로 Excel 생성
            result = await ai_excel_generator.generate_from_natural_language(
                user_request=session["request"],
                context=session["context"],
                language=session["language"]
            )
            
            # 세션 정리
            session["stage"] = GenerationStage.FINAL_GENERATION
            session["completed_at"] = datetime.now()
            
            return {
                "stage": GenerationStage.FINAL_GENERATION.value,
                "status": "success",
                "file_path": result["file_path"],
                "features": result.get("features_applied", []),
                "message": "Excel 파일이 성공적으로 생성되었습니다!",
                "session_complete": True
            }
            
        except Exception as e:
            logger.error(f"최종 생성 실패: {str(e)}")
            return {
                "stage": GenerationStage.FINAL_GENERATION.value,
                "status": "error",
                "error": str(e),
                "message": "생성 중 오류가 발생했습니다. 다시 시도해주세요."
            }
    
    async def get_session_status(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """세션 상태 확인"""
        
        if session_id not in self.sessions:
            return {"error": "Session not found"}
        
        session = self.sessions[session_id]
        
        return {
            "session_id": session_id,
            "stage": session["stage"].value,
            "created_at": session["created_at"].isoformat(),
            "conversation_length": len(self.conversation_history.get(session_id, [])),
            "context_keys": list(session["context"].keys())
        }
    
    def cleanup_old_sessions(self, hours: int = 24):
        """오래된 세션 정리"""
        
        cutoff_time = datetime.now().timestamp() - (hours * 3600)
        
        sessions_to_remove = []
        for session_id, session in self.sessions.items():
            if session["created_at"].timestamp() < cutoff_time:
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            del self.sessions[session_id]
            if session_id in self.conversation_history:
                del self.conversation_history[session_id]
        
        logger.info(f"Cleaned up {len(sessions_to_remove)} old sessions")


# 전역 대화형 생성기 인스턴스
interactive_excel_generator = InteractiveExcelGenerator()