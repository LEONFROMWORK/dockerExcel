"""
Unit tests for Advanced VBA Analyzer
"""

import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.advanced_vba_analyzer import (
    AdvancedVBAAnalyzer,
    VBAError,
    VBAModule,
    ErrorCategory,
    ErrorSeverity,
)


class TestAdvancedVBAAnalyzer:
    """Test suite for Advanced VBA Analyzer"""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance"""
        return AdvancedVBAAnalyzer()

    @pytest.fixture
    def sample_vba_code(self):
        """Sample VBA code with various error patterns"""
        return """
Option Explicit

Sub TestErrors()
    ' Runtime Error 1004 pattern
    Worksheets("NonExistent").Range("A1").Value = "Test"

    ' Runtime Error 91 pattern
    Dim ws As Worksheet
    Set ws = Nothing
    ws.Range("A1").Value = "Test"

    ' Security risk - Shell execution
    Shell "cmd.exe /c dir", vbNormalFocus

    ' Performance issue - Select/Activate
    Sheets("Sheet1").Select
    Range("A1").Select

    ' Nested loops
    Dim i As Integer, j As Integer, k As Integer
    For i = 1 To 100
        For j = 1 To 100
            For k = 1 To 100
                Cells(i, j).Value = k
            Next k
        Next j
    Next i
End Sub
"""

    @pytest.fixture
    def vba_module(self, sample_vba_code):
        """Create a VBA module for testing"""
        return VBAModule(
            name="TestModule",
            code=sample_vba_code,
            type="Module",
            size=len(sample_vba_code),
            hash="test_hash",
        )

    def test_error_pattern_detection(self, analyzer, vba_module):
        """Test detection of various error patterns"""
        errors = analyzer._detect_errors_in_module(vba_module)

        # Check that errors were detected
        assert len(errors) > 0

        # Check for specific error types
        error_types = {error.error_type for error in errors}
        assert "runtime_1004" in error_types
        assert "runtime_91" in error_types
        assert "shell_execution" in error_types
        assert "select_activate" in error_types
        assert "nested_loops" in error_types

        # Check severity levels
        critical_errors = [e for e in errors if e.severity == ErrorSeverity.CRITICAL]
        assert len(critical_errors) >= 2  # runtime_91 and shell_execution

    def test_missing_option_explicit_detection(self, analyzer):
        """Test detection of missing Option Explicit"""
        code_without_option = """
Sub TestSub()
    myVar = 100  ' Undeclared variable
End Sub
"""
        module = VBAModule(
            name="TestModule",
            code=code_without_option,
            type="Module",
            size=len(code_without_option),
            hash="test_hash",
        )

        errors = analyzer._detect_errors_in_module(module)

        # Should detect missing Option Explicit
        option_explicit_errors = [
            e for e in errors if e.error_type == "missing_option_explicit"
        ]
        assert len(option_explicit_errors) == 1
        assert option_explicit_errors[0].auto_fixable == True

    def test_suspicious_keyword_detection(self, analyzer, vba_module):
        """Test detection of suspicious keywords"""
        suspicious = analyzer._check_suspicious_keywords(vba_module)

        assert len(suspicious) > 0

        # Check for Shell detection
        shell_errors = [e for e in suspicious if "Shell" in e.description]
        assert len(shell_errors) > 0
        assert shell_errors[0].category == ErrorCategory.SECURITY

    def test_obfuscation_detection(self, analyzer):
        """Test detection of obfuscated code"""
        obfuscated_code = """
Sub ObfuscatedSub()
    Dim s As String
    s = Chr(72) & Chr(101) & Chr(108) & Chr(108) & Chr(111)  ' "Hello"
    s = StrReverse("dlroW olleH")
    s = "&H48656C6C6F"  ' Hex encoding
