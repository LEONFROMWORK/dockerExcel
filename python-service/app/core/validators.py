"""
Input Validators
입력 검증 유틸리티 - 보안 및 데이터 무결성 보장
"""

import re
import os
from typing import Any, Optional, List, Dict
from pydantic import BaseModel, Field, validator
from app.core.config import settings

# 보안 패턴
DANGEROUS_PATTERNS = {
    "sql_injection": [
        r"(';|--;|\/\*|\*\/|@@|@)",
        r"(union|select|insert|update|delete|drop|create|alter|exec|execute)\s",
        r"(script|javascript|vbscript|onload|onerror|onclick)",
        r"(cmd|powershell|bash|sh|eval|exec)",
    ],
    "path_traversal": [
        r"\.\./",
        r"\.\.\\",
        r"%2e%2e%2f",
        r"%2e%2e%5c",
        r"\.\.%2f",
        r"\.\.%5c",
    ],
    "xss": [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe[^>]*>",
        r"<object[^>]*>",
        r"<embed[^>]*>",
    ],
}


class FileValidator:
    """파일 업로드 검증"""

    @staticmethod
    def validate_filename(filename: str) -> bool:
        """파일명 검증"""
        if not filename:
            return False

        # 위험한 문자 확인
        dangerous_chars = ["..", "/", "\\", "\x00", "\n", "\r", "\t"]
        for char in dangerous_chars:
            if char in filename:
                return False

        # 확장자 확인
        _, ext = os.path.splitext(filename)
        if ext.lower() not in settings.ALLOWED_EXTENSIONS:
            return False

        # 파일명 길이 제한
        if len(filename) > 255:
            return False

        return True

    @staticmethod
    def validate_file_size(size: int) -> bool:
        """파일 크기 검증"""
        return 0 < size <= settings.MAX_UPLOAD_SIZE

    @staticmethod
    def validate_mime_type(filename: str, content: bytes) -> bool:
        """MIME 타입 검증"""
        # 파일 시그니처 확인 (Magic Number)
        excel_signatures = {
            b"\x50\x4B\x03\x04": [".xlsx", ".xlsm"],  # ZIP format (Office 2007+)
            b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1": [".xls"],  # OLE format
        }

        for signature, extensions in excel_signatures.items():
            if content.startswith(signature):
                _, ext = os.path.splitext(filename)
                return ext.lower() in extensions

        return False


class CellAddressValidator:
    """셀 주소 검증"""

    # 유효한 셀 주소 패턴
    CELL_PATTERN = re.compile(r"^[A-Z]+[1-9]\d*$")
    RANGE_PATTERN = re.compile(r"^[A-Z]+[1-9]\d*:[A-Z]+[1-9]\d*$")

    @classmethod
    def validate_cell_address(cls, address: str) -> bool:
        """단일 셀 주소 검증"""
        if not address:
            return False

        address = address.upper().strip()

        # 시트명이 포함된 경우
        if "!" in address:
            parts = address.split("!")
            if len(parts) != 2:
                return False
            sheet_name, cell_ref = parts
            if not cls.validate_sheet_name(sheet_name):
                return False
            address = cell_ref

        return bool(cls.CELL_PATTERN.match(address))

    @classmethod
    def validate_range(cls, range_str: str) -> bool:
        """범위 검증"""
        if not range_str:
            return False

        range_str = range_str.upper().strip()

        # 시트명 처리
        if "!" in range_str:
            parts = range_str.split("!")
            if len(parts) != 2:
                return False
            range_str = parts[1]

        return bool(cls.RANGE_PATTERN.match(range_str))

    @staticmethod
    def validate_sheet_name(name: str) -> bool:
        """시트명 검증"""
        if not name:
            return False

        # 금지된 문자
        forbidden_chars = [":", "\\", "/", "?", "*", "[", "]"]
        for char in forbidden_chars:
            if char in name:
                return False

        # 길이 제한
        if len(name) > 31:
            return False

        return True


