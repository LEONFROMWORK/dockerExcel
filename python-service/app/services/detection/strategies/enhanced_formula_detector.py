"""
Enhanced Formula Error Detector
Detects potential formula errors before Excel evaluation
"""

import re
from typing import List, Set
from app.core.interfaces import ExcelError, ExcelErrorType
from app.services.detection.strategies.formula_error_detector import (
    FormulaErrorDetector,
)
import logging

logger = logging.getLogger(__name__)


class EnhancedFormulaDetector(FormulaErrorDetector):
    """Enhanced formula detector that can detect potential errors"""

    def __init__(self):
        super().__init__()
        # Additional patterns for detecting potential errors
        self.potential_error_patterns = {
            "div_zero": re.compile(
                r"/\s*(?:0|[A-Z]+\d+)(?![0-9])"
            ),  # Division by zero or cell
            "missing_sheet": re.compile(r"([A-Z]\w+)!"),  # Sheet references
            "vlookup": re.compile(
                r"VLOOKUP\s*\(", re.IGNORECASE
            ),  # VLOOKUP that might fail
            "circular_ref": re.compile(
                r"([A-Z]+\d+)"
            ),  # Cell references for circular check
        }

    async def check_cell_formula(self, cell, sheet_name: str) -> List[ExcelError]:
        """Enhanced cell formula checking"""
        # Skip if cell already has an actual error value
        if cell.value is not None:
            value_str = str(cell.value).strip()
            if value_str in [
                "#DIV/0!",
                "#N/A",
                "#NAME?",
                "#NULL!",
                "#NUM!",
                "#REF!",
                "#VALUE!",
                "#SPILL!",
                "#CALC!",
            ]:
                # Actual error already exists, don't check for potential errors
                return []

        errors = await super().check_cell_formula(cell, sheet_name)

        # Additional checks for potential errors only if no actual error exists
        if cell.data_type == "f" and cell.value:
            formula = str(cell.value)

            # Check for potential DIV/0
            if self._check_potential_div_zero(formula, cell):
                errors.append(
                    self._create_error(
                        cell,
                        sheet_name,
                        ExcelErrorType.DIV_ZERO,
                        "잠재적 0으로 나누기 오류",
                    )
                )

            # Check for sheet references
            worksheet = cell.parent
            workbook = worksheet.parent
            missing_sheets = self._check_missing_sheets(formula, workbook)
            for sheet in missing_sheets:
                errors.append(
                    self._create_error(
                        cell,
                        sheet_name,
                        ExcelErrorType.REF,
                        f"존재하지 않는 시트 참조: {sheet}",
                    )
                )

            # Check for potential #N/A in VLOOKUP
            if self._check_potential_vlookup_error(formula):
                errors.append(
                    self._create_error(
                        cell,
                        sheet_name,
                        ExcelErrorType.NA,
                        "VLOOKUP이 실패할 가능성이 있습니다",
                    )
                )

            # Check for circular references
            if self._check_circular_reference(cell, sheet_name):
                errors.append(
                    self._create_error(
                        cell,
                        sheet_name,
                        ExcelErrorType.CIRCULAR_REF,
                        "순환 참조가 감지되었습니다",
                    )
                )

            # Check for #VALUE! errors (text + number)
            if self._check_potential_value_error(formula, worksheet):
                errors.append(
                    self._create_error(
                        cell,
                        sheet_name,
                        ExcelErrorType.VALUE,
                        "타입 불일치로 인한 잠재적 오류",
                    )
                )

        return errors

    def _check_potential_div_zero(self, formula: str, cell) -> bool:
        """Check for potential division by zero"""
        # Look for division by literal 0
        if "/0" in formula.replace(" ", ""):
            return True

        # Look for division by cells that might contain 0
        div_pattern = re.compile(r"/\s*([A-Z]+\d+)")
        matches = div_pattern.findall(formula)

        worksheet = cell.parent
        for cell_ref in matches:
            try:
                ref_cell = worksheet[cell_ref]
                if ref_cell.value == 0:
                    return True
            except (KeyError, AttributeError, ValueError):
                pass

        return False

    def _check_missing_sheets(self, formula: str, workbook) -> Set[str]:
        """Check for references to non-existent sheets"""
        missing_sheets = set()
        sheet_pattern = re.compile(r"([A-Z]\w+)!")

        existing_sheets = set(workbook.sheetnames)
        referenced_sheets = set(sheet_pattern.findall(formula))

        for sheet in referenced_sheets:
            if sheet not in existing_sheets:
                missing_sheets.add(sheet)

        return missing_sheets

    def _check_potential_vlookup_error(self, formula: str) -> bool:
        """Check if VLOOKUP might fail"""
        # Simple check - could be enhanced
        return "VLOOKUP" in formula.upper()

    def _check_circular_reference(self, cell, sheet_name: str) -> bool:
        """Check for circular references"""
        visited = set()

        def has_circular(current_cell, target_coord):
            if current_cell.coordinate in visited:
                return current_cell.coordinate == target_coord

            visited.add(current_cell.coordinate)

            if current_cell.data_type == "f" and current_cell.value:
                # Extract cell references from formula
                refs = re.findall(r"([A-Z]+\d+)", str(current_cell.value))

                worksheet = current_cell.parent
                for ref in refs:
                    try:
                        ref_cell = worksheet[ref]
                        if ref == target_coord or has_circular(ref_cell, target_coord):
                            return True
                    except (KeyError, AttributeError, ValueError):
                        pass

            return False

        return has_circular(cell, cell.coordinate)

    def _check_potential_value_error(self, formula: str, worksheet) -> bool:
        """Check for potential #VALUE! errors"""
        # Look for operations between text and numbers
        if "+" in formula or "-" in formula or "*" in formula or "/" in formula:
            refs = re.findall(r"([A-Z]+\d+)", formula)

            has_text = False
            has_number = False

            for ref in refs:
                try:
                    ref_cell = worksheet[ref]
                    if ref_cell.data_type == "s":  # String
                        has_text = True
                    elif ref_cell.data_type == "n":  # Number
                        has_number = True
                except (KeyError, AttributeError, ValueError):
                    pass

            return has_text and has_number

        return False

    def _create_error(
        self, cell, sheet_name: str, error_type: ExcelErrorType, message: str
    ) -> ExcelError:
        """오류 객체 생성 - Override to set auto_fixable correctly"""
        return ExcelError(
            id=f"{sheet_name}_{cell.coordinate}_{error_type.value}",
            type=error_type.value,
            category="critical_error",  # All formula errors are critical
            sheet=sheet_name,
            cell=cell.coordinate,
            formula=str(cell.value) if cell.data_type == "f" else None,
            value=cell.value,
            message=message,
            severity=self._get_error_severity(error_type),
            is_auto_fixable=self._is_auto_fixable(error_type),
            suggested_fix=self._get_suggested_fix(error_type, cell),
            confidence=0.95,
        )
