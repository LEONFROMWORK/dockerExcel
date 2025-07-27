"""
VBA Code Generator Service
Handles template-based and AI-assisted VBA code generation
"""
import os
import re
import json
from typing import Dict, Any, List, Optional, Tuple
from jinja2 import Environment, FileSystemLoader, Template
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class VBAGenerator:
    """VBA code generation and validation service"""
    
    def __init__(self):
        # Initialize template engine
        template_dir = Path(__file__).parent.parent / "templates" / "vba"
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Load template metadata
        self.templates = self._load_template_metadata()
        
        # Initialize validation patterns
        self._init_validation_patterns()
        
    def _load_template_metadata(self) -> Dict[str, Any]:
        """Load VBA template metadata"""
        metadata_path = Path(__file__).parent.parent / "templates" / "vba" / "metadata.json"
        try:
            if metadata_path.exists():
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # Default templates if metadata file doesn't exist
                return {
                    "data_processing": {
                        "id": "data_processing",
                        "name": "Data Processing",
                        "description": "Template for data manipulation and analysis",
                        "category": "data",
                        "parameters": ["worksheet_name", "data_range", "output_range"]
                    },
                    "automation": {
                        "id": "automation",
                        "name": "Task Automation",
                        "description": "Template for automating repetitive tasks",
                        "category": "automation",
                        "parameters": ["task_name", "frequency", "conditions"]
                    },
                    "reports": {
                        "id": "reports",
                        "name": "Report Generation",
                        "description": "Template for creating reports",
                        "category": "reporting",
                        "parameters": ["report_name", "data_sources", "format"]
                    }
                }
        except Exception as e:
            logger.error(f"Error loading template metadata: {e}")
            return {}
    
    def _init_validation_patterns(self):
        """Initialize patterns for code validation"""
        # Security risk patterns
        self.security_patterns = {
            'shell_execution': re.compile(r'Shell\s*\(', re.IGNORECASE),
            'file_system': re.compile(r'CreateObject\s*\(\s*["\']Scripting\.FileSystemObject', re.IGNORECASE),
            'wscript': re.compile(r'CreateObject\s*\(\s*["\']WScript\.Shell', re.IGNORECASE),
            'registry': re.compile(r'RegRead|RegWrite|RegDelete', re.IGNORECASE),
            'external_data': re.compile(r'ADODB\.|XMLHttp|InternetExplorer\.Application', re.IGNORECASE)
        }
        
        # Performance issue patterns
        self.performance_patterns = {
            'select_activate': re.compile(r'\.Select\s*\n.*?\.Activate|\.Activate\s*\n.*?\.Select', re.IGNORECASE),
            'redundant_select': re.compile(r'\.Select\s*\n\s*Selection\.', re.IGNORECASE),
            'nested_loops_cells': re.compile(r'For.*?\n.*?For.*?\n.*?Cells\(', re.IGNORECASE | re.DOTALL),
            'copy_paste': re.compile(r'\.Copy\s*\n.*?\.Paste(?!Special)', re.IGNORECASE)
        }
        
        # Syntax patterns
        self.syntax_patterns = {
            'unclosed_blocks': re.compile(r'(If|For|While|With|Sub|Function)(?!.*?End\s*\1)', re.IGNORECASE),
            'undeclared_variables': re.compile(r'(?<!Dim\s)(?<!Set\s)(\w+)\s*=(?!=)', re.IGNORECASE),
            'missing_error_handling': re.compile(r'Sub\s+\w+.*?End\s+Sub(?!.*?On\s+Error)', re.IGNORECASE | re.DOTALL)
        }
    
    def generate_from_template(self, template_id: str, parameters: Dict[str, Any]) -> str:
        """Generate VBA code from a template"""
        try:
            # Get template
            template_info = self.templates.get(template_id)
            if not template_info:
                raise ValueError(f"Template '{template_id}' not found")
            
            # Load template file
            template = self.env.get_template(f"{template_id}.vba.j2")
            
            # Add common utilities to parameters
            parameters['error_handling'] = self._get_error_handling_code()
            parameters['common_functions'] = self._get_common_functions()
            
            # Generate code
            vba_code = template.render(**parameters)
            
            # Post-process
            vba_code = self._post_process_code(vba_code)
            
            return vba_code
            
        except Exception as e:
            logger.error(f"Template generation error: {e}")
            raise
    
    def validate_vba_code(self, vba_code: str, check_security: bool = True, 
                         check_performance: bool = True) -> Dict[str, Any]:
        """Validate VBA code for issues"""
        issues = []
        warnings = []
        
        # Check for syntax issues
        for pattern_name, pattern in self.syntax_patterns.items():
            if pattern.search(vba_code):
                issues.append({
                    "type": "syntax",
                    "severity": "error",
                    "description": f"Syntax issue: {pattern_name.replace('_', ' ')}"
                })
        
        # Check for security issues
        if check_security:
            for pattern_name, pattern in self.security_patterns.items():
                if pattern.search(vba_code):
                    warnings.append({
                        "type": "security",
                        "severity": "warning",
                        "description": f"Security risk: {pattern_name.replace('_', ' ')}"
                    })
        
        # Check for performance issues
        if check_performance:
            for pattern_name, pattern in self.performance_patterns.items():
                if pattern.search(vba_code):
                    warnings.append({
                        "type": "performance",
                        "severity": "warning",
                        "description": f"Performance issue: {pattern_name.replace('_', ' ')}"
                    })
        
        # Calculate security score
        security_score = 100
        if check_security:
            security_score -= len([w for w in warnings if w["type"] == "security"]) * 20
            security_score = max(0, security_score)
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "security_score": security_score,
            "line_count": len(vba_code.splitlines()),
            "has_error_handling": bool(re.search(r'On\s+Error', vba_code, re.IGNORECASE))
        }
    
    def fix_common_issues(self, vba_code: str) -> str:
        """Fix common VBA code issues"""
        fixed_code = vba_code
        
        # Add Option Explicit if missing
        if not re.search(r'Option\s+Explicit', fixed_code, re.IGNORECASE):
            fixed_code = "Option Explicit\n\n" + fixed_code
        
        # Replace Select/Activate patterns
        fixed_code = re.sub(
            r'(\w+)\.Select\s*\n\s*Selection\.',
            r'\1.',
            fixed_code,
            flags=re.IGNORECASE
        )
        
        # Add basic error handling to Subs without it
        def add_error_handling(match):
            sub_declaration = match.group(1)
            sub_body = match.group(2)
            if not re.search(r'On\s+Error', sub_body, re.IGNORECASE):
                return f"{sub_declaration}\n    On Error GoTo ErrorHandler\n{sub_body}\nErrorHandler:\n    If Err.Number <> 0 Then\n        MsgBox \"Error: \" & Err.Description, vbCritical\n    End If\nEnd Sub"
            return match.group(0)
        
        fixed_code = re.sub(
            r'(Sub\s+\w+\(.*?\))\s*\n(.*?)\nEnd\s+Sub',
            add_error_handling,
            fixed_code,
            flags=re.IGNORECASE | re.DOTALL
        )
        
        return fixed_code
    
    def analyze_vba_code(self, vba_code: str) -> Dict[str, Any]:
        """Analyze VBA code for improvements"""
        analysis = {
            "issues": [],
            "suggestions": [],
            "metrics": {}
        }
        
        # Basic metrics
        lines = vba_code.splitlines()
        analysis["metrics"]["total_lines"] = len(lines)
        analysis["metrics"]["code_lines"] = len([l for l in lines if l.strip() and not l.strip().startswith("'")])
        analysis["metrics"]["comment_lines"] = len([l for l in lines if l.strip().startswith("'")])
        
        # Count procedures
        procedures = re.findall(r'(?:Sub|Function)\s+(\w+)', vba_code, re.IGNORECASE)
        analysis["metrics"]["procedure_count"] = len(procedures)
        
        # Check for common issues
        if not re.search(r'Option\s+Explicit', vba_code, re.IGNORECASE):
            analysis["issues"].append("Missing Option Explicit")
            analysis["suggestions"].append("Add 'Option Explicit' at the beginning")
        
        if re.search(r'\.Select.*?\.Activate|\.Activate.*?\.Select', vba_code, re.IGNORECASE | re.DOTALL):
            analysis["issues"].append("Using Select/Activate pattern")
            analysis["suggestions"].append("Replace Select/Activate with direct object references")
        
        if not re.search(r'On\s+Error', vba_code, re.IGNORECASE):
            analysis["issues"].append("No error handling")
            analysis["suggestions"].append("Add error handling to all procedures")
        
        # Check for hard-coded values
        hard_coded = re.findall(r'["\'][\w\s]{10,}["\']', vba_code)
        if hard_coded:
            analysis["issues"].append(f"Found {len(hard_coded)} hard-coded strings")
            analysis["suggestions"].append("Consider using constants or configuration")
        
        return analysis
    
    def get_improvement_suggestions(self, vba_code: str) -> List[Dict[str, str]]:
        """Get specific improvement suggestions for VBA code"""
        suggestions = []
        
        # Performance suggestions
        if re.search(r'\.Copy.*?\.Paste(?!Special)', vba_code, re.IGNORECASE | re.DOTALL):
            suggestions.append({
                "category": "performance",
                "suggestion": "Use direct value assignment instead of Copy/Paste",
                "example": "Range(\"B1:B10\").Value = Range(\"A1:A10\").Value"
            })
        
        if re.search(r'For.*?Cells\(.*?\)\.Value', vba_code, re.IGNORECASE | re.DOTALL):
            suggestions.append({
                "category": "performance",
                "suggestion": "Use array operations instead of cell-by-cell loops",
                "example": "Dim arr As Variant\narr = Range(\"A1:A100\").Value\n' Process arr\nRange(\"A1:A100\").Value = arr"
            })
        
        # Best practices
        if not re.search(r'Const\s+\w+', vba_code, re.IGNORECASE):
            suggestions.append({
                "category": "maintainability",
                "suggestion": "Define constants for magic numbers and strings",
                "example": "Const MAX_ROWS As Long = 1000\nConst SHEET_NAME As String = \"Data\""
            })
        
        if re.search(r'ActiveSheet|ActiveWorkbook', vba_code, re.IGNORECASE):
            suggestions.append({
                "category": "reliability",
                "suggestion": "Avoid using ActiveSheet/ActiveWorkbook",
                "example": "Dim ws As Worksheet\nSet ws = ThisWorkbook.Worksheets(\"Sheet1\")"
            })
        
        return suggestions
    
    def _get_error_handling_code(self) -> str:
        """Get standard error handling code"""
        return """
'Standard error handling
On Error GoTo ErrorHandler
    
    ' Your code here
    
    Exit Sub
ErrorHandler:
    MsgBox "Error " & Err.Number & ": " & Err.Description, vbCritical
    ' Optional: Log error to worksheet
    ' LogError Err.Number, Err.Description, "ProcedureName"
"""
    
    def _get_common_functions(self) -> str:
        """Get common utility functions"""
        return """
'Common utility functions
Function WorksheetExists(wsName As String) As Boolean
    Dim ws As Worksheet
    On Error Resume Next
    Set ws = ThisWorkbook.Worksheets(wsName)
    WorksheetExists = Not ws Is Nothing
    On Error GoTo 0
End Function

Function GetLastRow(ws As Worksheet, col As Long) As Long
    GetLastRow = ws.Cells(ws.Rows.Count, col).End(xlUp).Row
End Function

Function GetLastColumn(ws As Worksheet, row As Long) As Long
    GetLastColumn = ws.Cells(row, ws.Columns.Count).End(xlToLeft).Column
End Function
"""
    
    def _post_process_code(self, vba_code: str) -> str:
        """Post-process generated VBA code"""
        # Remove extra blank lines
        vba_code = re.sub(r'\n\s*\n\s*\n', '\n\n', vba_code)
        
        # Ensure proper indentation
        lines = vba_code.splitlines()
        processed_lines = []
        indent_level = 0
        
        for line in lines:
            stripped = line.strip()
            
            # Decrease indent for End statements
            if stripped.startswith(('End ', 'Next', 'Loop', 'Wend', 'Else', 'ElseIf', 'Case')):
                indent_level = max(0, indent_level - 1)
            
            # Add indented line
            if stripped:
                processed_lines.append('    ' * indent_level + stripped)
            else:
                processed_lines.append('')
            
            # Increase indent for block statements
            if stripped.startswith(('Sub ', 'Function ', 'If ', 'For ', 'Do ', 'While ', 'With ', 'Select Case')):
                if not stripped.endswith('_'):  # Not a line continuation
                    indent_level += 1
            elif stripped.startswith(('Else', 'ElseIf', 'Case')):
                indent_level += 1
        
        return '\n'.join(processed_lines)
    
    def list_templates(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available templates"""
        templates = []
        for template_id, template_info in self.templates.items():
            if category is None or template_info.get("category") == category:
                templates.append({
                    "id": template_id,
                    "name": template_info.get("name", template_id),
                    "description": template_info.get("description", ""),
                    "category": template_info.get("category", "general"),
                    "parameters": template_info.get("parameters", [])
                })
        return templates
    
    def get_template_categories(self) -> List[str]:
        """Get all available template categories"""
        categories = set()
        for template_info in self.templates.values():
            if "category" in template_info:
                categories.add(template_info["category"])
        return sorted(list(categories))
    
    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific template"""
        return self.templates.get(template_id)