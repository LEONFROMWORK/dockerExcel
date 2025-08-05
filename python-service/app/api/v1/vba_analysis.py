from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import Dict, Any
import tempfile
import os
import zipfile
import xml.etree.ElementTree as ET
import sys
import logging

# Add path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from services.advanced_vba_analyzer import AdvancedVBAAnalyzer

logger = logging.getLogger(__name__)
router = APIRouter()


class VBAAnalyzer:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.vba_modules = []
        self.analysis_result = {
            "has_vba": False,
            "modules": [],
            "macros": [],
            "potential_issues": [],
            "security_risks": [],
            "dependencies": [],
            "summary": {},
        }

    def analyze(self) -> Dict[str, Any]:
        """Analyze VBA content in Excel file"""
        try:
            # Excel files are actually zip archives
            with zipfile.ZipFile(self.file_path, "r") as zip_file:
                # Check for VBA project
                if "xl/vbaProject.bin" in zip_file.namelist():
                    self.analysis_result["has_vba"] = True
                    self._extract_vba_info(zip_file)
                else:
                    self.analysis_result["has_vba"] = False
                    return self.analysis_result

            # Analyze the VBA content
            self._analyze_vba_content()
            self._detect_security_risks()
            self._generate_summary()

        except Exception as e:
            self.analysis_result["error"] = str(e)

        return self.analysis_result

    def _extract_vba_info(self, zip_file):
        """Extract basic VBA information from Excel file"""
        # This is a simplified version - full VBA extraction requires
        # specialized libraries like oletools or win32com on Windows

        # Check for macro-enabled workbook indicators
        if "xl/workbook.xml" in zip_file.namelist():
            workbook_xml = zip_file.read("xl/workbook.xml")
            root = ET.fromstring(workbook_xml)

            # Look for defined names (often used in VBA)
            for elem in root.iter():
                if "definedName" in elem.tag:
                    self.analysis_result["dependencies"].append(
                        {"type": "defined_name", "name": elem.get("name", "Unknown")}
                    )

        # Add placeholder modules
        self.analysis_result["modules"] = [
            {
                "name": "VBAProject",
                "type": "project",
                "size": "Unknown",
                "has_code": True,
            }
        ]

    def _analyze_vba_content(self):
        """Analyze VBA content for patterns and issues"""
        # Common VBA patterns to look for
        risky_patterns = [
            ("Shell", "Executes external commands"),
            ("CreateObject", "Creates COM objects"),
            ("GetObject", "Gets COM objects"),
            ("Open.*For.*As", "File operations"),
            ("Kill", "Deletes files"),
            ("FileCopy", "Copies files"),
            ("Name.*As", "Renames files"),
            ("Environ", "Accesses environment variables"),
            ("SendKeys", "Simulates keyboard input"),
            ("Application.Run", "Runs external macros"),
        ]

        # Since we can't extract actual VBA without specialized tools,
        # we'll provide general recommendations
        self.analysis_result["potential_issues"] = [
            {
                "type": "info",
                "message": "Full VBA analysis requires specialized tools",
                "recommendation": "Use Excel's built-in VBA editor for detailed analysis",
            }
        ]

        # Add common macro types
        self.analysis_result["macros"] = [
            {
                "name": "Auto_Open",
                "type": "auto_exec",
                "description": "Runs automatically when workbook opens",
                "risk_level": "medium",
            },
            {
                "name": "Workbook_Open",
                "type": "event",
                "description": "Triggered when workbook opens",
                "risk_level": "medium",
            },
        ]

    def _detect_security_risks(self):
        """Detect potential security risks in VBA"""
        if self.analysis_result["has_vba"]:
            self.analysis_result["security_risks"] = [
                {
                    "risk": "Macro-enabled workbook",
                    "level": "medium",
                    "description": "This workbook contains VBA macros which could potentially be harmful",
                    "mitigation": "Only enable macros from trusted sources",
                },
                {
                    "risk": "Auto-execution possibility",
                    "level": "high",
                    "description": "Macros may run automatically when the workbook is opened",
                    "mitigation": "Open in Protected View first",
                },
            ]

    def _generate_summary(self):
        """Generate analysis summary"""
        self.analysis_result["summary"] = {
            "has_vba": self.analysis_result["has_vba"],
            "module_count": len(self.analysis_result["modules"]),
            "macro_count": len(self.analysis_result["macros"]),
            "risk_count": len(self.analysis_result["security_risks"]),
            "highest_risk": (
                "high" if self.analysis_result["security_risks"] else "none"
            ),
            "recommendations": [
                "Review all macros before enabling",
                "Use Excel's macro security settings",
                "Consider converting VBA to modern alternatives",
            ],
        }


