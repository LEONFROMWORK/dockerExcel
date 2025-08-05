"""
Error Predictor Service
실시간 오류 예측 서비스
"""

from typing import Dict, Any, List, Set
from dataclasses import dataclass
from datetime import datetime
import logging
from app.core.interfaces import IErrorPredictor, RiskLevel
from app.services.context import WorkbookContext, CellInfo
from app.services.detection.integrated_error_detector import IntegratedErrorDetector

logger = logging.getLogger(__name__)


@dataclass
class ErrorPrediction:
    """오류 예측 결과"""

    cell_address: str
    sheet_name: str
    risk_level: RiskLevel
    probability: float
    error_type: str
    description: str
    prevention_tips: List[str]
    related_cells: List[str] = None


class ErrorPredictor(IErrorPredictor):
    """오류 예측 엔진"""

    def __init__(self):
        self.error_detector = IntegratedErrorDetector()
        self.prediction_cache: Dict[str, List[ErrorPrediction]] = {}
        self.error_patterns = self._init_error_patterns()

    def _init_error_patterns(self) -> Dict[str, Dict[str, Any]]:
        """오류 패턴 초기화"""
        return {
            "circular_reference_risk": {
                "detector": self._check_circular_reference_risk,
                "error_type": "CIRCULAR_REFERENCE",
                "base_probability": 0.3,
            },
            "div_zero_risk": {
                "detector": self._check_div_zero_risk,
                "error_type": "DIV_ZERO",
                "base_probability": 0.4,
            },
            "ref_error_risk": {
                "detector": self._check_ref_error_risk,
                "error_type": "REF_ERROR",
                "base_probability": 0.35,
            },
            "data_type_mismatch": {
                "detector": self._check_type_mismatch_risk,
                "error_type": "VALUE_ERROR",
                "base_probability": 0.45,
            },
            "missing_dependency": {
                "detector": self._check_missing_dependency_risk,
                "error_type": "DEPENDENCY_ERROR",
                "base_probability": 0.25,
            },
        }

    async def predict_errors(
        self, context: WorkbookContext, changed_cells: List[str]
    ) -> List[ErrorPrediction]:
        """변경된 셀들을 기반으로 오류 예측"""
        try:
            predictions = []

            # 변경된 셀들의 영향을 받는 모든 셀 찾기
            affected_cells = await self._find_affected_cells(context, changed_cells)

            # 각 영향받는 셀에 대해 오류 위험도 평가
            for sheet_name, cell_address in affected_cells:
                cell = context.get_cell(sheet_name, cell_address)
                if not cell or not cell.formula:
                    continue

                # 각 오류 패턴에 대해 검사
                for pattern_name, pattern in self.error_patterns.items():
                    risk = await pattern["detector"](cell, context)
                    if risk > 0:
                        prediction = ErrorPrediction(
                            cell_address=cell_address,
                            sheet_name=sheet_name,
                            risk_level=self._calculate_risk_level(risk),
                            probability=risk,
                            error_type=pattern["error_type"],
                            description=self._get_error_description(
                                pattern["error_type"], cell
                            ),
                            prevention_tips=self._get_prevention_tips(
                                pattern["error_type"]
                            ),
                            related_cells=list(cell.dependencies)[:5],  # 최대 5개
                        )
                        predictions.append(prediction)

            # 위험도 순으로 정렬
            predictions.sort(key=lambda p: p.probability, reverse=True)

            # 캐시 저장
            cache_key = f"{context.file_id}_{datetime.now().isoformat()}"
            self.prediction_cache[cache_key] = predictions[:10]  # 상위 10개만

            return predictions[:10]

        except Exception as e:
            logger.error(f"오류 예측 실패: {str(e)}")
            return []

    async def _find_affected_cells(
        self, context: WorkbookContext, changed_cells: List[str]
    ) -> Set[tuple]:
        """변경된 셀의 영향을 받는 모든 셀 찾기"""
        affected = set()

        for cell_ref in changed_cells:
            # cell_ref가 "Sheet1!A1" 형태일 수 있음
            if "!" in cell_ref:
                sheet_name, cell_address = cell_ref.split("!", 1)
            else:
                sheet_name = "Sheet1"
                cell_address = cell_ref

            # 직접 의존 셀들
            dependents = context.get_dependent_cells(sheet_name, cell_address)
            for dep in dependents:
                if "!" in dep:
                    dep_sheet, dep_addr = dep.split("!", 1)
                    affected.add((dep_sheet, dep_addr))
                else:
                    affected.add((sheet_name, dep))

        return affected

    async def _check_circular_reference_risk(
        self, cell: CellInfo, context: WorkbookContext
    ) -> float:
        """순환 참조 위험도 확인"""
        if not cell.formula or not cell.dependencies:
            return 0.0

        # 재귀적으로 의존성 체크
        visited = set()
        risk = 0.0

        def check_circular(current_ref: str, path: List[str], depth: int = 0) -> float:
            if depth > 10:  # 깊이 제한
                return 0.1

            if current_ref in visited:
                return 0.0
            visited.add(current_ref)

            if current_ref == f"{cell.sheet}!{cell.address}" and len(path) > 0:
                # 순환 참조 발견
                return 0.9

            # 현재 셀의 의존성 확인
            if "!" in current_ref:
                sheet, addr = current_ref.split("!", 1)
                dep_cell = context.get_cell(sheet, addr)
            else:
                dep_cell = context.get_cell(cell.sheet, current_ref)

            if dep_cell and dep_cell.dependencies:
                max_risk = 0.0
                for dep in dep_cell.dependencies:
                    sub_risk = check_circular(dep, path + [current_ref], depth + 1)
                    max_risk = max(max_risk, sub_risk)
                return max_risk * 0.8  # 거리에 따라 감소

            return 0.0

        # 각 의존성에 대해 체크
        for dep in cell.dependencies:
            risk = max(risk, check_circular(dep, [f"{cell.sheet}!{cell.address}"]))

        return min(risk, 0.9)

    async def _check_div_zero_risk(
        self, cell: CellInfo, context: WorkbookContext
    ) -> float:
        """0으로 나누기 위험도 확인"""
        if not cell.formula:
            return 0.0

        # 나누기 연산자 확인
        if "/" not in cell.formula:
            return 0.0

        risk = 0.0

        # 간단한 패턴 매칭
        import re

        # /B1, /SUM(...) 등의 패턴 찾기
        div_patterns = re.findall(r"/\s*([A-Z]+\d+|\w+\([^)]*\))", cell.formula)

        for pattern in div_patterns:
            if re.match(r"[A-Z]+\d+", pattern):  # 셀 참조인 경우
                # 참조 셀의 값 확인
                ref_cell = context.get_cell(cell.sheet, pattern)
                if ref_cell:
                    if ref_cell.value == 0:
                        risk = max(risk, 0.9)
                    elif ref_cell.value is None:
                        risk = max(risk, 0.6)
                    elif (
                        isinstance(ref_cell.value, str) and ref_cell.value.strip() == ""
                    ):
                        risk = max(risk, 0.7)
            elif "SUM" in pattern or "AVERAGE" in pattern:
                # 집계 함수의 경우 빈 범위 위험
                risk = max(risk, 0.3)

        return risk

    async def _check_ref_error_risk(
        self, cell: CellInfo, context: WorkbookContext
    ) -> float:
        """참조 오류 위험도 확인"""
        if not cell.dependencies:
            return 0.0

        risk = 0.0

        for dep in cell.dependencies:
            if "!" in dep:
                sheet_name, cell_addr = dep.split("!", 1)
                # 시트 존재 여부 확인
                if not context.get_sheet(sheet_name):
                    risk = max(risk, 0.8)
                    continue

                ref_cell = context.get_cell(sheet_name, cell_addr)
            else:
                ref_cell = context.get_cell(cell.sheet, dep)

            # 참조 셀이 없거나 오류가 있는 경우
            if not ref_cell:
                risk = max(risk, 0.7)
            elif ref_cell.errors:
                risk = max(risk, 0.6)
            elif isinstance(ref_cell.value, str) and ref_cell.value.startswith("#"):
                risk = max(risk, 0.8)

        return risk

    async def _check_type_mismatch_risk(
        self, cell: CellInfo, context: WorkbookContext
    ) -> float:
        """데이터 타입 불일치 위험도 확인"""
        if not cell.formula:
            return 0.0

        risk = 0.0

        # 수식에서 사용되는 함수 확인
        numeric_functions = ["SUM", "AVERAGE", "MIN", "MAX", "COUNT"]
        text_functions = ["CONCATENATE", "UPPER", "LOWER", "TRIM"]

        has_numeric = any(func in cell.formula.upper() for func in numeric_functions)
        any(func in cell.formula.upper() for func in text_functions)

        if has_numeric:
            # 의존 셀들의 데이터 타입 확인
            for dep in cell.dependencies:
                if "!" in dep:
                    sheet_name, cell_addr = dep.split("!", 1)
                    dep_cell = context.get_cell(sheet_name, cell_addr)
                else:
                    dep_cell = context.get_cell(cell.sheet, dep)

                if dep_cell and isinstance(dep_cell.value, str):
                    try:
                        float(dep_cell.value)
                    except (ValueError, TypeError):
                        risk = max(risk, 0.7)

        return risk

    async def _check_missing_dependency_risk(
        self, cell: CellInfo, context: WorkbookContext
    ) -> float:
        """누락된 의존성 위험도 확인"""
        if not cell.formula:
            return 0.0

        # 수식에서 참조하는 범위가 비어있는지 확인
        import re

        # A1:B10 형태의 범위 찾기
        ranges = re.findall(r"([A-Z]+\d+:[A-Z]+\d+)", cell.formula)

        risk = 0.0
        for range_str in ranges:
            # 범위의 셀들이 비어있는지 확인
            empty_count = 0
            total_count = 0

            # 간단한 구현 - 실제로는 범위를 파싱해서 모든 셀 확인 필요
            start, end = range_str.split(":")
            # 여기서는 시작과 끝 셀만 확인
            for addr in [start, end]:
                total_count += 1
                check_cell = context.get_cell(cell.sheet, addr)
                if not check_cell or check_cell.value is None:
                    empty_count += 1

            if total_count > 0 and empty_count / total_count > 0.5:
                risk = max(risk, 0.5)

        return risk

    def _calculate_risk_level(self, probability: float) -> RiskLevel:
        """확률을 기반으로 위험 레벨 계산"""
        if probability >= 0.7:
            return RiskLevel.HIGH
        elif probability >= 0.4:
            return RiskLevel.MEDIUM
        elif probability >= 0.2:
            return RiskLevel.LOW
        else:
            return RiskLevel.NONE

    def _get_error_description(self, error_type: str, cell: CellInfo) -> str:
        """오류 타입에 따른 설명 생성"""
        descriptions = {
            "CIRCULAR_REFERENCE": f"{cell.address} 셀이 순환 참조를 일으킬 가능성이 있습니다",
            "DIV_ZERO": f"{cell.address} 셀에서 0으로 나누기 오류가 발생할 수 있습니다",
            "REF_ERROR": f"{cell.address} 셀의 참조가 유효하지 않을 수 있습니다",
            "VALUE_ERROR": f"{cell.address} 셀에서 데이터 타입 불일치가 발생할 수 있습니다",
            "DEPENDENCY_ERROR": f"{cell.address} 셀의 일부 의존성이 누락되었을 수 있습니다",
        }
        return descriptions.get(
            error_type, f"{cell.address} 셀에서 오류가 발생할 수 있습니다"
        )

    def _get_prevention_tips(self, error_type: str) -> List[str]:
        """오류 예방 팁"""
        tips = {
            "CIRCULAR_REFERENCE": [
                "수식의 참조 관계를 다시 확인하세요",
                "간접 참조(INDIRECT)를 사용하는 경우 특히 주의하세요",
                "순환 참조 추적 도구를 사용하세요",
            ],
            "DIV_ZERO": [
                "IFERROR 함수로 오류를 처리하세요",
                "분모가 0이 아닌지 IF 함수로 확인하세요",
                "예: =IF(B1=0, 0, A1/B1)",
            ],
            "REF_ERROR": [
                "참조하는 셀이나 시트가 존재하는지 확인하세요",
                "INDIRECT 함수 사용 시 유효성을 검증하세요",
                "이름 정의를 사용하여 참조를 관리하세요",
            ],
            "VALUE_ERROR": [
                "데이터 타입이 일치하는지 확인하세요",
                "VALUE, TEXT 함수로 타입을 변환하세요",
                "ISNUMBER, ISTEXT로 타입을 검사하세요",
            ],
            "DEPENDENCY_ERROR": [
                "참조 범위에 데이터가 있는지 확인하세요",
                "COUNTA 함수로 빈 셀을 확인하세요",
                "기본값을 설정하여 누락을 방지하세요",
            ],
        }
        return tips.get(
            error_type, ["수식을 다시 검토하세요", "자동 수정 기능을 사용해보세요"]
        )

    def get_prediction_summary(self, session_id: str) -> Dict[str, Any]:
        """예측 요약 조회"""
        # 최근 예측 결과 조회
        recent_predictions = []
        for key in sorted(self.prediction_cache.keys(), reverse=True)[:1]:
            if session_id in key:
                recent_predictions = self.prediction_cache[key]
                break

        if not recent_predictions:
            return {
                "has_predictions": False,
                "total_risks": 0,
                "high_risks": 0,
                "predictions": [],
            }

        high_risks = [p for p in recent_predictions if p.risk_level == RiskLevel.HIGH]

        return {
            "has_predictions": True,
            "total_risks": len(recent_predictions),
            "high_risks": len(high_risks),
            "predictions": [
                {
                    "cell": f"{p.sheet_name}!{p.cell_address}",
                    "risk_level": p.risk_level.value,
                    "probability": round(p.probability * 100, 1),
                    "error_type": p.error_type,
                    "description": p.description,
                    "prevention_tips": p.prevention_tips[:2],  # 상위 2개 팁
                }
                for p in recent_predictions[:5]  # 상위 5개
            ],
        }
