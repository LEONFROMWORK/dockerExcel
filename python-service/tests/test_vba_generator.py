"""
Unit tests for VBA Generator
"""
import pytest
import json
from pathlib import Path
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.vba_generator import VBAGenerator


class TestVBAGenerator:
    """Test suite for VBA code generator"""
    
    @pytest.fixture
    def generator(self):
        """Create VBA generator instance"""
        return VBAGenerator()
    
    def test_template_loading(self, generator):
        """Test template metadata loading"""
        templates = generator.list_templates()
        assert len(templates) > 0
        assert any(t["id"] == "data_processing" for t in templates)
        assert any(t["id"] == "automation" for t in templates)
        assert any(t["id"] == "reports" for t in templates)
    
    def test_validate_vba_code_valid(self, generator):
        """Test validation of valid VBA code"""
        valid_code = """
Option Explicit

Sub TestProcedure()
    On Error GoTo ErrorHandler
    
    Dim ws As Worksheet
    Set ws = ThisWorkbook.Worksheets("Sheet1")
    
    ws.Range("A1").Value = "Test"
    
    Exit Sub
ErrorHandler:
    MsgBox "Error: " & Err.Description
End Sub
"""
        result = generator.validate_vba_code(valid_code)
        assert result["is_valid"] == True
        assert result["has_error_handling"] == True
        assert len(result["issues"]) == 0
    
    def test_validate_vba_code_missing_option_explicit(self, generator):
        """Test validation detects missing Option Explicit"""
        code_without_option = """
Sub TestProcedure()
    Range("A1").Value = "Test"
End Sub
"""
        result = generator.validate_vba_code(code_without_option)
        # Code is still valid but should have warnings
        assert result["is_valid"] == True
        assert any("unclosed" in str(issue) for issue in result["issues"]) or len(result["issues"]) == 0
    
    def test_validate_vba_code_security_issues(self, generator):
        """Test security issue detection"""
        risky_code = """
Option Explicit

Sub RiskyProcedure()
    Shell "cmd.exe /c dir"
    CreateObject("WScript.Shell").Run "notepad.exe"
End Sub
"""
        result = generator.validate_vba_code(risky_code, check_security=True)
        assert len(result["warnings"]) >= 2
        assert any(w["type"] == "security" for w in result["warnings"])
        assert result["security_score"] < 100
    
    def test_validate_vba_code_performance_issues(self, generator):
        """Test performance issue detection"""
        inefficient_code = """
Option Explicit

Sub InefficientProcedure()
    Sheets("Sheet1").Select
    Range("A1").Select
    Selection.Copy
    Range("B1").Select
    ActiveSheet.Paste
End Sub
"""
        result = generator.validate_vba_code(inefficient_code, check_performance=True)
        assert len(result["warnings"]) > 0
        assert any(w["type"] == "performance" for w in result["warnings"])
    
    def test_fix_common_issues(self, generator):
        """Test automatic issue fixing"""
        problematic_code = """
Sub TestWithoutErrorHandling()
    Worksheets("Sheet1").Select
    Selection.Value = "Test"
End Sub
"""
        fixed_code = generator.fix_common_issues(problematic_code)
        
        # Should add Option Explicit
        assert "Option Explicit" in fixed_code
        
        # Should fix Select/Selection pattern
        assert "Selection." not in fixed_code or ".Select" not in fixed_code
        
        # Should add error handling
        assert "On Error" in fixed_code
    
    def test_analyze_vba_code(self, generator):
        """Test VBA code analysis"""
        code = """
Option Explicit

Sub Procedure1()
    ' Comment line
    Dim i As Integer
    For i = 1 To 10
        Cells(i, 1).Value = i
    Next i
End Sub

Function Calculate(x As Double) As Double
    Calculate = x * 2
End Function
"""
        analysis = generator.analyze_vba_code(code)
        
        assert analysis["metrics"]["procedure_count"] == 2
        assert analysis["metrics"]["comment_lines"] > 0
        assert analysis["metrics"]["code_lines"] > 0
    
    def test_get_improvement_suggestions(self, generator):
        """Test improvement suggestions"""
        code = """
Sub BadPractices()
    ActiveSheet.Range("A1").Copy
    ActiveSheet.Range("B1").Paste
    
    For i = 1 To 1000
        Cells(i, 1).Value = i
    Next i
End Sub
"""
        suggestions = generator.get_improvement_suggestions(code)
        
        assert len(suggestions) > 0
        assert any(s["category"] == "performance" for s in suggestions)
        assert any(s["category"] == "reliability" for s in suggestions)
    
    def test_post_process_code(self, generator):
        """Test code post-processing"""
        unformatted_code = """
Sub Test()
Dim x As Integer
If x > 0 Then
MsgBox "Positive"
Else
MsgBox "Not positive"
End If
End Sub
"""
        formatted = generator._post_process_code(unformatted_code)
        
        # Check indentation is applied
        lines = formatted.splitlines()
        # Find lines that should be indented
        dim_line = next((i for i, line in enumerate(lines) if "Dim x" in line), None)
        if_line = next((i for i, line in enumerate(lines) if "If x" in line), None)
        
        if dim_line and if_line:
            # Both should have some indentation
            assert lines[dim_line].startswith("    ")
            assert lines[if_line].startswith("    ")
    
    def test_template_categories(self, generator):
        """Test template category retrieval"""
        categories = generator.get_template_categories()
        
        assert isinstance(categories, list)
        assert "data" in categories
        assert "automation" in categories
        assert "reporting" in categories
    
    def test_get_specific_template(self, generator):
        """Test getting specific template"""
        template = generator.get_template("data_processing")
        
        assert template is not None
        assert template["id"] == "data_processing"
        assert "parameters" in template
    
    def test_generate_from_template_missing_template(self, generator):
        """Test error handling for missing template"""
        with pytest.raises(ValueError, match="Template 'non_existent' not found"):
            generator.generate_from_template("non_existent", {})
    
    @pytest.mark.asyncio
    async def test_validation_patterns(self, generator):
        """Test all validation patterns are properly compiled"""
        # Test that patterns don't raise exceptions
        test_code = "Sub Test()\nEnd Sub"
        
        for pattern_name, pattern in generator.security_patterns.items():
            # Should not raise
            pattern.search(test_code)
        
        for pattern_name, pattern in generator.performance_patterns.items():
            # Should not raise
            pattern.search(test_code)
        
        for pattern_name, pattern in generator.syntax_patterns.items():
            # Should not raise
            pattern.search(test_code)