@router.post("/analyze-vba")
async def analyze_vba(file: UploadFile = File(...)):
    """Analyze VBA content in an Excel file using Advanced VBA Analyzer"""
    # Security: Validate filename
    if (
        not file.filename
        or ".." in file.filename
        or "/" in file.filename
        or "\\" in file.filename
    ):
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Validate file extension
    allowed_extensions = (".xlsm", ".xlsb", ".xls", ".xlsx")
    if not file.filename.lower().endswith(allowed_extensions):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_extensions)}",
        )

    # Check file size (50MB limit)
    file_size = 0
    content = await file.read()
    file_size = len(content)
    if file_size > 50 * 1024 * 1024:  # 50MB
        raise HTTPException(
            status_code=413, detail="File too large. Maximum size is 50MB."
        )

    # Save uploaded file temporarily with secure filename
    safe_filename = os.path.basename(file.filename)
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=os.path.splitext(safe_filename)[1]
    ) as tmp_file:
        tmp_file.write(content)
        tmp_path = os.path.abspath(tmp_file.name)

    try:
        # Use Advanced VBA Analyzer with oletools
        advanced_analyzer = AdvancedVBAAnalyzer()
        result = await advanced_analyzer.analyze_file(tmp_path)

        # Fallback to basic analyzer if oletools fails
        if result.get("error") or not result.get("has_vba"):
            logger.info("Falling back to basic VBA analyzer")
            basic_analyzer = VBAAnalyzer(tmp_path)
            basic_result = basic_analyzer.analyze()
            # Merge results
            result.update(basic_result)

        return {"filename": file.filename, "analysis": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/extract-vba-code")
async def extract_vba_code(file: UploadFile = File(...)):
    """Extract VBA code from Excel file using oletools"""
    # Security: Validate filename
    if (
        not file.filename
        or ".." in file.filename
        or "/" in file.filename
        or "\\" in file.filename
    ):
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Validate file extension
    allowed_extensions = (".xlsm", ".xlsb", ".xls", ".xlsx")
    if not file.filename.lower().endswith(allowed_extensions):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_extensions)}",
        )

    # Check file size (50MB limit)
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50MB
        raise HTTPException(
            status_code=413, detail="File too large. Maximum size is 50MB."
        )

    # Save uploaded file temporarily with secure filename
    safe_filename = os.path.basename(file.filename)
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=os.path.splitext(safe_filename)[1]
    ) as tmp_file:
        tmp_file.write(content)
        tmp_path = os.path.abspath(tmp_file.name)

    try:
        # Extract VBA code using Advanced Analyzer
        analyzer = AdvancedVBAAnalyzer()
        modules = await analyzer._extract_vba_modules(tmp_path)

        if not modules:
            return {
                "status": "no_vba",
                "message": "No VBA code found in the file",
                "modules": [],
            }

        # Convert modules to response format
        extracted_modules = []
        for module in modules:
            extracted_modules.append(
                {
                    "name": module.name,
                    "type": module.type,
                    "code": module.code,
                    "size": module.size,
                    "line_count": len(module.code.split("\n")),
                }
            )

        return {
            "status": "success",
            "message": f"Extracted {len(modules)} VBA modules",
            "modules": extracted_modules,
        }

    except Exception as e:
        logger.error(f"VBA extraction failed: {str(e)}")
        return {"status": "error", "message": str(e), "modules": []}
    finally:
        # Clean up
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/suggest-vba-improvements")
async def suggest_vba_improvements(
    vba_description: str, improvement_type: str = "performance"
):
    """Suggest improvements for VBA code based on description"""
    suggestions = {
        "performance": [
            "Use 'Application.ScreenUpdating = False' to speed up macro execution",
            "Avoid selecting/activating objects - work with them directly",
            "Use arrays instead of repeatedly accessing cells",
            "Turn off automatic calculation during macro execution",
            "Use 'With' statements for repeated object references",
        ],
        "security": [
            "Avoid using 'Shell' or 'CreateObject' for external commands",
            "Implement error handling with 'On Error' statements",
            "Validate all user inputs before processing",
            "Use explicit variable declarations with 'Option Explicit'",
            "Avoid hardcoded passwords or sensitive data",
        ],
        "maintainability": [
            "Use meaningful variable and function names",
            "Add comments to explain complex logic",
            "Break large procedures into smaller functions",
            "Use constants for values that don't change",
            "Implement proper error handling and logging",
        ],
        "modernization": [
            "Consider migrating to Office Scripts for web compatibility",
            "Use Power Query for data transformation tasks",
            "Leverage Power Automate for workflow automation",
            "Consider Python with openpyxl for complex operations",
            "Use Excel's built-in functions instead of VBA where possible",
        ],
    }

    selected_suggestions = suggestions.get(improvement_type, suggestions["performance"])

    return {
        "improvement_type": improvement_type,
        "suggestions": selected_suggestions,
        "general_tips": [
            "Always test macros in a copy of your workbook first",
            "Document your VBA code for future maintenance",
            "Consider code signing for trusted macros",
            "Regular backup your macro-enabled workbooks",
        ],
    }
