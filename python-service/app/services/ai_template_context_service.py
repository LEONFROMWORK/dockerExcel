"""
AI Template Context Service
AI가 템플릿을 더 잘 이해하고 활용할 수 있도록 돕는 컨텍스트 서비스
"""

import logging
import json
from typing import Dict, List, Any, Optional

from ..models.template_metadata import (
    EnhancedTemplateMetadata,
    FieldDefinition,
    WorkflowStep,
)
from .openai_service import openai_service

logger = logging.getLogger(__name__)


class AITemplateContextService:
    """AI 템플릿 컨텍스트 서비스"""

    def __init__(self):
        self.context_cache = {}

    async def generate_ai_context(
        self, metadata: EnhancedTemplateMetadata
    ) -> Dict[str, Any]:
        """
        템플릿 메타데이터를 기반으로 AI가 사용할 컨텍스트 정보 생성
        """
        context = {
            "template_understanding": await self._generate_template_understanding(
                metadata
            ),
            "field_guidance": await self._generate_field_guidance(metadata),
            "validation_prompts": await self._generate_validation_prompts(metadata),
            "user_assistance": await self._generate_user_assistance_prompts(metadata),
            "data_insights": await self._generate_data_insight_prompts(metadata),
            "error_recovery": await self._generate_error_recovery_prompts(metadata),
        }

        return context

    async def _generate_template_understanding(
        self, metadata: EnhancedTemplateMetadata
    ) -> Dict[str, str]:
        """템플릿 이해를 위한 컨텍스트 생성"""

        understanding_prompt = f"""
        템플릿 정보:
        - 이름: {metadata.name}
        - 목적: {metadata.purpose}
        - 카테고리: {metadata.category.value}
        - 대상 사용자: {', '.join(metadata.target_audience)}
        - 주요 사용 사례: {', '.join(metadata.business_use_cases)}

        이 템플릿의 핵심 비즈니스 로직과 목적을 한 문장으로 요약해주세요.
        """

        try:
            summary = await openai_service.chat_completion(
                messages=[{"role": "user", "content": understanding_prompt}],
                max_tokens=500,
            )

            return {
                "business_purpose": summary,
                "key_concepts": metadata.context_keywords,
                "domain_expertise": f"{metadata.category.value} domain",
                "complexity_level": metadata.complexity.value,
                "user_context": f"Designed for {', '.join(metadata.target_audience)}",
            }
        except Exception as e:
            logger.error(f"Failed to generate template understanding: {e}")
            return {
                "business_purpose": metadata.purpose,
                "key_concepts": metadata.context_keywords,
                "domain_expertise": f"{metadata.category.value} domain",
                "complexity_level": metadata.complexity.value,
            }

    async def _generate_field_guidance(
        self, metadata: EnhancedTemplateMetadata
    ) -> Dict[str, Dict[str, Any]]:
        """각 필드에 대한 AI 가이던스 생성"""
        field_guidance = {}

        for section in metadata.sections:
            for field in section.fields:
                guidance = {
                    "description": field.description,
                    "data_type": field.data_type,
                    "validation_rules": field.validation_rules,
                    "examples": field.example_values,
                    "business_logic": field.business_logic,
                    "ai_prompt": await self._generate_field_ai_prompt(
                        field, section, metadata
                    ),
                }

                field_guidance[f"{section.name}.{field.name}"] = guidance

        return field_guidance

    async def _generate_field_ai_prompt(
        self, field: FieldDefinition, section, metadata: EnhancedTemplateMetadata
    ) -> str:
        """개별 필드에 대한 AI 프롬프트 생성"""

        prompt = f"""
        당신은 {metadata.category.value} 전문가입니다.

        필드명: {field.name}
        섹션: {section.name}
        템플릿: {metadata.name}

        필드 설명: {field.description}
        데이터 타입: {field.data_type}
        비즈니스 로직: {field.business_logic or '없음'}

        사용자가 이 필드에 데이터를 입력할 때:
        1. 어떤 점을 주의해야 하는지
        2. 일반적인 실수는 무엇인지
        3. 올바른 값의 예시는 무엇인지

        간단명료하게 안내해주세요.
        """

        return prompt

    async def _generate_validation_prompts(
        self, metadata: EnhancedTemplateMetadata
    ) -> Dict[str, str]:
        """데이터 검증을 위한 프롬프트 생성"""

        return {
            "data_consistency": f"""
            {metadata.name} 템플릿의 데이터 일관성을 검증해주세요.

            다음 사항을 확인해주세요:
            1. 수입/지출 항목의 합계가 올바른지
            2. 계산 공식이 정확히 적용되었는지
            3. 월별 데이터 간 비정상적인 변동이 있는지
            4. 필수 필드가 모두 입력되었는지

            문제가 발견되면 구체적인 수정 방안을 제시해주세요.
            """,
            "business_logic": f"""
            {metadata.category.value} 관점에서 이 데이터가 비즈니스 로직에 맞는지 검증해주세요.

            주요 검증 포인트:
            - {', '.join(metadata.key_metrics)}

            {metadata.business_use_cases[0] if metadata.business_use_cases else '일반적인 업무'} 맥락에서
            데이터가 합리적인지 평가해주세요.
            """,
            "trend_analysis": f"""
            입력된 데이터의 트렌드를 분석하고 다음을 확인해주세요:

            1. 계절성 패턴이 있는지
            2. 예상치 못한 급증/급감이 있는지
            3. 향후 예측에 영향을 줄 수 있는 패턴이 있는지

            {metadata.target_audience[0] if metadata.target_audience else '사용자'}에게
            유용한 인사이트를 제공해주세요.
            """,
        }

    async def _generate_user_assistance_prompts(
        self, metadata: EnhancedTemplateMetadata
    ) -> Dict[str, str]:
        """사용자 지원을 위한 프롬프트 생성"""

        return {
            "getting_started": f"""
            {metadata.name} 템플릿 사용을 시작하는 사용자를 도와주세요.

            사용자 프로필: {', '.join(metadata.target_audience)}
            예상 완료 시간: {metadata.estimated_completion_time}

            다음 순서로 안내해주세요:
            1. 준비해야 할 데이터: {', '.join(metadata.prerequisites)}
            2. 작성 순서와 주의사항
            3. 가장 중요한 3가지 포인트

            초보자도 이해할 수 있게 설명해주세요.
            """,
            "step_by_step": f"""
            현재 사용자가 진행 중인 단계를 파악하고 다음 단계를 안내해주세요.

            전체 워크플로우:
            {self._format_workflow_steps(metadata.workflow_steps)}

            사용자의 현재 상황을 분석하고 맞춤형 가이드를 제공해주세요.
            """,
            "troubleshooting": f"""
            사용자가 {metadata.name} 사용 중 문제를 겪고 있습니다.

            일반적인 문제들:
            {self._format_common_errors(metadata.common_errors)}

            문제 상황을 파악하고 단계별 해결 방안을 제시해주세요.
            """,
        }

    async def _generate_data_insight_prompts(
        self, metadata: EnhancedTemplateMetadata
    ) -> Dict[str, str]:
        """데이터 인사이트 생성을 위한 프롬프트"""

        return {
            "key_metrics_analysis": f"""
            {metadata.name}의 핵심 지표들을 분석해주세요:

            주요 지표: {', '.join(metadata.key_metrics)}
            계산 방법: {json.dumps(metadata.calculation_methods, ensure_ascii=False)}

            각 지표의 의미와 비즈니스에 미치는 영향을 설명하고,
            개선을 위한 실행 가능한 제안을 해주세요.
            """,
            "comparative_analysis": f"""
            업계 표준이나 일반적인 벤치마크와 비교하여 분석해주세요.

            비즈니스 카테고리: {metadata.category.value}
            주요 사용 사례: {metadata.business_use_cases[0] if metadata.business_use_cases else '일반'}

            현재 수치가 양호한지, 개선이 필요한지 평가해주세요.
            """,
            "future_planning": f"""
            현재 데이터를 바탕으로 향후 계획 수립을 도와주세요.

            목적: {metadata.purpose}
            타겟 사용자: {', '.join(metadata.target_audience)}

            다음 분기/반기 계획 수립을 위한 구체적인 권장사항을 제시해주세요.
            """,
        }

    async def _generate_error_recovery_prompts(
        self, metadata: EnhancedTemplateMetadata
    ) -> Dict[str, str]:
        """오류 복구를 위한 프롬프트 생성"""

        return {
            "data_correction": f"""
            {metadata.name}에서 데이터 오류가 발견되었습니다.

            가능한 오류 유형:
            1. 계산 공식 오류
            2. 데이터 타입 불일치
            3. 비즈니스 로직 위반
            4. 필수 데이터 누락

            오류를 자동으로 감지하고 수정 방안을 제시해주세요.
            """,
            "template_repair": f"""
            템플릿 구조에 문제가 있는 것 같습니다.

            예상되는 문제:
            - 필수 섹션 누락
            - 계산 공식 오류
            - 셀 참조 문제

            {metadata.name}의 원래 구조와 비교하여 복구 방안을 제시해주세요.
            """,
            "workflow_recovery": f"""
            사용자가 워크플로우 중간에 막혔습니다.

            표준 워크플로우:
            {self._format_workflow_steps(metadata.workflow_steps)}

            현재 상황을 진단하고 다시 시작할 수 있는 방법을 안내해주세요.
            """,
        }

    def _format_workflow_steps(self, steps: List[WorkflowStep]) -> str:
        """워크플로우 단계를 텍스트로 포맷팅"""
        if not steps:
            return "워크플로우 정보 없음"

        formatted = []
        for step in steps:
            formatted.append(f"{step.step_number}. {step.title}: {step.description}")

        return "\n".join(formatted)

    def _format_common_errors(self, errors: List[str]) -> str:
        """일반적인 오류들을 텍스트로 포맷팅"""
        if not errors:
            return "일반적인 오류 정보 없음"

        return "\n".join([f"- {error}" for error in errors])

    async def get_contextual_ai_prompt(
        self,
        metadata: EnhancedTemplateMetadata,
        task_type: str,
        user_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        특정 작업에 맞는 컨텍스트 기반 AI 프롬프트 생성

        Args:
            metadata: 템플릿 메타데이터
            task_type: 작업 유형 (validation, assistance, insights, etc.)
            user_data: 사용자 데이터 (선택사항)
        """

        base_context = f"""
        템플릿: {metadata.name}
        카테고리: {metadata.category.value}
        목적: {metadata.purpose}
        사용자: {', '.join(metadata.target_audience)}
        복잡도: {metadata.complexity.value}
        """

        # 작업 유형별 특화 프롬프트
        task_prompts = {
            "validation": metadata.ai_prompts.get(
                "data_validation", "데이터를 검증해주세요."
            ),
            "analysis": metadata.ai_prompts.get(
                "trend_analysis", "데이터를 분석해주세요."
            ),
            "optimization": metadata.ai_prompts.get(
                "optimization", "개선방안을 제시해주세요."
            ),
            "assistance": "사용자를 단계별로 안내해주세요.",
            "troubleshooting": "문제를 진단하고 해결방안을 제시해주세요.",
        }

        task_prompt = task_prompts.get(task_type, "요청사항을 처리해주세요.")

        # 사용자 데이터가 있는 경우 추가 컨텍스트 제공
        data_context = ""
        if user_data:
            data_context = f"\n\n현재 데이터:\n{json.dumps(user_data, ensure_ascii=False, indent=2)}"

        return f"{base_context}\n\n요청사항: {task_prompt}{data_context}"

    async def generate_smart_suggestions(
        self, metadata: EnhancedTemplateMetadata, current_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        현재 입력된 데이터를 기반으로 스마트 제안 생성
        """
        suggestions = []

        # 1. 누락된 필수 데이터 확인
        missing_fields = self._check_missing_required_fields(metadata, current_data)
        if missing_fields:
            suggestions.append(
                {
                    "type": "missing_data",
                    "priority": "high",
                    "title": "필수 데이터 입력 필요",
                    "description": f"다음 필수 필드가 비어있습니다: {', '.join(missing_fields)}",
                    "action": "complete_required_fields",
                    "fields": missing_fields,
                }
            )

        # 2. 데이터 일관성 검증
        inconsistencies = self._check_data_consistency(metadata, current_data)
        for inconsistency in inconsistencies:
            suggestions.append(
                {
                    "type": "data_validation",
                    "priority": "medium",
                    "title": "데이터 검증 필요",
                    "description": inconsistency,
                    "action": "review_data",
                }
            )

        # 3. 최적화 제안
        optimizations = self._generate_optimization_suggestions(metadata, current_data)
        suggestions.extend(optimizations)

        return suggestions

    def _check_missing_required_fields(
        self, metadata: EnhancedTemplateMetadata, current_data: Dict[str, Any]
    ) -> List[str]:
        """필수 필드 누락 확인"""
        missing = []

        for section in metadata.sections:
            for field in section.fields:
                if field.is_required:
                    field_key = f"{section.name}.{field.name}"
                    if field_key not in current_data or not current_data[field_key]:
                        missing.append(field.name)

        return missing

    def _check_data_consistency(
        self, metadata: EnhancedTemplateMetadata, current_data: Dict[str, Any]
    ) -> List[str]:
        """데이터 일관성 검증"""
        issues = []

        # 계산 공식 검증
        for metric, formula in metadata.calculation_methods.items():
            # 간단한 합계 검증 예시
            if "총수입 - 총지출" in formula:
                # 실제 구현에서는 더 정교한 검증 로직 필요
                pass

        return issues

    def _generate_optimization_suggestions(
        self, metadata: EnhancedTemplateMetadata, current_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """최적화 제안 생성"""
        suggestions = []

        # 비즈니스 로직 기반 제안
        if metadata.category == metadata.category.FINANCE:
            suggestions.append(
                {
                    "type": "optimization",
                    "priority": "low",
                    "title": "현금흐름 최적화 기회",
                    "description": "매출채권 회전율을 개선하여 현금흐름을 안정화할 수 있습니다",
                    "action": "review_receivables",
                }
            )

        return suggestions


# 글로벌 인스턴스
ai_template_context_service = AITemplateContextService()
