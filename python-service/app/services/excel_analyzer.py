"""
Excel file analysis service
"""
import pandas as pd
import openpyxl
from typing import Dict, Any, List, Optional, Tuple
import re
from pathlib import Path
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class ExcelAnalyzer:
    """Service for analyzing Excel files"""
    
    def __init__(self):
        self.formula_pattern = re.compile(r'^=')
        self.error_patterns = {
            '#DIV/0!': 'Division by zero error',
            '#N/A': 'Value not available error',
            '#NAME?': 'Unrecognized formula name',
            '#NULL!': 'Null intersection error',
            '#NUM!': 'Invalid numeric value',
            '#REF!': 'Invalid cell reference',
            '#VALUE!': 'Wrong value type'
        }
    
    async def analyze_file(self, file_path: str) -> Dict[str, Any]:
        """Analyze an Excel file and extract metadata"""
        try:
            file_path = Path(file_path)
            
            # Basic file info
            file_info = {
                "filename": file_path.name,
                "size": file_path.stat().st_size,
                "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
            }
            
            # Load workbook for structure analysis
            workbook = openpyxl.load_workbook(file_path, read_only=True, data_only=False)
            
            sheets_info = {}
            total_formulas = 0
            total_errors = 0
            
            for sheet_name in workbook.sheetnames:
                sheet = workbook[sheet_name]
                sheet_analysis = await self._analyze_sheet(sheet)
                sheets_info[sheet_name] = sheet_analysis
                total_formulas += sheet_analysis.get("formula_count", 0)
                total_errors += len(sheet_analysis.get("errors", []))
            
            workbook.close()
            
            # Load with openpyxl for data extraction with formatting
            workbook_data = openpyxl.load_workbook(file_path, data_only=True)
            
            for sheet_name in workbook_data.sheetnames:
                sheet = workbook_data[sheet_name]
                sheets_info[sheet_name]["data"] = self._extract_sheet_data(sheet)
                sheets_info[sheet_name]["row_count"] = sheet.max_row
                sheets_info[sheet_name]["column_count"] = sheet.max_column
            
            workbook_data.close()
            
            return {
                "file_info": file_info,
                "sheets": sheets_info,
                "summary": {
                    "total_sheets": len(sheets_info),
                    "total_formulas": total_formulas,
                    "total_errors": total_errors,
                    "has_errors": total_errors > 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error analyzing Excel file: {str(e)}")
            raise
    
    async def _analyze_sheet(self, sheet) -> Dict[str, Any]:
        """Analyze a single sheet"""
        analysis = {
            "dimensions": f"{sheet.max_row}x{sheet.max_column}",
            "used_range": f"A1:{sheet.max_column_letter}{sheet.max_row}",
            "formulas": [],
            "errors": [],
            "formula_count": 0,
            "merged_cells": []
        }
        
        # Extract merged cell ranges
        for merged_range in sheet.merged_cells.ranges:
            analysis["merged_cells"].append(str(merged_range))
        
        # Extract column widths
        column_widths = {}
        for col in sheet.columns:
            col_letter = col[0].column_letter if col else None
            if col_letter and sheet.column_dimensions[col_letter].width:
                # Convert Excel width to pixels (approximately)
                width = sheet.column_dimensions[col_letter].width
                column_widths[col[0].column] = int(width * 7)  # Excel unit * 7 ≈ pixels
        analysis["column_widths"] = column_widths
        
        # Extract row heights
        row_heights = {}
        for row in sheet.rows:
            row_num = row[0].row if row else None
            if row_num and sheet.row_dimensions[row_num].height:
                height = sheet.row_dimensions[row_num].height
                row_heights[row_num] = int(height * 1.33)  # Points to pixels
        analysis["row_heights"] = row_heights
        
        # Sample the sheet (first 100 rows for performance)
        for row in sheet.iter_rows(max_row=min(100, sheet.max_row)):
            for cell in row:
                if cell.value is not None:
                    # Check for formulas
                    if isinstance(cell.value, str) and self.formula_pattern.match(cell.value):
                        analysis["formulas"].append({
                            "cell": cell.coordinate,
                            "formula": cell.value
                        })
                        analysis["formula_count"] += 1
                    
                    # Check for errors
                    if isinstance(cell.value, str):
                        for error, description in self.error_patterns.items():
                            if error in str(cell.value):
                                analysis["errors"].append({
                                    "cell": cell.coordinate,
                                    "error": error,
                                    "description": description
                                })
        
        # Limit stored formulas for response size
        if len(analysis["formulas"]) > 10:
            analysis["formulas"] = analysis["formulas"][:10]
            analysis["formulas_truncated"] = True
        
        return analysis
    
    def _extract_sheet_data(self, sheet) -> List[List[Dict[str, Any]]]:
        """Extract sheet data with cell formatting"""
        data = []
        
        for row_idx in range(1, sheet.max_row + 1):
            row_data = []
            for col_idx in range(1, sheet.max_column + 1):
                cell = sheet.cell(row=row_idx, column=col_idx)
                cell_data = {
                    "value": cell.value,
                    "address": cell.coordinate
                }
                
                # Add comprehensive style information
                style_data = {}
                
                # Font information
                if cell.font:
                    font_data = {
                        "bold": cell.font.bold,
                        "italic": cell.font.italic,
                        "size": cell.font.size,
                        "name": cell.font.name,
                        "underline": cell.font.underline,
                        "strike": cell.font.strike
                    }
                    
                    # Handle font color
                    if cell.font.color:
                        if cell.font.color.type == 'theme':
                            font_data["color"] = {
                                "theme": cell.font.color.theme,
                                "tint": cell.font.color.tint
                            }
                        elif cell.font.color.type == 'indexed':
                            font_data["color"] = {
                                "indexed": cell.font.color.indexed
                            }
                        elif cell.font.color.rgb:
                            font_data["color"] = {
                                "rgb": cell.font.color.rgb
                            }
                    
                    style_data["font"] = font_data
                
                # Fill information
                if cell.fill and cell.fill.patternType:
                    fill_data = {
                        "patternType": cell.fill.patternType
                    }
                    
                    # Foreground color
                    if cell.fill.fgColor:
                        if cell.fill.fgColor.type == 'theme':
                            fill_data["fgColor"] = {
                                "theme": cell.fill.fgColor.theme,
                                "tint": cell.fill.fgColor.tint
                            }
                        elif cell.fill.fgColor.type == 'indexed':
                            fill_data["fgColor"] = {
                                "indexed": cell.fill.fgColor.indexed
                            }
                        elif cell.fill.fgColor.rgb:
                            fill_data["fgColor"] = {
                                "rgb": cell.fill.fgColor.rgb
                            }
                    
                    # Background color
                    if cell.fill.bgColor:
                        if cell.fill.bgColor.type == 'theme':
                            fill_data["bgColor"] = {
                                "theme": cell.fill.bgColor.theme,
                                "tint": cell.fill.bgColor.tint
                            }
                        elif cell.fill.bgColor.type == 'indexed':
                            fill_data["bgColor"] = {
                                "indexed": cell.fill.bgColor.indexed
                            }
                        elif cell.fill.bgColor.rgb:
                            fill_data["bgColor"] = {
                                "rgb": cell.fill.bgColor.rgb
                            }
                    
                    style_data["fill"] = fill_data
                
                # Alignment information
                if cell.alignment:
                    style_data["alignment"] = {
                        "horizontal": cell.alignment.horizontal,
                        "vertical": cell.alignment.vertical,
                        "wrapText": cell.alignment.wrap_text,
                        "indent": cell.alignment.indent,
                        "textRotation": cell.alignment.text_rotation
                    }
                
                # Border information
                if cell.border:
                    border_data = {}
                    for side in ['top', 'bottom', 'left', 'right']:
                        border = getattr(cell.border, side)
                        if border and border.style:
                            border_info = {"style": border.style}
                            if border.color:
                                if border.color.type == 'theme':
                                    border_info["color"] = {
                                        "theme": border.color.theme,
                                        "tint": border.color.tint
                                    }
                                elif border.color.rgb:
                                    border_info["color"] = {
                                        "rgb": border.color.rgb
                                    }
                            border_data[side] = border_info
                    
                    if border_data:
                        style_data["border"] = border_data
                
                # Number format
                if cell.number_format and cell.number_format != 'General':
                    style_data["numberFormat"] = cell.number_format
                
                if style_data:
                    cell_data["style"] = style_data
                
                row_data.append(cell_data)
            data.append(row_data)
        
        return data
    
    def _analyze_dataframe(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze dataframe for data quality"""
        analysis = {
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": list(df.columns),
            "data_types": df.dtypes.astype(str).to_dict(),
            "missing_values": df.isnull().sum().to_dict(),
            "sample_data": self._get_sample_data(df)
        }
        
        # Detect potential issues
        issues = []
        
        # Check for high missing value percentages
        for col, missing in analysis["missing_values"].items():
            if missing > 0:
                missing_pct = (missing / len(df)) * 100
                if missing_pct > 50:
                    issues.append({
                        "type": "high_missing_values",
                        "column": col,
                        "percentage": round(missing_pct, 2)
                    })
        
        # Check for duplicate rows
        duplicate_count = df.duplicated().sum()
        if duplicate_count > 0:
            issues.append({
                "type": "duplicate_rows",
                "count": int(duplicate_count),
                "percentage": round((duplicate_count / len(df)) * 100, 2)
            })
        
        if issues:
            analysis["data_quality_issues"] = issues
        
        return analysis
    
    def _get_sample_data(self, df: pd.DataFrame, rows: int = 5) -> List[Dict]:
        """Get sample data from dataframe"""
        sample_df = df.head(rows)
        # Convert to dict and handle any non-serializable types
        return json.loads(sample_df.to_json(orient='records', date_format='iso'))
    
    async def extract_formulas(self, file_path: str) -> Dict[str, List[Dict]]:
        """Extract all formulas from an Excel file"""
        formulas_by_sheet = {}
        
        try:
            workbook = openpyxl.load_workbook(file_path, read_only=True, data_only=False)
            
            for sheet_name in workbook.sheetnames:
                sheet = workbook[sheet_name]
                formulas = []
                
                for row in sheet.iter_rows():
                    for cell in row:
                        if cell.value and isinstance(cell.value, str) and self.formula_pattern.match(cell.value):
                            formulas.append({
                                "cell": cell.coordinate,
                                "formula": cell.value,
                                "dependencies": self._extract_cell_references(cell.value)
                            })
                
                if formulas:
                    formulas_by_sheet[sheet_name] = formulas
            
            workbook.close()
            return formulas_by_sheet
            
        except Exception as e:
            logger.error(f"Error extracting formulas: {str(e)}")
            raise
    
    def _extract_cell_references(self, formula: str) -> List[str]:
        """Extract cell references from a formula"""
        # Pattern to match cell references like A1, $A$1, Sheet1!A1
        cell_pattern = r'(?:[\w\s]+!)?(?:\$?[A-Z]+\$?\d+)'
        references = re.findall(cell_pattern, formula)
        return list(set(references))  # Remove duplicates


# Create singleton instance
excel_analyzer = ExcelAnalyzer()