class FormulaValidator:
    """수식 검증"""

    # 허용된 Excel 함수
    ALLOWED_FUNCTIONS = {
        "SUM",
        "AVERAGE",
        "COUNT",
        "MAX",
        "MIN",
        "IF",
        "VLOOKUP",
        "HLOOKUP",
        "INDEX",
        "MATCH",
        "SUMIF",
        "COUNTIF",
        "AVERAGEIF",
        "CONCATENATE",
        "LEFT",
        "RIGHT",
        "MID",
        "LEN",
        "TRIM",
        "UPPER",
        "LOWER",
        "DATE",
        "TODAY",
        "NOW",
        "YEAR",
        "MONTH",
        "DAY",
        "HOUR",
        "MINUTE",
        "SECOND",
        "ROUND",
        "ROUNDUP",
        "ROUNDDOWN",
        "ABS",
        "SQRT",
        "POWER",
        "MOD",
        "AND",
        "OR",
        "NOT",
        "IFERROR",
        "ISBLANK",
        "ISERROR",
        "ISNUMBER",
    }

    @classmethod
    def validate_formula(cls, formula: str) -> bool:
        """수식 검증"""
        if not formula or not formula.startswith("="):
            return False

        # 위험한 함수 확인
        dangerous_functions = ["EXEC", "EVAL", "CALL", "REGISTER"]
        formula_upper = formula.upper()
        for func in dangerous_functions:
            if func in formula_upper:
                return False

        # 외부 참조 확인
        if any(char in formula for char in ["[", "]"]):
            # 외부 워크북 참조 차단
            return False

        # 매크로 함수 확인
        if "MACRO" in formula_upper or "RUN" in formula_upper:
            return False

        return True


class InputSanitizer:
    """입력 값 정제"""

    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """문자열 정제"""
        if not value:
            return ""

        # 길이 제한
        value = value[:max_length]

        # 제어 문자 제거
        value = "".join(char for char in value if ord(char) >= 32 or char in "\n\r\t")

        # HTML 이스케이프
        html_escape_table = {
            "&": "&amp;",
            '"': "&quot;",
            "'": "&#x27;",
            ">": "&gt;",
            "<": "&lt;",
        }
        value = "".join(html_escape_table.get(c, c) for c in value)

        return value.strip()

    @staticmethod
    def sanitize_number(
        value: Any, min_val: Optional[float] = None, max_val: Optional[float] = None
    ) -> Optional[float]:
        """숫자 정제"""
        try:
            num = float(value)

            # NaN, Infinity 확인
            if not (-float("inf") < num < float("inf")):
                return None

            # 범위 확인
            if min_val is not None and num < min_val:
                return min_val
            if max_val is not None and num > max_val:
                return max_val

            return num
        except (ValueError, TypeError):
            return None


# Pydantic 모델들
class SecureFileUpload(BaseModel):
    """보안 파일 업로드 모델"""

    filename: str = Field(..., min_length=1, max_length=255)
    size: int = Field(..., gt=0, le=settings.MAX_UPLOAD_SIZE)
    content_type: Optional[str] = None

    @validator("filename")
    def validate_filename(cls, v):
        if not FileValidator.validate_filename(v):
            raise ValueError("Invalid filename")
        return v

    @validator("content_type")
    def validate_content_type(cls, v):
        if v and not v.startswith(
            ("application/vnd.ms-excel", "application/vnd.openxmlformats")
        ):
            raise ValueError("Invalid content type for Excel file")
        return v


class SecureCellReference(BaseModel):
    """보안 셀 참조 모델"""

    address: str = Field(..., min_length=2, max_length=50)
    sheet: Optional[str] = Field(None, min_length=1, max_length=31)

    @validator("address")
    def validate_address(cls, v):
        if not CellAddressValidator.validate_cell_address(v):
            raise ValueError("Invalid cell address")
        return v.upper()

    @validator("sheet")
    def validate_sheet(cls, v):
        if v and not CellAddressValidator.validate_sheet_name(v):
            raise ValueError("Invalid sheet name")
        return v


