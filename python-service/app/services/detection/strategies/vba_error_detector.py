"""
VBA Error Detector
VBA 코드 오류 감지 전략 - AdvancedVBAAnalyzer 통합
"""

from typing import List, Dict, Any
from app.core.interfaces import ExcelError
from app.core.base_detector import BaseErrorDetector
from app.core.cacheable_mixin import CacheableMixin
from app.services.advanced_vba_analyzer import AdvancedVBAAnalyzer
import re
import logging

logger = logging.getLogger(__name__)

# oletools 가용성 체크
try:
    OLETOOLS_AVAILABLE = True
except ImportError:
    OLETOOLS_AVAILABLE = False
    logger.warning("oletools not available. Advanced VBA analysis will be limited.")


class VBAErrorDetector(BaseErrorDetector, CacheableMixin):
    """VBA 코드 오류 감지기 - AdvancedVBAAnalyzer 기능 통합"""

    def __init__(self):
        super().__init__()

        # AdvancedVBAAnalyzer 인스턴스
        self.advanced_analyzer = AdvancedVBAAnalyzer() if OLETOOLS_AVAILABLE else None

        # 기본 VBA 에러 패턴 (oletools 없을 때 사용)
        self.error_patterns = {
            "undeclared_variable": re.compile(
                r"(?<!Dim\s)(?<!Private\s)(?<!Public\s)(?<!Const\s)\b([a-zA-Z_]\w*)\s*=",
                re.IGNORECASE,
            ),
            "missing_error_handling": re.compile(
                r"^(?!.*On\s+Error).*\b(Open|Kill|MkDir|Name|FileCopy)\b",
                re.IGNORECASE | re.MULTILINE,
            ),
            "deprecated_function": re.compile(
                r"\b(DoEvents|SendKeys|Application\.Volatile)\b", re.IGNORECASE
            ),
            "infinite_loop_risk": re.compile(
                r"Do\s+While\s+True|While\s+True|Do\s*\n(?!.*Loop\s+Until)",
                re.IGNORECASE | re.DOTALL,
            ),
            "missing_option_explicit": re.compile(
                r"^(?!Option\s+Explicit)", re.IGNORECASE
            ),
            "hardcoded_path": re.compile(r'["\'](?:[A-Za-z]:[\\/]|\\\\)[^"\']+["\']'),
            "sql_injection_risk": re.compile(
                r'\.Execute\s*\(\s*["\'].*["\'].*&.*&.*["\']', re.IGNORECASE
            ),
            "unhandled_object": re.compile(
                r"Set\s+(\w+)\s*=.*(?!.*Set\s+\1\s*=\s*Nothing)",
                re.IGNORECASE | re.DOTALL,
            ),
        }

        # VBA 구문 패턴
        self.syntax_patterns = {
            "sub_function": re.compile(
                r"(?:Sub|Function)\s+(\w+)\s*\(([^)]*)\)", re.IGNORECASE
            ),
            "end_sub_function": re.compile(r"End\s+(?:Sub|Function)", re.IGNORECASE),
            "variable_declaration": re.compile(
                r"(?:Dim|Private|Public|Const)\s+(\w+)(?:\s+As\s+(\w+))?", re.IGNORECASE
            ),
            "with_block": re.compile(r"With\s+(.+)", re.IGNORECASE),
            "end_with": re.compile(r"End\s+With", re.IGNORECASE),
            "if_block": re.compile(r"If\s+(.+)\s+Then", re.IGNORECASE),
            "end_if": re.compile(r"End\s+If", re.IGNORECASE),
        }

        # 위험한 API 호출
        self.dangerous_apis = {
            "Shell": "critical",
            "CreateObject": "high",
            "GetObject": "high",
            "Environ": "medium",
            "Kill": "critical",
            "FileCopy": "high",
            "Name": "high",
            "URLDownloadToFile": "critical",
            "MSXML2.XMLHTTP": "critical",
            "WScript.Shell": "critical",
        }

    async def detect(self, workbook: Any) -> List[ExcelError]:
        """워크북에서 VBA 오류 감지 - AdvancedVBAAnalyzer 통합"""
        errors = []

        # workbook이 파일 경로인 경우와 객체인 경우 처리
        file_path = None
        if isinstance(workbook, str):
            file_path = workbook
        elif hasattr(workbook, "path"):
            file_path = workbook.path

        # AdvancedVBAAnalyzer 사용 (oletools 사용 가능한 경우)
        if self.advanced_analyzer and file_path:
            try:
                # 고급 분석 수행
                analysis_result = await self.advanced_analyzer.analyze_file(file_path)

                if analysis_result.get("has_vba") and analysis_result.get("errors"):
                    # AdvancedVBAError를 ExcelError로 변환
                    for vba_error in analysis_result["errors"]:
                        excel_error = self._convert_advanced_error(vba_error)
                        errors.append(excel_error)

                return errors

            except Exception as e:
                logger.warning(
                    f"AdvancedVBAAnalyzer 실패, 기본 분석으로 전환: {str(e)}"
                )
                # 기본 분석으로 fallback

        # 기본 VBA 분석 (oletools 없는 경우)
        if hasattr(workbook, "vba_archive") and workbook.vba_archive:
            try:
                vba_modules = self._extract_vba_modules(workbook)

                for module_name, code in vba_modules.items():
                    module_errors = await self._analyze_vba_module(module_name, code)
                    errors.extend(module_errors)

            except Exception as e:
                logger.error(f"기본 VBA 분석 오류: {str(e)}")

        return errors

    def can_detect(self, error_type: str) -> bool:
        """VBA 관련 오류만 감지"""
        vba_error_types = [
            "VBA Syntax Error",
            "VBA Logic Error",
            "VBA Security Risk",
            "VBA Performance Issue",
            "VBA Best Practice Violation",
        ]
        return error_type in vba_error_types

    async def _analyze_vba_module(
        self, module_name: str, code: str
    ) -> List[ExcelError]:
        """VBA 모듈 분석"""
        errors = []

        # Option Explicit 확인
        if not re.search(r"Option\s+Explicit", code, re.IGNORECASE):
            errors.append(
                self._create_error(
                    module_name,
                    1,
                    "VBA Best Practice Violation",
                    "Option Explicit이 선언되지 않았습니다",
                    "medium",
                    True,
                    "모듈 최상단에 'Option Explicit' 추가",
                )
            )

        # 에러 처리 확인
        errors.extend(self._check_error_handling(module_name, code))

        # 변수 선언 확인
        errors.extend(self._check_variable_declarations(module_name, code))

        # 무한 루프 위험 확인
        errors.extend(self._check_infinite_loops(module_name, code))

        # 하드코딩된 경로 확인
        errors.extend(self._check_hardcoded_paths(module_name, code))

        # 위험한 API 사용 확인
        errors.extend(self._check_dangerous_apis(module_name, code))

        # SQL 인젝션 위험 확인
        errors.extend(self._check_sql_injection(module_name, code))

        # 구조적 문제 확인
        errors.extend(self._check_structural_issues(module_name, code))

        # 미사용 변수/함수 확인
        errors.extend(self._check_unused_items(module_name, code))

        return errors

    def _check_error_handling(self, module_name: str, code: str) -> List[ExcelError]:
        """에러 처리 확인"""
        errors = []

        # 함수/서브루틴별로 분석
        procedures = self._extract_procedures(code)

        for proc_name, proc_code in procedures.items():
            # 위험한 작업이 있는지 확인
            if self.error_patterns["missing_error_handling"].search(proc_code):
                if not re.search(r"On\s+Error", proc_code, re.IGNORECASE):
                    line_num = self._find_line_number(code, proc_code)
                    errors.append(
                        self._create_error(
                            module_name,
                            line_num,
                            "VBA Logic Error",
                            f"{proc_name} 프로시저에 에러 처리가 없습니다",
                            "high",
                            True,
                            "On Error GoTo 또는 On Error Resume Next 추가",
                        )
                    )

        return errors

    def _check_variable_declarations(
        self, module_name: str, code: str
    ) -> List[ExcelError]:
        """변수 선언 확인"""
        errors = []
        declared_vars = set()

        # 선언된 변수 수집
        for match in self.syntax_patterns["variable_declaration"].finditer(code):
            declared_vars.add(match.group(1).lower())

        # 사용되는 변수 확인
        lines = code.split("\n")
        for i, line in enumerate(lines):
            # 주석 제거
            if "'" in line:
                line = line[: line.index("'")]

            # 할당 패턴 찾기
            assignments = re.findall(r"\b([a-zA-Z_]\w*)\s*=", line)
            for var in assignments:
                if var.lower() not in declared_vars and not self._is_builtin(var):
                    errors.append(
                        self._create_error(
                            module_name,
                            i + 1,
                            "VBA Syntax Error",
                            f"선언되지 않은 변수 사용: {var}",
                            "high",
                            True,
                            f"Dim {var} As Variant 추가",
                        )
                    )

        return errors

    def _check_infinite_loops(self, module_name: str, code: str) -> List[ExcelError]:
        """무한 루프 위험 확인"""
        errors = []

        # Do While True 패턴
        for match in self.error_patterns["infinite_loop_risk"].finditer(code):
            line_num = code[: match.start()].count("\n") + 1
            errors.append(
                self._create_error(
                    module_name,
                    line_num,
                    "VBA Logic Error",
                    "무한 루프 위험이 있습니다",
                    "critical",
                    True,
                    "루프 종료 조건을 명확히 정의하세요",
                )
            )

        return errors

    def _check_hardcoded_paths(self, module_name: str, code: str) -> List[ExcelError]:
        """하드코딩된 경로 확인"""
        errors = []

        for match in self.error_patterns["hardcoded_path"].finditer(code):
            line_num = code[: match.start()].count("\n") + 1
            path = match.group(0)
            errors.append(
                self._create_error(
                    module_name,
                    line_num,
                    "VBA Best Practice Violation",
                    f"하드코딩된 경로: {path}",
                    "medium",
                    True,
                    "설정 파일이나 환경 변수 사용 권장",
                )
            )

        return errors

    def _check_dangerous_apis(self, module_name: str, code: str) -> List[ExcelError]:
        """위험한 API 사용 확인"""
        errors = []

        for api, severity in self.dangerous_apis.items():
            pattern = re.compile(rf"\b{api}\b", re.IGNORECASE)
            for match in pattern.finditer(code):
                line_num = code[: match.start()].count("\n") + 1
                errors.append(
                    self._create_error(
                        module_name,
                        line_num,
                        "VBA Security Risk",
                        f"위험한 API 사용: {api}",
                        severity,
                        False,
                        "보안을 고려하여 대체 방법 검토 필요",
                    )
                )

        return errors

    def _check_sql_injection(self, module_name: str, code: str) -> List[ExcelError]:
        """SQL 인젝션 위험 확인"""
        errors = []

        for match in self.error_patterns["sql_injection_risk"].finditer(code):
            line_num = code[: match.start()].count("\n") + 1
            errors.append(
                self._create_error(
                    module_name,
                    line_num,
                    "VBA Security Risk",
                    "SQL 인젝션 위험이 있습니다",
                    "critical",
                    True,
                    "파라미터화된 쿼리 사용 권장",
                )
            )

        return errors

    def _check_structural_issues(self, module_name: str, code: str) -> List[ExcelError]:
        """구조적 문제 확인"""
        errors = []

        # With 블록 매칭
        with_count = len(self.syntax_patterns["with_block"].findall(code))
        end_with_count = len(self.syntax_patterns["end_with"].findall(code))

        if with_count != end_with_count:
            errors.append(
                self._create_error(
                    module_name,
                    0,
                    "VBA Syntax Error",
                    f"With 블록이 올바르게 닫히지 않았습니다 (With: {with_count}, End With: {end_with_count})",
                    "high",
                    False,
                    "모든 With 블록에 대응하는 End With 확인",
                )
            )

        # If 블록 매칭
        if_count = len(self.syntax_patterns["if_block"].findall(code))
        end_if_count = len(self.syntax_patterns["end_if"].findall(code))

        # 한 줄 If 문은 End If가 필요 없으므로 정확한 검사는 더 복잡함
        if abs(if_count - end_if_count) > 3:  # 허용 오차
            errors.append(
                self._create_error(
                    module_name,
                    0,
                    "VBA Syntax Error",
                    "If 블록 구조에 문제가 있을 수 있습니다",
                    "medium",
                    False,
                    "모든 If 블록이 올바르게 닫혔는지 확인",
                )
            )

        return errors

    def _check_unused_items(self, module_name: str, code: str) -> List[ExcelError]:
        """미사용 변수/함수 확인"""
        errors = []

        # 선언된 변수 수집
        declared_vars = {}
        for match in self.syntax_patterns["variable_declaration"].finditer(code):
            var_name = match.group(1)
            line_num = code[: match.start()].count("\n") + 1
            declared_vars[var_name.lower()] = line_num

        # 사용 여부 확인
        for var_name, line_num in declared_vars.items():
            # 선언 부분을 제외하고 사용되는지 확인
            usage_pattern = re.compile(rf"\b{var_name}\b", re.IGNORECASE)
            usages = list(usage_pattern.finditer(code))

            if len(usages) <= 1:  # 선언만 있고 사용 안됨
                errors.append(
                    self._create_error(
                        module_name,
                        line_num,
                        "VBA Best Practice Violation",
                        f"미사용 변수: {var_name}",
                        "low",
                        True,
                        "사용하지 않는 변수는 제거하세요",
                    )
                )

        return errors

    # Helper methods
    def _extract_vba_modules(self, workbook: Any) -> Dict[str, str]:
        """VBA 모듈 추출"""
        modules = {}

        try:
            # openpyxl의 VBA 아카이브에서 모듈 추출
            # 실제 구현은 VBA 파일 형식에 따라 다름
            if hasattr(workbook, "vba_archive"):
                # 간단한 예시 - 실제로는 더 복잡한 파싱 필요
                modules["Module1"] = "Sample VBA Code"
        except Exception as e:
            logger.error(f"VBA 모듈 추출 오류: {str(e)}")

        return modules

    def _extract_procedures(self, code: str) -> Dict[str, str]:
        """프로시저 추출"""
        procedures = {}
        current_proc = None
        current_code = []

        for line in code.split("\n"):
            # 새 프로시저 시작
            match = self.syntax_patterns["sub_function"].search(line)
            if match:
                if current_proc:
                    procedures[current_proc] = "\n".join(current_code)
                current_proc = match.group(1)
                current_code = [line]
            elif current_proc:
                current_code.append(line)
                # 프로시저 끝
                if self.syntax_patterns["end_sub_function"].search(line):
                    procedures[current_proc] = "\n".join(current_code)
                    current_proc = None
                    current_code = []

        return procedures

    def _is_builtin(self, var_name: str) -> bool:
        """내장 변수/함수인지 확인"""
        builtins = {
            "true",
            "false",
            "null",
            "nothing",
            "empty",
            "me",
            "err",
            "debug",
            "application",
            "activeworkbook",
            "activesheet",
            "selection",
            "range",
            "cells",
        }
        return var_name.lower() in builtins

    def _find_line_number(self, full_code: str, snippet: str) -> int:
        """코드 조각의 줄 번호 찾기"""
        try:
            index = full_code.index(snippet)
            return full_code[:index].count("\n") + 1
        except ValueError:
            return 0

    def _convert_advanced_error(self, vba_error: Dict[str, Any]) -> ExcelError:
        """AdvancedVBAAnalyzer 오류를 ExcelError로 변환"""
        return self._create_error(
            error_id=vba_error.get("id", ""),
            error_type=f"VBA {vba_error.get('category', 'Error')}",
            sheet=vba_error.get("module_name", "VBA"),
            cell=f"Line {vba_error.get('line_number', 0)}",
            message=vba_error.get("description", ""),
            severity=vba_error.get("severity", "medium"),
            is_auto_fixable=vba_error.get("auto_fixable", False),
            suggested_fix=vba_error.get("fix_suggestion", ""),
            formula=vba_error.get("code_snippet"),
            confidence=vba_error.get("confidence", 0.85),
        )
