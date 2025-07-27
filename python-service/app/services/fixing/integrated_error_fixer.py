"""
Integrated Error Fixer Service
통합 오류 수정 서비스 - SOLID 원칙 적용
"""

from typing import List, Dict, Any, Optional
from app.core.interfaces import (
    IErrorFixer, IErrorFixStrategy, IProgressReporter,
    ExcelError, FixResult, ExcelErrorType
)
from app.services.fixing.strategies.div_zero_fix_strategy import DivZeroFixStrategy
from app.services.workbook_loader import OpenpyxlWorkbookLoader
from app.core.exceptions import ErrorFixingError
from app.core.config import settings
import asyncio
import logging
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

class IntegratedErrorFixer(IErrorFixer):
    """통합 오류 수정 서비스"""
    
    def __init__(self, progress_reporter: Optional[IProgressReporter] = None):
        self.progress_reporter = progress_reporter
        self.workbook_loader = OpenpyxlWorkbookLoader()
        
        # 수정 전략들 (Open/Closed Principle)
        self.fix_strategies: List[IErrorFixStrategy] = [
            DivZeroFixStrategy(),
            # NAFixStrategy(),          # 추후 구현
            # NameFixStrategy(),        # 추후 구현
            # RefFixStrategy(),         # 추후 구현
            # ValueFixStrategy(),       # 추후 구현
        ]
        
        # 수정 이력 캐시
        self._fix_history = {}
        self._batch_size = settings.BATCH_PROCESSING_SIZE
    
    async def fix(self, error: ExcelError) -> FixResult:
        """단일 오류 수정"""
        try:
            # 적절한 전략 찾기
            strategy = self._find_strategy(error)
            if not strategy:
                return FixResult(
                    success=False,
                    error_id=error.id,
                    original_formula=error.formula or "",
                    fixed_formula="",
                    confidence=0.0,
                    applied=False,
                    message=f"'{error.type}' 오류에 대한 수정 전략이 없습니다"
                )
            
            # 수정 적용
            result = await strategy.apply_fix(error)
            
            # 이력 저장
            self._save_fix_history(error, result)
            
            # 진행 상황 보고
            if self.progress_reporter and result.success:
                await self.progress_reporter.report_progress(
                    1, 1, f"오류 수정 완료: {error.cell}"
                )
            
            return result
            
        except Exception as e:
            logger.error(f"오류 수정 실패: {str(e)}")
            if self.progress_reporter:
                await self.progress_reporter.report_error(e)
            
            raise ErrorFixingError(
                f"오류 수정 중 예외 발생: {str(e)}",
                code="FIX_ERROR",
                details={"error_id": error.id, "error_type": error.type}
            )
    
    def can_fix(self, error: ExcelError) -> bool:
        """오류 수정 가능 여부"""
        return any(strategy.can_handle(error) for strategy in self.fix_strategies)
    
    async def fix_batch(self, errors: List[ExcelError], strategy: str = "safe") -> Dict[str, Any]:
        """여러 오류 일괄 수정"""
        start_time = datetime.now()
        results = {
            'total': len(errors),
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'results': [],
            'strategy': strategy
        }
        
        # 진행 상황 초기화
        if self.progress_reporter:
            await self.progress_reporter.start_task("일괄 오류 수정", len(errors))
        
        # 오류를 우선순위와 신뢰도에 따라 정렬
        sorted_errors = self._sort_errors_for_fixing(errors, strategy)
        
        # 배치 처리
        for i in range(0, len(sorted_errors), self._batch_size):
            batch = sorted_errors[i:i + self._batch_size]
            batch_results = await self._process_batch(batch, strategy)
            
            # 결과 집계
            for result in batch_results:
                results['results'].append(result)
                if result.success:
                    results['success'] += 1
                else:
                    results['failed'] += 1
            
            # 진행 상황 보고
            if self.progress_reporter:
                await self.progress_reporter.report_progress(
                    i + len(batch), len(errors),
                    f"수정 중: {results['success']}개 성공, {results['failed']}개 실패"
                )
        
        # 완료 시간 계산
        results['processing_time'] = (datetime.now() - start_time).total_seconds()
        
        # 완료 보고
        if self.progress_reporter:
            await self.progress_reporter.complete_task(
                "일괄 오류 수정",
                results
            )
        
        return results
    
    async def apply_fix_to_workbook(self, workbook: Any, fix_result: FixResult) -> bool:
        """수정 사항을 워크북에 적용"""
        try:
            # 수정된 수식을 해당 셀에 적용
            # 실제 구현은 워크북 타입에 따라 다름
            sheet_name, cell_address = self._parse_cell_reference(fix_result.error_id)
            
            success = await self.workbook_loader.set_cell_value(
                workbook,
                sheet_name,
                cell_address,
                fix_result.fixed_formula
            )
            
            if success:
                fix_result.applied = True
                logger.info(f"수정 적용 완료: {sheet_name}!{cell_address}")
            
            return success
            
        except Exception as e:
            logger.error(f"수정 적용 실패: {str(e)}")
            return False
    
    def add_strategy(self, strategy: IErrorFixStrategy):
        """새로운 수정 전략 추가 (Open/Closed Principle)"""
        self.fix_strategies.append(strategy)
        logger.info(f"새로운 수정 전략 추가: {strategy.__class__.__name__}")
    
    def remove_strategy(self, strategy_type: type):
        """수정 전략 제거"""
        self.fix_strategies = [s for s in self.fix_strategies 
                              if not isinstance(s, strategy_type)]
    
    def get_fix_confidence(self, error: ExcelError) -> float:
        """오류 수정 신뢰도 계산"""
        strategy = self._find_strategy(error)
        if strategy:
            return strategy.get_confidence(error)
        return 0.0
    
    def get_fix_history(self, error_id: str) -> Optional[Dict[str, Any]]:
        """수정 이력 조회"""
        return self._fix_history.get(error_id)
    
    # Private methods
    def _find_strategy(self, error: ExcelError) -> Optional[IErrorFixStrategy]:
        """오류에 맞는 수정 전략 찾기"""
        for strategy in self.fix_strategies:
            if strategy.can_handle(error):
                return strategy
        return None
    
    def _save_fix_history(self, error: ExcelError, result: FixResult):
        """수정 이력 저장"""
        self._fix_history[error.id] = {
            'timestamp': datetime.now().isoformat(),
            'error': error.__dict__,
            'result': result.__dict__
        }
    
    def _sort_errors_for_fixing(self, errors: List[ExcelError], strategy: str) -> List[ExcelError]:
        """수정을 위한 오류 정렬"""
        if strategy == "safe":
            # 안전 모드: 신뢰도가 높은 것부터
            return sorted(errors, key=lambda e: (
                -self.get_fix_confidence(e),  # 신뢰도 높은 것 우선
                e.severity == 'low',           # 낮은 심각도 우선
                e.sheet,
                e.cell
            ))
        elif strategy == "aggressive":
            # 공격적 모드: 심각도가 높은 것부터
            severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
            return sorted(errors, key=lambda e: (
                severity_order.get(e.severity, 4),
                -self.get_fix_confidence(e),
                e.sheet,
                e.cell
            ))
        else:
            # 기본: 입력 순서대로
            return errors
    
    async def _process_batch(self, errors: List[ExcelError], strategy: str) -> List[FixResult]:
        """배치 처리"""
        tasks = []
        for error in errors:
            if strategy == "safe" and self.get_fix_confidence(error) < 0.8:
                # 안전 모드에서는 신뢰도 80% 미만은 건너뜀
                tasks.append(self._create_skip_result(error, "신뢰도 부족"))
            else:
                tasks.append(self.fix(error))
        
        # 병렬 처리
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 예외 처리
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(self._create_error_result(errors[i], str(result)))
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _create_skip_result(self, error: ExcelError, reason: str) -> FixResult:
        """건너뛰기 결과 생성"""
        return FixResult(
            success=False,
            error_id=error.id,
            original_formula=error.formula or "",
            fixed_formula="",
            confidence=0.0,
            applied=False,
            message=f"건너뜀: {reason}"
        )
    
    def _create_error_result(self, error: ExcelError, error_msg: str) -> FixResult:
        """오류 결과 생성"""
        return FixResult(
            success=False,
            error_id=error.id,
            original_formula=error.formula or "",
            fixed_formula="",
            confidence=0.0,
            applied=False,
            message=f"오류: {error_msg}"
        )
    
    def _parse_cell_reference(self, error_id: str) -> tuple:
        """오류 ID에서 시트명과 셀 주소 추출"""
        # 구현은 error_id 형식에 따라 다름
        # 예: "sheet1_A1_div_zero" -> ("sheet1", "A1")
        parts = error_id.split('_')
        if len(parts) >= 2:
            return parts[0], parts[1]
        return "Sheet1", "A1"  # 기본값