End Sub
"""
        module = VBAModule(
            name="ObfuscatedModule",
            code=obfuscated_code,
            type="Module",
            size=len(obfuscated_code),
            hash="test_hash",
        )

        obfuscation_errors = analyzer._check_obfuscation(module)
        assert len(obfuscation_errors) > 0

    @pytest.mark.asyncio
    async def test_file_analysis_without_vba(self, analyzer, tmp_path):
        """Test analysis of file without VBA"""
        # Create a simple text file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Simple text file")

        result = await analyzer.analyze_file(str(test_file))

        assert result["has_vba"] == False
        assert "No VBA code found" in result.get("message", "")

    @pytest.mark.asyncio
    @patch("app.services.advanced_vba_analyzer.VBA_Parser")
    async def test_oletools_integration(self, mock_parser_class, analyzer):
        """Test integration with oletools"""
        # Mock VBA_Parser instance
        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser

        # Configure mock
        mock_parser.detect_vba_macros.return_value = True
        mock_parser.extract_macros.return_value = [
            ("file.xlsm", "stream", "Module1", "Sub Test()\nEnd Sub"),
            ("file.xlsm", "stream", "Module2", "Function Calc()\nEnd Function"),
        ]

        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix=".xlsm", delete=False) as tmp:
            tmp.write(b"fake excel content")
            tmp_path = tmp.name

        try:
            modules = await analyzer._extract_vba_modules(tmp_path)

            assert len(modules) == 2
            assert modules[0].name == "Module1"
            assert modules[1].name == "Module2"
            assert mock_parser.close.called
        finally:
            os.unlink(tmp_path)

    def test_fix_generation(self, analyzer):
        """Test generation of fix suggestions"""
        errors = [
            VBAError(
                id="test_1",
                category=ErrorCategory.STYLE,
                severity=ErrorSeverity.MEDIUM,
                line_number=1,
                module_name="Module1",
                error_type="missing_option_explicit",
                description="Missing Option Explicit",
                code_snippet=None,
                fix_suggestion="Add Option Explicit",
                confidence=0.95,
                auto_fixable=True,
            ),
            VBAError(
                id="test_2",
                category=ErrorCategory.SECURITY,
                severity=ErrorSeverity.CRITICAL,
                line_number=10,
                module_name="Module1",
                error_type="shell_execution",
                description="Shell execution detected",
                code_snippet="Shell cmd",
                fix_suggestion="Review shell command",
                confidence=0.9,
                auto_fixable=False,
            ),
        ]

        fixes = analyzer._generate_fixes(errors)

        assert len(fixes) == 2

        # Check auto-fixable
        auto_fixes = [f for f in fixes if f["fix_type"] == "auto"]
        assert len(auto_fixes) == 1
        assert "Option Explicit" in auto_fixes[0]["code"]

        # Check manual fixes
        manual_fixes = [f for f in fixes if f["fix_type"] == "manual"]
        assert len(manual_fixes) == 1
        assert len(manual_fixes[0]["guidelines"]) > 0

    def test_security_score_calculation(self, analyzer):
        """Test security score calculation"""
        errors = [
            VBAError(
                id="1",
                category=ErrorCategory.SECURITY,
                severity=ErrorSeverity.CRITICAL,
                line_number=1,
                module_name="M1",
                error_type="shell",
                description="",
                code_snippet="",
                fix_suggestion="",
                confidence=0.9,
                auto_fixable=False,
            ),
            VBAError(
                id="2",
                category=ErrorCategory.SECURITY,
                severity=ErrorSeverity.HIGH,
                line_number=2,
                module_name="M1",
                error_type="file",
                description="",
                code_snippet="",
                fix_suggestion="",
                confidence=0.8,
                auto_fixable=False,
            ),
            VBAError(
                id="3",
                category=ErrorCategory.PERFORMANCE,
                severity=ErrorSeverity.LOW,
                line_number=3,
                module_name="M1",
                error_type="perf",
                description="",
                code_snippet="",
                fix_suggestion="",
                confidence=0.7,
                auto_fixable=True,
            ),
        ]

        impact = analyzer._calculate_security_impact(errors)
        assert impact == 30  # 20 (critical) + 10 (high)

    def test_summary_generation(self, analyzer):
        """Test summary generation"""
        errors = [
            VBAError(
                id="1",
                category=ErrorCategory.RUNTIME,
                severity=ErrorSeverity.CRITICAL,
                line_number=1,
                module_name="M1",
                error_type="runtime_91",
                description="Error 91",
                code_snippet="",
                fix_suggestion="",
                confidence=0.9,
                auto_fixable=False,
            ),
            VBAError(
                id="2",
                category=ErrorCategory.STYLE,
                severity=ErrorSeverity.LOW,
                line_number=2,
                module_name="M1",
                error_type="style",
                description="Style issue",
                code_snippet="",
                fix_suggestion="",
                confidence=0.8,
                auto_fixable=True,
            ),
        ]

        summary = analyzer._generate_summary(errors)

        assert summary["total_errors"] == 2
        assert summary["by_severity"]["critical"] == 1
        assert summary["by_severity"]["low"] == 1
        assert summary["by_category"]["runtime"] == 1
        assert summary["by_category"]["style"] == 1
        assert len(summary["critical_issues"]) == 1

    @pytest.mark.asyncio
    async def test_memory_cleanup(self, analyzer, tmp_path):
        """Test that resources are properly cleaned up"""
        # Create mock file
        test_file = tmp_path / "test.xlsm"
        test_file.write_bytes(b"fake excel content")

        with patch(
            "app.services.advanced_vba_analyzer.VBA_Parser"
        ) as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser_class.return_value = mock_parser

            # Simulate an error during parsing
            mock_parser.detect_vba_macros.side_effect = Exception("Parse error")

            await analyzer._extract_vba_modules(str(test_file))

            # Ensure close was still called despite error
            assert mock_parser.close.called

    def test_regex_pattern_compilation(self, analyzer):
        """Test that all regex patterns compile successfully"""
        for pattern_name, pattern_info in analyzer.error_patterns.items():
            try:
                import re

                re.compile(pattern_info["pattern"])
            except re.error as e:
                pytest.fail(f"Regex pattern '{pattern_name}' failed to compile: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
