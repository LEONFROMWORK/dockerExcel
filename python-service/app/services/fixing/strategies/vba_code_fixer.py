"""
VBA Code Fixer
VBA 코드 오류 수정 전략 - IErrorFixStrategy 구현
"""

from typing import Dict, Any, Optional
from app.core.interfaces import IErrorFixStrategy, ExcelError, FixResult
import re
import logging

logger = logging.getLogger(__name__)


class VBACodeFixer(IErrorFixStrategy):
    """VBA 코드 오류 수정 전략"""

    def __init__(self):
        # 수정 가능한 VBA 오류 타입
        self.fixable_error_types = {
            "missing_option_explicit",
            "missing_error_handling",
            "select_activate",
            "unhandled_object",
            "hardcoded_path",
            "deprecated_function",
            "undeclared_variable",
        }

        # 수정 템플릿
        self.fix_templates = self._init_fix_templates()

        # 수정 패턴
        self.fix_patterns = self._init_fix_patterns()

    def can_handle(self, error: ExcelError) -> bool:
        """이 전략이 처리할 수 있는 오류인지 확인"""
        # VBA 관련 오류이고 수정 가능한 타입인지 확인
        if "vba" in error.type.lower():
            error_subtype = self._extract_error_subtype(error.type)
            return error_subtype in self.fixable_error_types
        return False

    async def apply_fix(
        self, error: ExcelError, context: Optional[Dict[str, Any]] = None
    ) -> FixResult:
        """오류 수정 적용"""
        try:
            error_subtype = self._extract_error_subtype(error.type)

            # 오류 타입별 수정 처리
            if error_subtype == "missing_option_explicit":
                return await self._fix_missing_option_explicit(error, context)
            elif error_subtype == "missing_error_handling":
                return await self._fix_missing_error_handling(error, context)
            elif error_subtype == "select_activate":
                return await self._fix_select_activate(error, context)
            elif error_subtype == "unhandled_object":
                return await self._fix_unhandled_object(error, context)
            elif error_subtype == "hardcoded_path":
                return await self._fix_hardcoded_path(error, context)
            elif error_subtype == "deprecated_function":
                return await self._fix_deprecated_function(error, context)
            elif error_subtype == "undeclared_variable":
                return await self._fix_undeclared_variable(error, context)
            else:
                return self._create_failed_result(
                    error, "지원하지 않는 VBA 오류 타입입니다"
                )

        except Exception as e:
            logger.error(f"VBA 수정 중 오류 발생: {str(e)}")
            return self._create_failed_result(error, str(e))

    def get_confidence(self, error: ExcelError) -> float:
        """수정 신뢰도 반환"""
        error_subtype = self._extract_error_subtype(error.type)

        # 오류 타입별 신뢰도
        confidence_map = {
            "missing_option_explicit": 0.95,
            "missing_error_handling": 0.85,
            "select_activate": 0.90,
            "unhandled_object": 0.80,
            "hardcoded_path": 0.70,
            "deprecated_function": 0.75,
            "undeclared_variable": 0.85,
        }

        return confidence_map.get(error_subtype, 0.5)

    # === 개별 오류 수정 메서드 ===

    async def _fix_missing_option_explicit(
        self, error: ExcelError, context: Optional[Dict[str, Any]]
    ) -> FixResult:
        """Option Explicit 누락 수정"""
        module_code = context.get("module_code", "") if context else ""

        # 모듈 최상단에 Option Explicit 추가
        fixed_code = "Option Explicit\n\n" + module_code

        return FixResult(
            success=True,
            error_id=error.id,
            original_formula=module_code[:100] + "...",  # 처음 100자만
            fixed_formula=fixed_code[:100] + "...",
            confidence=0.95,
            applied=False,
            message="Option Explicit 추가됨",
        )

    async def _fix_missing_error_handling(
        self, error: ExcelError, context: Optional[Dict[str, Any]]
    ) -> FixResult:
        """에러 처리 누락 수정"""
        procedure_code = error.formula or ""

        # 프로시저에 에러 처리 추가
        fixed_code = self._add_error_handling(procedure_code)

        return FixResult(
            success=True,
            error_id=error.id,
            original_formula=procedure_code,
            fixed_formula=fixed_code,
            confidence=0.85,
            applied=False,
            message="에러 처리 코드 추가됨",
        )

    async def _fix_select_activate(
        self, error: ExcelError, context: Optional[Dict[str, Any]]
    ) -> FixResult:
        """Select/Activate 제거"""
        code_line = error.formula or ""

        # Select/Activate 패턴을 직접 참조로 변경
        fixed_line = self._remove_select_activate(code_line)

        return FixResult(
            success=True,
            error_id=error.id,
            original_formula=code_line,
            fixed_formula=fixed_line,
            confidence=0.90,
            applied=False,
            message="Select/Activate 제거 및 직접 참조로 변경",
        )

    async def _fix_unhandled_object(
        self, error: ExcelError, context: Optional[Dict[str, Any]]
    ) -> FixResult:
        """처리되지 않은 객체 수정"""
        code_snippet = error.formula or ""
        object_name = self._extract_object_name(code_snippet)

        # Set 객체 = Nothing 추가
        fixed_code = f"{code_snippet}\n    ' 객체 정리\n    Set {object_name} = Nothing"

        return FixResult(
            success=True,
            error_id=error.id,
            original_formula=code_snippet,
            fixed_formula=fixed_code,
            confidence=0.80,
            applied=False,
            message=f"객체 정리 코드 추가: Set {object_name} = Nothing",
        )

    async def _fix_hardcoded_path(
        self, error: ExcelError, context: Optional[Dict[str, Any]]
    ) -> FixResult:
        """하드코딩된 경로 수정"""
        code_line = error.formula or ""
        hardcoded_path = self._extract_hardcoded_path(code_line)

        if hardcoded_path:
            # 설정 시트 참조로 변경
            fixed_line = code_line.replace(
                hardcoded_path,
                'ThisWorkbook.Worksheets("Settings").Range("FilePath").Value',
            )

            return FixResult(
                success=True,
                error_id=error.id,
                original_formula=code_line,
                fixed_formula=fixed_line,
                confidence=0.70,
                applied=False,
                message="하드코딩된 경로를 설정 시트 참조로 변경",
            )

        return self._create_failed_result(error, "하드코딩된 경로를 찾을 수 없습니다")

    async def _fix_deprecated_function(
        self, error: ExcelError, context: Optional[Dict[str, Any]]
    ) -> FixResult:
        """사용 중지된 함수 수정"""
        code_line = error.formula or ""

        # 대체 함수 매핑
        replacements = {
            "Application.FileSearch": "// Dir() 함수 사용 권장",
            "Application.Assistant": "// 제거됨 - 대체 기능 없음",
            "DoEvents": 'Application.Wait (Now + TimeValue("0:00:01"))',
        }

        fixed_line = code_line
        for old, new in replacements.items():
            if old in code_line:
                fixed_line = code_line.replace(old, new)
                break

        return FixResult(
            success=True,
            error_id=error.id,
            original_formula=code_line,
            fixed_formula=fixed_line,
            confidence=0.75,
            applied=False,
            message="사용 중지된 함수를 최신 대체 함수로 변경",
        )

    async def _fix_undeclared_variable(
        self, error: ExcelError, context: Optional[Dict[str, Any]]
    ) -> FixResult:
        """선언되지 않은 변수 수정"""
        variable_name = self._extract_variable_name(error.message)

        if variable_name:
            # 변수 선언 추가
            declaration = f"Dim {variable_name} As Variant"

            return FixResult(
                success=True,
                error_id=error.id,
                original_formula="",
                fixed_formula=declaration,
                confidence=0.85,
                applied=False,
                message=f"변수 선언 추가: {declaration}",
            )

        return self._create_failed_result(error, "변수명을 추출할 수 없습니다")

    # === 헬퍼 메서드 ===

    def _init_fix_templates(self) -> Dict[str, str]:
        """수정 템플릿 초기화"""
        return {
            "error_handler": """On Error GoTo ErrorHandler

    ' 기존 코드
    {original_code}

    Exit Sub
ErrorHandler:
    MsgBox "Error " & Err.Number & ": " & Err.Description
    Resume Next""",
            "object_cleanup": """    ' 객체 정리
    If Not {object_name} Is Nothing Then
        Set {object_name} = Nothing
    End If""",
        }

    def _init_fix_patterns(self) -> Dict[str, re.Pattern]:
        """수정 패턴 초기화"""
        return {
            "select_activate": re.compile(r"(\w+)\.Select\s*\n\s*Selection\.(\w+)"),
            "object_set": re.compile(r"Set\s+(\w+)\s*="),
            "hardcoded_path": re.compile(r'["\']([A-Za-z]:[\\\/][^"\']+)["\']'),
            "variable_assignment": re.compile(r"\b(\w+)\s*="),
        }

    def _extract_error_subtype(self, error_type: str) -> str:
        """오류 타입에서 서브타입 추출"""
        # 예: "VBA Best Practice Violation" -> "missing_option_explicit"
        error_lower = error_type.lower()

        if "option explicit" in error_lower:
            return "missing_option_explicit"
        elif "error handling" in error_lower:
            return "missing_error_handling"
        elif "select" in error_lower or "activate" in error_lower:
            return "select_activate"
        elif "object" in error_lower and "nothing" in error_lower:
            return "unhandled_object"
        elif "hardcoded" in error_lower or "path" in error_lower:
            return "hardcoded_path"
        elif "deprecated" in error_lower:
            return "deprecated_function"
        elif "undeclared" in error_lower or "variable" in error_lower:
            return "undeclared_variable"

        return "unknown"

    def _add_error_handling(self, procedure_code: str) -> str:
        """프로시저에 에러 처리 추가"""
        # 프로시저 시작 부분 찾기
        lines = procedure_code.split("\n")

        # Sub/Function 선언 다음 줄에 에러 처리 추가
        for i, line in enumerate(lines):
            if re.match(r"^\s*(?:Sub|Function)\s+", line, re.IGNORECASE):
                lines.insert(i + 1, "    On Error GoTo ErrorHandler")
                break

        # Exit Sub/Function 전에 에러 핸들러 추가
        for i in range(len(lines) - 1, -1, -1):
            if re.match(r"^\s*End\s+(?:Sub|Function)", lines[i], re.IGNORECASE):
                error_handler = [
                    "",
                    "ErrorHandler:",
                    "    If Err.Number <> 0 Then",
                    '        MsgBox "Error " & Err.Number & ": " & Err.Description',
                    "        Resume Next",
                    "    End If",
                ]
                lines[i:i] = error_handler
                break

        return "\n".join(lines)

    def _remove_select_activate(self, code_line: str) -> str:
        """Select/Activate 제거"""
        # 패턴: Object.Select -> Selection.Method
        match = self.fix_patterns["select_activate"].search(code_line)
        if match:
            return f"{match.group(1)}.{match.group(2)}"

        # 단순 Select/Activate 제거
        return re.sub(r"\.(Select|Activate)\s*$", "", code_line)

    def _extract_object_name(self, code_snippet: str) -> Optional[str]:
        """코드에서 객체명 추출"""
        match = self.fix_patterns["object_set"].search(code_snippet)
        return match.group(1) if match else None

    def _extract_hardcoded_path(self, code_line: str) -> Optional[str]:
        """하드코딩된 경로 추출"""
        match = self.fix_patterns["hardcoded_path"].search(code_line)
        return match.group(0) if match else None

    def _extract_variable_name(self, error_message: str) -> Optional[str]:
        """오류 메시지에서 변수명 추출"""
        # 예: "선언되지 않은 변수 사용: myVar"
        match = re.search(r"변수.*:\s*(\w+)", error_message)
        if match:
            return match.group(1)

        # 영문 메시지
        match = re.search(r"variable.*:\s*(\w+)", error_message, re.IGNORECASE)
        return match.group(1) if match else None

    def _create_failed_result(self, error: ExcelError, message: str) -> FixResult:
        """실패 결과 생성"""
        return FixResult(
            success=False,
            error_id=error.id,
            original_formula=error.formula or "",
            fixed_formula="",
            confidence=0.0,
            applied=False,
            message=message,
        )
