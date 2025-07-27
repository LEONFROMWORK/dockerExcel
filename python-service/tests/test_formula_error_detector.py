"""
Formula Error Detector Tests
수식 오류 감지기 테스트
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from app.services.detection.strategies.formula_error_detector import FormulaErrorDetector
from app.core.interfaces import ExcelErrorType
import asyncio

class TestFormulaErrorDetector:
    """FormulaErrorDetector 테스트"""
    
    @pytest.fixture
    def detector(self):
        """감지기 인스턴스"""
        return FormulaErrorDetector()
    
    @pytest.fixture
    def mock_worksheet(self):
        """모의 워크시트"""
        worksheet = MagicMock()
        worksheet.title = "Sheet1"
        return worksheet
    
    def test_can_detect_formula_errors(self, detector):
        """수식 오류 타입 감지 가능 여부 테스트"""
        # 감지 가능한 오류 타입
        assert detector.can_detect("#DIV/0!") == True
        assert detector.can_detect("#N/A") == True
        assert detector.can_detect("#NAME?") == True
        assert detector.can_detect("#REF!") == True
        assert detector.can_detect("#VALUE!") == True
        
        # 감지 불가능한 오류 타입
        assert detector.can_detect("Duplicate Data") == False
        assert detector.can_detect("Missing Data") == False
    
    @pytest.mark.asyncio
    async def test_detect_div_zero_error(self, detector, mock_worksheet):
        """#DIV/0! 오류 감지 테스트"""
        # 모의 셀 설정
        mock_cell = MagicMock()
        mock_cell.coordinate = "A1"
        mock_cell.value = "#DIV/0!"
        mock_cell.data_type = "e"  # Error type
        mock_cell.formula = "=B1/C1"
        mock_cell.row = 1
        mock_cell.column = 1
        
        mock_worksheet.iter_rows.return_value = [[mock_cell]]
        
        # 오류 감지 실행
        errors = await detector._detect_sheet_errors(mock_worksheet, "Sheet1")
        
        # 검증
        assert len(errors) == 1
        error = errors[0]
        assert error.type == ExcelErrorType.DIV_ZERO.value
        assert error.cell == "A1"
        assert error.sheet == "Sheet1"
        assert error.formula == "=B1/C1"
        assert error.is_auto_fixable == True
        assert error.severity == "high"
    
    @pytest.mark.asyncio
    async def test_detect_multiple_errors(self, detector, mock_worksheet):
        """여러 오류 동시 감지 테스트"""
        # 여러 오류가 있는 셀들
        cells = []
        
        # #DIV/0! 오류
        cell1 = MagicMock()
        cell1.coordinate = "A1"
        cell1.value = "#DIV/0!"
        cell1.data_type = "e"
        cell1.formula = "=10/0"
        cells.append(cell1)
        
        # #NAME? 오류
        cell2 = MagicMock()
        cell2.coordinate = "B2"
        cell2.value = "#NAME?"
        cell2.data_type = "e"
        cell2.formula = "=UNKNOWNFUNC()"
        cells.append(cell2)
        
        # 정상 셀
        cell3 = MagicMock()
        cell3.coordinate = "C3"
        cell3.value = 100
        cell3.data_type = "n"
        cell3.formula = "=A1+B1"
        cells.append(cell3)
        
        mock_worksheet.iter_rows.return_value = [cells]
        
        # 오류 감지 실행
        errors = await detector._detect_sheet_errors(mock_worksheet, "Sheet1")
        
        # 검증
        assert len(errors) == 2
        
        # 오류 타입 확인
        error_types = [e.type for e in errors]
        assert ExcelErrorType.DIV_ZERO.value in error_types
        assert ExcelErrorType.NAME.value in error_types
    
    @pytest.mark.asyncio
    async def test_detect_with_workbook(self, detector):
        """전체 워크북 오류 감지 테스트"""
        # 모의 워크북
        mock_workbook = MagicMock()
        mock_workbook.sheetnames = ["Sheet1", "Sheet2"]
        
        # Sheet1 모의 설정
        sheet1 = MagicMock()
        sheet1.title = "Sheet1"
        
        error_cell = MagicMock()
        error_cell.coordinate = "A1"
        error_cell.value = "#REF!"
        error_cell.data_type = "e"
        error_cell.formula = "=Sheet3!A1"
        
        sheet1.iter_rows.return_value = [[error_cell]]
        
        # Sheet2 모의 설정 (오류 없음)
        sheet2 = MagicMock()
        sheet2.title = "Sheet2"
        
        normal_cell = MagicMock()
        normal_cell.coordinate = "A1"
        normal_cell.value = "Normal"
        normal_cell.data_type = "s"
        
        sheet2.iter_rows.return_value = [[normal_cell]]
        
        # 워크북에 시트 연결
        mock_workbook.__getitem__.side_effect = lambda x: sheet1 if x == "Sheet1" else sheet2
        
        # 오류 감지 실행
        errors = await detector.detect(mock_workbook)
        
        # 검증
        assert len(errors) == 1
        assert errors[0].type == ExcelErrorType.REF.value
        assert errors[0].sheet == "Sheet1"
    
    def test_error_severity_assignment(self, detector):
        """오류 심각도 할당 테스트"""
        severities = detector._get_error_severity()
        
        # 높은 심각도
        assert severities[ExcelErrorType.DIV_ZERO] == "high"
        assert severities[ExcelErrorType.REF] == "high"
        
        # 중간 심각도
        assert severities[ExcelErrorType.VALUE] == "medium"
        assert severities[ExcelErrorType.NAME] == "medium"
        
        # 낮은 심각도
        assert severities[ExcelErrorType.NA] == "low"
    
    def test_auto_fixable_determination(self, detector):
        """자동 수정 가능 여부 판단 테스트"""
        auto_fixable = detector._is_auto_fixable()
        
        # 자동 수정 가능
        assert auto_fixable[ExcelErrorType.DIV_ZERO] == True
        assert auto_fixable[ExcelErrorType.NA] == True
        
        # 자동 수정 불가능
        assert auto_fixable[ExcelErrorType.REF] == False
        assert auto_fixable[ExcelErrorType.NAME] == False