class SecureFormulaRequest(BaseModel):
    """보안 수식 요청 모델"""

    formula: str = Field(..., min_length=2, max_length=5000)
    context: Optional[Dict[str, Any]] = None

    @validator("formula")
    def validate_formula(cls, v):
        if not FormulaValidator.validate_formula(v):
            raise ValueError("Invalid or dangerous formula")
        return v

    @validator("context")
    def validate_context(cls, v):
        if v:
            # 컨텍스트 크기 제한
            if len(str(v)) > 10000:
                raise ValueError("Context too large")
        return v


class SecureQueryRequest(BaseModel):
    """보안 쿼리 요청 모델"""

    query: str = Field(..., min_length=1, max_length=1000)
    filters: Optional[Dict[str, Any]] = None
    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @validator("query")
    def sanitize_query(cls, v):
        # SQL injection 패턴 확인
        for pattern in DANGEROUS_PATTERNS["sql_injection"]:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("Dangerous pattern detected in query")
        return InputSanitizer.sanitize_string(v)

    @validator("filters")
    def validate_filters(cls, v):
        if v:
            # 필터 키와 값 검증
            for key, value in v.items():
                if not re.match(r"^[a-zA-Z0-9_]+$", key):
                    raise ValueError(f"Invalid filter key: {key}")
                if isinstance(value, str) and len(value) > 100:
                    raise ValueError(f"Filter value too long: {key}")
        return v


class SecureAIPrompt(BaseModel):
    """보안 AI 프롬프트 모델"""

    prompt: str = Field(..., min_length=1, max_length=5000)
    session_id: Optional[str] = Field(None, pattern=r"^[a-zA-Z0-9\-_]+$")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1000, ge=1, le=4000)

    @validator("prompt")
    def sanitize_prompt(cls, v):
        # 프롬프트 인젝션 방지
        dangerous_prompts = [
            "ignore previous instructions",
            "disregard all prior",
            "system prompt",
            "you are now",
            "act as root",
            "sudo",
            "admin mode",
        ]

        v_lower = v.lower()
        for pattern in dangerous_prompts:
            if pattern in v_lower:
                raise ValueError("Potentially malicious prompt detected")

        return InputSanitizer.sanitize_string(v, max_length=5000)


class SecureBatchRequest(BaseModel):
    """보안 배치 요청 모델"""

    items: List[Dict[str, Any]] = Field(..., min_items=1, max_items=100)
    operation: str = Field(..., pattern=r"^[a-zA-Z_]+$")

    @validator("items")
    def validate_items(cls, v):
        # 각 아이템 검증
        for item in v:
            if len(str(item)) > 10000:
                raise ValueError("Item too large")
        return v


# 검증 헬퍼 함수들
def validate_request_path(path: str) -> bool:
    """요청 경로 검증"""
    # Path traversal 확인
    for pattern in DANGEROUS_PATTERNS["path_traversal"]:
        if re.search(pattern, path):
            return False

    # 절대 경로 확인
    if path.startswith("/") or ":" in path:
        return False

    return True


def validate_json_depth(data: Any, max_depth: int = 10, current_depth: int = 0) -> bool:
    """JSON 깊이 검증 (DoS 방지)"""
    if current_depth > max_depth:
        return False

    if isinstance(data, dict):
        for value in data.values():
            if not validate_json_depth(value, max_depth, current_depth + 1):
                return False
    elif isinstance(data, list):
        for item in data:
            if not validate_json_depth(item, max_depth, current_depth + 1):
                return False

    return True


def validate_session_id(session_id: str) -> bool:
    """세션 ID 검증"""
    if not session_id:
        return False

    # 형식 확인 (알파벳, 숫자, 하이픈, 언더스코어만 허용)
    if not re.match(r"^[a-zA-Z0-9\-_]{8,128}$", session_id):
        return False

    return True


def validate_api_key(api_key: str) -> bool:
    """API 키 검증"""
    if not api_key:
        return False

    # 길이 확인
    if len(api_key) < 32 or len(api_key) > 128:
        return False

    # 형식 확인
    if not re.match(r"^[a-zA-Z0-9\-_]+$", api_key):
        return False

    return True
