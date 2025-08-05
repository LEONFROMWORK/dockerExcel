"""
Fix Recommendation Service
수정 제안 생성 전담 서비스 - DRY 원칙 적용
"""

from typing import List, Dict, Any, Optional
from app.core.interfaces import ExcelError
import re
import logging

logger = logging.getLogger(__name__)


class FixRecommendationService:
    """오류 수정 제안 생성 서비스"""

    def __init__(self):
        # 오류 타입별 수정 템플릿
        self.fix_templates = self._init_fix_templates()
        # 수정 가이드라인
        self.fix_guidelines = self._init_fix_guidelines()
        # 자동 수정 가능 패턴
        self.auto_fixable_patterns = self._init_auto_fixable_patterns()

    def generate_recommendations(self, error: ExcelError) -> Dict[str, Any]:
        """오류에 대한 수정 제안 생성"""
        recommendation = {
            "error_id": error.id,
            "auto_fixable": error.is_auto_fixable,
            "fixes": [],
            "guidelines": [],
            "warnings": [],
            "confidence": 0.0,
        }

        # 자동 수정 가능한 경우
        if error.is_auto_fixable:
            auto_fix = self._generate_auto_fix(error)
            if auto_fix:
                recommendation["fixes"].append(auto_fix)
                recommendation["confidence"] = auto_fix.get("confidence", 0.8)

        # 수동 수정 가이드라인
        guidelines = self._generate_guidelines(error)
        recommendation["guidelines"] = guidelines

        # 경고 사항
        warnings = self._generate_warnings(error)
        recommendation["warnings"] = warnings

        # 대체 수정 방법
        alternatives = self._generate_alternatives(error)
        if alternatives:
            recommendation["fixes"].extend(alternatives)

        return recommendation

    def batch_recommendations(
        self, errors: List[ExcelError]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """여러 오류에 대한 일괄 수정 제안"""
        recommendations_by_type = {}

        for error in errors:
            error_type = self._normalize_error_type(error.type)

            if error_type not in recommendations_by_type:
                recommendations_by_type[error_type] = []

            recommendation = self.generate_recommendations(error)
            recommendations_by_type[error_type].append(recommendation)

        # 유사한 수정 제안 병합
        merged_recommendations = self._merge_similar_recommendations(
            recommendations_by_type
        )

        return merged_recommendations

    def get_fix_template(self, error_type: str) -> Optional[str]:
        """오류 타입에 대한 수정 템플릿 반환"""
        normalized_type = self._normalize_error_type(error_type)
        return self.fix_templates.get(normalized_type)

    def estimate_fix_complexity(self, error: ExcelError) -> str:
        """수정 복잡도 추정"""
        if error.is_auto_fixable:
            return "simple"

        # 복잡도 기준
        if any(
            keyword in error.type.lower() for keyword in ["circular", "vba", "macro"]
        ):
            return "complex"

        if error.severity in ["critical", "high"]:
            return "moderate"

        return "simple"

    # === Private 메서드 ===

    def _init_fix_templates(self) -> Dict[str, str]:
        """수정 템플릿 초기화"""
        return {
            "division_by_zero": "=IFERROR({original_formula}, 0)",
            "missing_reference": '=IFERROR({original_formula}, "")',
            "circular_reference": "# 순환 참조를 제거하고 별도 셀에 계산 분리",
            "name_error": '=IFERROR({original_formula}, "Name Error")',
            "value_error": "=IFERROR(VALUE({cell_ref}), 0)",
            "missing_option_explicit": "Option Explicit\n{original_code}",
            "hardcoded_path": "# 설정 시트에 경로 저장 후 참조\n=Settings!$B$1 & {filename}",
            "volatile_function": "# 휘발성 함수를 정적 값으로 대체 고려",
            "large_range": "# 동적 범위 사용\n=SUM(OFFSET(A1,0,0,COUNTA(A:A),1))",
        }

    def _init_fix_guidelines(self) -> Dict[str, List[str]]:
        """수정 가이드라인 초기화"""
        return {
            "circular_reference": [
                "순환 참조 체인 확인",
                "계산을 여러 셀로 분리",
                "반복 계산 옵션 활성화 고려",
                "계산 순서 재정의",
            ],
            "vba_security_risk": [
                "위험한 API 호출 검토",
                "사용자 입력 검증 추가",
                "에러 처리 구현",
                "코드 서명 고려",
            ],
            "performance_issue": [
                "계산 범위 최소화",
                "휘발성 함수 제거",
                "배열 수식 최적화",
                "조건부 서식 단순화",
            ],
            "data_validation": [
                "데이터 유효성 규칙 정의",
                "드롭다운 목록 사용",
                "입력 메시지 추가",
                "오류 메시지 커스터마이즈",
            ],
        }

    def _init_auto_fixable_patterns(self) -> Dict[str, Dict[str, Any]]:
        """자동 수정 가능 패턴 초기화"""
        return {
            "iferror_wrappable": {
                "pattern": re.compile(r"^=(?!IFERROR)(.+)$"),
                "fix": lambda match: f'=IFERROR({match.group(1)}, "")',
                "confidence": 0.9,
            },
            "option_explicit_missing": {
                "pattern": re.compile(
                    r"^(?!Option Explicit)(.*)$", re.MULTILINE | re.DOTALL
                ),
                "fix": lambda match: f"Option Explicit\n\n{match.group(1)}",
                "confidence": 0.95,
            },
            "select_activate_removal": {
                "pattern": re.compile(r"(\w+)\.Select\s*\n\s*Selection\.(\w+)"),
                "fix": lambda match: f"{match.group(1)}.{match.group(2)}",
                "confidence": 0.85,
            },
        }

    def _generate_auto_fix(self, error: ExcelError) -> Optional[Dict[str, Any]]:
        """자동 수정 생성"""
        error_type = self._normalize_error_type(error.type)

        # 템플릿 기반 수정
        if error_type in self.fix_templates:
            template = self.fix_templates[error_type]

            # 템플릿 변수 치환
            fix_code = template.format(
                original_formula=error.formula or "",
                cell_ref=error.cell,
                original_code=error.value or "",
            )

            return {
                "type": "template",
                "code": fix_code,
                "description": f"{error_type} 오류 자동 수정",
                "confidence": 0.85,
            }

        # 패턴 기반 수정
        for pattern_name, pattern_info in self.auto_fixable_patterns.items():
            if error.formula or error.value:
                content = error.formula or str(error.value)
                match = pattern_info["pattern"].match(content)

                if match:
                    fixed_content = pattern_info["fix"](match)
                    return {
                        "type": "pattern",
                        "code": fixed_content,
                        "description": f"{pattern_name} 패턴 수정",
                        "confidence": pattern_info["confidence"],
                    }

        return None

    def _generate_guidelines(self, error: ExcelError) -> List[str]:
        """수정 가이드라인 생성"""
        guidelines = []

        # 기본 가이드라인
        guidelines.append(f"오류 위치: {error.sheet} 시트의 {error.cell} 셀")

        # 오류 타입별 가이드라인
        error_category = self._get_error_category(error.type)
        if error_category in self.fix_guidelines:
            guidelines.extend(self.fix_guidelines[error_category])

        # 심각도별 추가 가이드라인
        if error.severity == "critical":
            guidelines.append("⚠️ 중요: 이 오류는 즉시 수정이 필요합니다")
        elif error.severity == "high":
            guidelines.append("📌 이 오류는 우선적으로 처리하는 것이 좋습니다")

        # 제안된 수정이 있는 경우
        if error.suggested_fix:
            guidelines.append(f"제안: {error.suggested_fix}")

        return guidelines

    def _generate_warnings(self, error: ExcelError) -> List[str]:
        """경고 사항 생성"""
        warnings = []

        # 순환 참조 경고
        if "circular" in error.type.lower():
            warnings.append("순환 참조 수정 시 다른 수식에 영향을 줄 수 있습니다")

        # VBA 관련 경고
        if "vba" in error.type.lower():
            warnings.append("VBA 코드 수정 후 반드시 테스트가 필요합니다")

        # 대량 데이터 경고
        if "performance" in error.type.lower():
            warnings.append(
                "대량의 데이터가 있는 경우 수정 작업이 오래 걸릴 수 있습니다"
            )

        # 자동 수정 경고
        if error.is_auto_fixable and error.confidence < 0.8:
            warnings.append("자동 수정의 신뢰도가 낮으므로 수동 검토가 필요합니다")

        return warnings

    def _generate_alternatives(self, error: ExcelError) -> List[Dict[str, Any]]:
        """대체 수정 방법 생성"""
        alternatives = []

        # VLOOKUP → XLOOKUP 대체
        if error.formula and "VLOOKUP" in error.formula:
            alternatives.append(
                {
                    "type": "modernization",
                    "code": self._convert_vlookup_to_xlookup(error.formula),
                    "description": "XLOOKUP으로 현대화 (Excel 365)",
                    "confidence": 0.7,
                }
            )

        # 중첩 IF → SWITCH 대체
        if error.formula and error.formula.count("IF(") > 3:
            alternatives.append(
                {
                    "type": "simplification",
                    "code": "=SWITCH(조건, 값1, 결과1, 값2, 결과2, ...)",
                    "description": "중첩 IF를 SWITCH로 단순화",
                    "confidence": 0.6,
                }
            )

        return alternatives

    def _merge_similar_recommendations(
        self, recommendations_by_type: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """유사한 수정 제안 병합"""
        merged = {}

        for error_type, recommendations in recommendations_by_type.items():
            if len(recommendations) > 3:
                # 많은 유사 오류가 있는 경우 일괄 수정 제안
                batch_fix = {
                    "type": "batch",
                    "description": f"{error_type} 오류 {len(recommendations)}개 일괄 수정",
                    "affected_count": len(recommendations),
                    "sample_fixes": recommendations[:3],
                }
                merged[error_type] = [batch_fix]
            else:
                merged[error_type] = recommendations

        return merged

    def _normalize_error_type(self, error_type: str) -> str:
        """오류 타입 정규화"""
        # 공백과 특수문자 제거
        normalized = error_type.lower().replace(" ", "_").replace("-", "_")

        # 일반적인 매핑
        mappings = {
            "div/0": "division_by_zero",
            "#ref!": "missing_reference",
            "#name?": "name_error",
            "#value!": "value_error",
            "circular": "circular_reference",
        }

        for key, value in mappings.items():
            if key in normalized:
                return value

        return normalized

    def _get_error_category(self, error_type: str) -> str:
        """오류 카테고리 추출"""
        error_lower = error_type.lower()

        if "vba" in error_lower:
            return "vba_security_risk"
        elif "circular" in error_lower:
            return "circular_reference"
        elif "performance" in error_lower or "slow" in error_lower:
            return "performance_issue"
        elif "validation" in error_lower:
            return "data_validation"

        return "general"

    def _convert_vlookup_to_xlookup(self, formula: str) -> str:
        """VLOOKUP을 XLOOKUP으로 변환 (예시)"""
        # 실제 구현은 더 복잡하지만 간단한 예시
        return formula.replace("VLOOKUP(", "XLOOKUP(")
