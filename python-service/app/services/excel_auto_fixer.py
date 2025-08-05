"""
Excel Auto Fixer Service
통합 자동 수정 시스템 - 모든 자동 수정 기능을 통합 관리
"""

from typing import Dict, Any, List, Optional
import logging
import time
from datetime import datetime

# ExcelError is now defined in excel_analyzer.py
from .excel_analyzer import ExcelError, ExcelAnalyzer
from .circular_reference_detector import CircularReferenceDetector
from .fast_formula_fixer import FastFormulaFixer
from .openai_service import OpenAIService


class ExcelAutoFixer:
    """Excel 파일의 모든 오류를 자동으로 수정하는 통합 시스템"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.error_analyzer = ExcelAnalyzer()
        self.circular_detector = CircularReferenceDetector()
        self.formula_fixer = FastFormulaFixer(max_workers=4, cache_size=1000)
        self.openai_service = OpenAIService()

    async def auto_fix_file(
        self, file_path: str, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Excel 파일의 모든 오류를 자동으로 감지하고 수정"""

        start_time = time.time()
        options = options or {}

        result = {
            "file_path": file_path,
            "status": "processing",
            "original_errors": {},
            "fixed_errors": {},
            "unfixed_errors": {},
            "performance": {},
            "summary": {},
        }

        try:
            # 1단계: 오류 감지
            self.logger.info(f"Starting error detection for: {file_path}")
            detection_result = await self.error_analyzer.analyze_file(file_path)

            if detection_result.get("error"):
                result["status"] = "error"
                result["error"] = detection_result["error"]
                return result

            result["original_errors"] = detection_result
            total_errors = len(detection_result["errors"])

            # 2단계: 오류 분류
            errors_by_type = self._classify_errors(detection_result["errors"])

            # 3단계: 자동 수정 실행
            fixed_count = 0

            # 3-1: 수식 오류 수정
            if errors_by_type["formula_errors"]:
                self.logger.info(
                    f"Fixing {len(errors_by_type['formula_errors'])} formula errors"
                )
                formula_fix_result = await self.formula_fixer.fix_formula_errors_batch(
                    workbook=detection_result.get("workbook"),
                    errors=errors_by_type["formula_errors"],
                )
                result["fixed_errors"]["formulas"] = formula_fix_result
                fixed_count += formula_fix_result["summary"]["successfully_fixed"]

            # 3-2: 데이터 품질 문제 수정
            if errors_by_type["data_quality"] and options.get("fix_data_quality", True):
                data_fix_result = await self._fix_data_quality_issues(
                    errors_by_type["data_quality"], detection_result.get("workbook")
                )
                result["fixed_errors"]["data_quality"] = data_fix_result
                fixed_count += data_fix_result["fixed_count"]

            # 3-3: 구조적 문제 수정
            if errors_by_type["structural"] and options.get("fix_structural", True):
                structural_fix_result = await self._fix_structural_issues(
                    errors_by_type["structural"], detection_result.get("workbook")
                )
                result["fixed_errors"]["structural"] = structural_fix_result
                fixed_count += structural_fix_result["fixed_count"]

            # 3-4: 서식 문제 수정
            if errors_by_type["formatting"] and options.get("fix_formatting", True):
                format_fix_result = await self._fix_formatting_issues(
                    errors_by_type["formatting"], detection_result.get("workbook")
                )
                result["fixed_errors"]["formatting"] = format_fix_result
                fixed_count += format_fix_result["fixed_count"]

            # 4단계: 수정 후 재검증
            if fixed_count > 0 and options.get("revalidate", True):
                self.logger.info("Revalidating after fixes")
                revalidation_result = await self.error_analyzer.analyze_file(file_path)
                result["unfixed_errors"] = revalidation_result["errors"]

            # 5단계: 요약 생성
            end_time = time.time()
            result["performance"] = {
                "total_time": round(end_time - start_time, 2),
                "errors_per_second": (
                    round(total_errors / (end_time - start_time), 2)
                    if total_errors > 0
                    else 0
                ),
                "cache_hit_rate": self._calculate_cache_hit_rate(),
            }

            result["summary"] = {
                "total_errors_found": total_errors,
                "total_errors_fixed": fixed_count,
                "fix_rate": (
                    round(fixed_count / total_errors * 100, 1)
                    if total_errors > 0
                    else 0
                ),
                "remaining_errors": total_errors - fixed_count,
                "categories_fixed": {
                    "formulas": result["fixed_errors"]
                    .get("formulas", {})
                    .get("summary", {})
                    .get("successfully_fixed", 0),
                    "data_quality": result["fixed_errors"]
                    .get("data_quality", {})
                    .get("fixed_count", 0),
                    "structural": result["fixed_errors"]
                    .get("structural", {})
                    .get("fixed_count", 0),
                    "formatting": result["fixed_errors"]
                    .get("formatting", {})
                    .get("fixed_count", 0),
                },
            }

            result["status"] = "completed"

            # 6단계: 파일 저장 (옵션)
            if options.get("save_fixed_file", False):
                fixed_file_path = self._save_fixed_file(
                    detection_result.get("workbook"),
                    file_path,
                    options.get("output_path"),
                )
                result["fixed_file_path"] = fixed_file_path

        except Exception as e:
            self.logger.error(f"Auto-fix failed: {str(e)}")
            result["status"] = "error"
            result["error"] = str(e)

        finally:
            # 리소스 정리
            self.formula_fixer.cleanup()

        return result

    def _classify_errors(self, errors: List[ExcelError]) -> Dict[str, List[ExcelError]]:
        """오류를 타입별로 분류"""
        classified = {
            "formula_errors": [],
            "circular_references": [],
            "data_quality": [],
            "structural": [],
            "formatting": [],
        }

        for error in errors:
            if error.error_type in ["formula_error", "inefficient_formula"]:
                classified["formula_errors"].append(error)
            elif error.error_type == "circular_reference":
                classified["circular_references"].append(error)
            elif error.error_type in [
                "duplicate_data",
                "missing_data",
                "text_stored_as_number",
            ]:
                classified["data_quality"].append(error)
            elif error.error_type in [
                "merged_cells",
                "excessive_empty_rows",
                "empty_sheets",
                "duplicate_headers",
            ]:
                classified["structural"].append(error)
            elif error.error_type in [
                "inconsistent_date_format",
                "mixed_currency_symbols",
            ]:
                classified["formatting"].append(error)

        return classified

    async def _fix_data_quality_issues(
        self, errors: List[ExcelError], workbook
    ) -> Dict[str, Any]:
        """데이터 품질 문제 자동 수정"""
        result = {"fixed_count": 0, "fixes_applied": []}

        for error in errors:
            if error.auto_fixable:
                try:
                    if error.error_type == "duplicate_data":
                        # 중복 데이터 제거
                        worksheet = workbook[error.sheet]
                        row = int(error.cell[1:])
                        worksheet.delete_rows(row)
                    elif error.error_type == "missing_data":
                        # 누락 데이터 기본값으로 채우기
                        worksheet = workbook[error.sheet]
                        worksheet[error.cell].value = 0
                    elif error.error_type == "text_stored_as_number":
                        # 텍스트를 숫자로 변환
                        worksheet = workbook[error.sheet]
                        cell_value = str(worksheet[error.cell].value)
                        try:
                            worksheet[error.cell].value = float(cell_value)
                        except ValueError:
                            self.logger.warning(
                                f"Cannot convert {cell_value} to number"
                            )

                    result["fixed_count"] += 1
                    result["fixes_applied"].append(
                        {
                            "error_type": error.error_type,
                            "location": error.location,
                            "fix_applied": error.suggested_fix,
                        }
                    )

                except Exception as e:
                    self.logger.error(f"Failed to fix {error.error_type}: {str(e)}")

        return result

    async def _fix_structural_issues(
        self, errors: List[ExcelError], workbook
    ) -> Dict[str, Any]:
        """구조적 문제 자동 수정"""
        result = {"fixed_count": 0, "fixes_applied": []}

        for error in errors:
            if error.auto_fixable:
                try:
                    if error.error_type == "merged_cells":
                        # 병합 셀 해제
                        worksheet = workbook[error.sheet]
                        for merged_range in list(worksheet.merged_cells.ranges):
                            if error.cell in merged_range:
                                worksheet.unmerge_cells(str(merged_range))
                                self.logger.info(f"Unmerged cells: {merged_range}")
                    elif error.error_type == "excessive_empty_rows":
                        # 빈 행 제거
                        worksheet = workbook[error.sheet]
                        empty_rows = []
                        for row in range(worksheet.max_row, 0, -1):
                            if all(cell.value is None for cell in worksheet[row]):
                                empty_rows.append(row)
                            else:
                                break

                        # 마지막 데이터 이후의 빈 행들 제거
                        for row_idx in empty_rows:
                            worksheet.delete_rows(row_idx)
                        self.logger.info(
                            f"Removed {len(empty_rows)} empty rows from {error.sheet}"
                        )
                    elif error.error_type == "empty_sheets":
                        # 빈 시트 제거 (최소 1개 시트는 남겨둠)
                        if (
                            len(workbook.worksheets) > 1
                            and error.sheet in workbook.sheetnames
                        ):
                            worksheet = workbook[error.sheet]
                            # 시트가 정말 비어있는지 확인
                            if worksheet.max_row == 1 and worksheet.max_column == 1:
                                if worksheet["A1"].value is None:
                                    workbook.remove(worksheet)
                                    self.logger.info(
                                        f"Removed empty sheet: {error.sheet}"
                                    )

                    result["fixed_count"] += 1
                    result["fixes_applied"].append(
                        {
                            "error_type": error.error_type,
                            "location": error.location,
                            "fix_applied": error.suggested_fix,
                        }
                    )

                except Exception as e:
                    self.logger.error(f"Failed to fix {error.error_type}: {str(e)}")

        return result

    async def _fix_formatting_issues(
        self, errors: List[ExcelError], workbook
    ) -> Dict[str, Any]:
        """서식 문제 자동 수정"""
        result = {"fixed_count": 0, "fixes_applied": []}

        for error in errors:
            if error.auto_fixable:
                try:
                    if error.error_type == "inconsistent_date_format":
                        # 날짜 형식 통일
                        worksheet = workbook[error.sheet]
                        cell = worksheet[error.cell]
                        if isinstance(cell.value, datetime):
                            # 표준 날짜 형식으로 설정
                            cell.number_format = "YYYY-MM-DD"
                        elif isinstance(cell.value, str):
                            # 문자열을 날짜로 변환 시도
                            try:
                                from dateutil import parser

                                date_value = parser.parse(cell.value)
                                cell.value = date_value
                                cell.number_format = "YYYY-MM-DD"
                            except Exception:
                                self.logger.warning(
                                    f"Could not parse date: {cell.value}"
                                )
                    elif error.error_type == "mixed_currency_symbols":
                        # 통화 기호 통일 (USD로 통일)
                        worksheet = workbook[error.sheet]
                        cell = worksheet[error.cell]
                        if isinstance(cell.value, (int, float)):
                            # 통화 형식 적용
                            cell.number_format = "$#,##0.00"
                        elif isinstance(cell.value, str):
                            # 문자열에서 숫자 추출
                            import re

                            numbers = re.findall(r"[\d,]+\.?\d*", str(cell.value))
                            if numbers:
                                try:
                                    value = float(numbers[0].replace(",", ""))
                                    cell.value = value
                                    cell.number_format = "$#,##0.00"
                                except ValueError:
                                    self.logger.warning(
                                        f"Could not convert to currency: {cell.value}"
                                    )

                    result["fixed_count"] += 1
                    result["fixes_applied"].append(
                        {
                            "error_type": error.error_type,
                            "location": error.location,
                            "fix_applied": error.suggested_fix,
                        }
                    )

                except Exception as e:
                    self.logger.error(f"Failed to fix {error.error_type}: {str(e)}")

        return result

    def _calculate_cache_hit_rate(self) -> float:
        """캐시 적중률 계산"""
        if hasattr(self.formula_fixer, "fix_cache"):
            total_hits = sum(
                cache.hit_count for cache in self.formula_fixer.fix_cache.values()
            )
            total_requests = total_hits + len(self.formula_fixer.fix_cache)
            return (
                round(total_hits / total_requests * 100, 1) if total_requests > 0 else 0
            )
        return 0

    def _save_fixed_file(
        self, workbook, original_path: str, output_path: Optional[str]
    ) -> str:
        """수정된 파일 저장"""
        if not output_path:
            # 원본 파일명에 _fixed 추가
            base_name = original_path.rsplit(".", 1)[0]
            extension = original_path.rsplit(".", 1)[1]
            output_path = f"{base_name}_fixed.{extension}"

        workbook.save(output_path)
        return output_path
