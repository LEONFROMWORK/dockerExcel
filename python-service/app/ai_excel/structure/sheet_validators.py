"""
Sheet validators - specialized validators for sheet components
"""

from typing import Dict, List, Any
from .excel_schema import SheetSchema, ColumnDefinition, FormulaDefinition, ChartSpecification


class SheetNameValidator:
    """Validates sheet names according to Excel rules"""
    
    def validate(self, name: str) -> Dict[str, Any]:
        """Validate sheet name"""
        results = {"valid": True, "errors": []}
        
        # Check length
        if len(name) > 31:
            results["errors"].append(f"Sheet name '{name}' exceeds 31 characters")
            results["valid"] = False
        
        # Check for invalid characters
        invalid_chars = ['\\', '/', '*', '[', ']', ':', '?']
        for char in invalid_chars:
            if char in name:
                results["errors"].append(f"Sheet name contains invalid character: {char}")
                results["valid"] = False
        
        # Check for reserved names
        reserved_names = ['History']
        if name in reserved_names:
            results["errors"].append(f"'{name}' is a reserved sheet name")
            results["valid"] = False
        
        # Check if name is empty or whitespace
        if not name or name.isspace():
            results["errors"].append("Sheet name cannot be empty or whitespace")
            results["valid"] = False
        
        return results


class ColumnValidator:
    """Validates column definitions"""
    
    def validate(self, column: ColumnDefinition) -> Dict[str, Any]:
        """Validate column"""
        results = {"valid": True, "errors": [], "warnings": []}
        
        # Check column name
        if not column.name:
            results["errors"].append("Column name is required")
            results["valid"] = False
        elif len(column.name) > 255:
            results["errors"].append(f"Column name '{column.name}' exceeds 255 characters")
            results["valid"] = False
        
        # Check data type
        valid_types = ["text", "number", "currency", "percentage", "date", "boolean"]
        if column.data_type not in valid_types:
            results["warnings"].append(f"Unknown data type: {column.data_type}")
        
        # Check width if specified
        if hasattr(column, 'width') and column.width:
            if column.width < 0 or column.width > 255:
                results["warnings"].append(f"Column width {column.width} may not be supported")
        
        return results


class FormulaValidator:
    """Validates formula definitions"""
    
    def __init__(self):
        self.excel_functions = self._load_excel_functions()
    
    def validate(self, formula: FormulaDefinition, sheet: SheetSchema) -> Dict[str, Any]:
        """Validate formula"""
        results = {"valid": True, "errors": [], "warnings": []}
        
        # Check formula syntax
        if not self._validate_formula_syntax(formula.formula):
            results["errors"].append(f"Invalid formula syntax: {formula.formula}")
            results["valid"] = False
        
        # Check cell references
        cell_refs = self._extract_cell_references(formula.formula)
        for ref in cell_refs:
            if not self._cell_exists_in_sheet(ref, sheet):
                results["warnings"].append(f"Cell reference {ref} may not exist")
        
        return results
    
    def _validate_formula_syntax(self, formula: str) -> bool:
        """Basic formula syntax validation"""
        if not formula.startswith('='):
            return False
        
        # Check balanced parentheses
        paren_count = 0
        for char in formula:
            if char == '(':
                paren_count += 1
            elif char == ')':
                paren_count -= 1
            if paren_count < 0:
                return False
        
        return paren_count == 0
    
    def _extract_cell_references(self, formula: str) -> List[str]:
        """Extract cell references from formula"""
        import re
        pattern = r'[A-Z]+[0-9]+'
        return re.findall(pattern, formula)
    
    def _cell_exists_in_sheet(self, cell_ref: str, sheet: SheetSchema) -> bool:
        """Check if cell reference exists in sheet"""
        # Simple check - could be enhanced
        return True
    
    def _load_excel_functions(self) -> set:
        """Load known Excel functions"""
        return {
            'SUM', 'AVERAGE', 'COUNT', 'MAX', 'MIN', 'IF', 'VLOOKUP',
            'HLOOKUP', 'INDEX', 'MATCH', 'CONCATENATE', 'LEFT', 'RIGHT',
            'MID', 'LEN', 'TRIM', 'UPPER', 'LOWER', 'DATE', 'TODAY'
        }


class ChartValidator:
    """Validates chart specifications"""
    
    def validate(self, chart: ChartSpecification, sheet: SheetSchema) -> Dict[str, Any]:
        """Validate chart"""
        results = {"valid": True, "errors": [], "warnings": []}
        
        # Check chart type
        valid_types = ["bar", "line", "pie", "area", "scatter", "column"]
        if chart.type not in valid_types:
            results["errors"].append(f"Invalid chart type: {chart.type}")
            results["valid"] = False
        
        # Check data range
        if not self._is_valid_range(chart.data_range):
            results["errors"].append(f"Invalid data range: {chart.data_range}")
            results["valid"] = False
        
        return results
    
    def _is_valid_range(self, range_str: str) -> bool:
        """Validate Excel range format"""
        import re
        pattern = r'^[A-Z]+[0-9]+:[A-Z]+[0-9]+$'
        return bool(re.match(pattern, range_str))


class SheetSuggestionGenerator:
    """Generates suggestions for sheet improvements"""
    
    def generate(self, sheet: SheetSchema) -> List[str]:
        """Generate suggestions for sheet"""
        suggestions = []
        
        # Suggest adding formulas if none exist
        if not sheet.formulas and len(sheet.columns) > 2:
            numeric_cols = sum(1 for col in sheet.columns if col.data_type in ["number", "currency"])
            if numeric_cols >= 2:
                suggestions.append("Consider adding summary formulas (SUM, AVERAGE) for numeric columns")
        
        # Suggest charts for data visualization
        if not sheet.charts and len(sheet.columns) > 1:
            suggestions.append("Consider adding charts for data visualization")
        
        # Suggest better column names
        for col in sheet.columns:
            if col.name.lower() in ['column1', 'col1', 'data1']:
                suggestions.append(f"Consider using more descriptive name for column '{col.name}'")
        
        return suggestions