"""
Validators for Excel schema and structure
Ensures generated schemas are valid and consistent
"""

from typing import Dict, List, Any, Optional, Set
import re
from datetime import datetime

from .excel_schema import (
    ExcelStructure, SheetSchema, ColumnDefinition,
    DataType, ChartSpecification, FormulaDefinition
)
from .sheet_validators import (
    SheetNameValidator, ColumnValidator, FormulaValidator,
    ChartValidator, SheetSuggestionGenerator
)


class SchemaValidator:
    """Validates Excel schemas for correctness and consistency"""
    
    def __init__(self):
        self.excel_functions = self._load_excel_functions()
        self.reserved_names = ['History', 'Sheet', '_xlnm']
        # Initialize specialized validators
        self.sheet_name_validator = SheetNameValidator()
        self.column_validator = ColumnValidator()
        self.formula_validator = FormulaValidator()
        self.chart_validator = ChartValidator()
        self.suggestion_generator = SheetSuggestionGenerator()
    
    def validate_structure(self, structure: ExcelStructure) -> Dict[str, Any]:
        """Validate complete Excel structure"""
        
        results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": []
        }
        
        # Validate sheets
        for sheet in structure.sheets:
            sheet_results = self.validate_sheet(sheet)
            if not sheet_results["valid"]:
                results["valid"] = False
            results["errors"].extend(sheet_results["errors"])
            results["warnings"].extend(sheet_results["warnings"])
            results["suggestions"].extend(sheet_results["suggestions"])
        
        # Validate relationships
        if structure.relationships:
            rel_results = self._validate_relationships(structure)
            if not rel_results["valid"]:
                results["valid"] = False
            results["errors"].extend(rel_results["errors"])
            results["warnings"].extend(rel_results["warnings"])
        
        # Check for circular dependencies
        circular_deps = self._check_circular_dependencies(structure)
        if circular_deps:
            results["errors"].append(f"Circular dependencies detected: {circular_deps}")
            results["valid"] = False
        
        return results
    
    def validate_sheet(self, sheet: SheetSchema) -> Dict[str, Any]:
        """Validate a single sheet using specialized validators"""
        
        results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": []
        }
        
        # Validate sheet name
        name_results = self.sheet_name_validator.validate(sheet.name)
        self._merge_results(results, name_results)
        
        # Validate columns
        column_names = set()
        for column in sheet.columns:
            # Check for duplicate column names
            if column.name in column_names:
                results["errors"].append(f"Duplicate column name: {column.name}")
                results["valid"] = False
            column_names.add(column.name)
            
            # Validate column using specialized validator
            col_results = self.column_validator.validate(column)
            self._merge_results(results, col_results)
        
        # Validate formulas
        if sheet.formulas:
            for formula in sheet.formulas:
                formula_results = self.formula_validator.validate(formula, sheet)
                self._merge_results(results, formula_results)
        
        # Validate charts
        if sheet.charts:
            for chart in sheet.charts:
                chart_results = self.chart_validator.validate(chart, sheet)
                self._merge_results(results, chart_results)
        
        # Generate suggestions
        suggestions = self.suggestion_generator.generate(sheet)
        results["suggestions"].extend(suggestions)
        
        return results
    
    def _merge_results(self, main_results: Dict[str, Any], new_results: Dict[str, Any]) -> None:
        """Merge validation results"""
        if not new_results.get("valid", True):
            main_results["valid"] = False
        main_results["errors"].extend(new_results.get("errors", []))
        main_results["warnings"].extend(new_results.get("warnings", []))
    
    
    
    
    def _validate_relationships(self, structure: ExcelStructure) -> Dict[str, Any]:
        """Validate data relationships"""
        
        results = {"valid": True, "errors": [], "warnings": []}
        
        sheet_names = {sheet.name for sheet in structure.sheets}
        
        for rel in structure.relationships:
            # Check if sheets exist
            if rel.source_sheet not in sheet_names:
                results["errors"].append(f"Relationship references non-existent sheet: {rel.source_sheet}")
                results["valid"] = False
            
            if rel.target_sheet not in sheet_names:
                results["errors"].append(f"Relationship references non-existent sheet: {rel.target_sheet}")
                results["valid"] = False
            
            # Validate ranges
            if not self._is_valid_range(rel.source_range):
                results["errors"].append(f"Invalid source range in relationship: {rel.source_range}")
                results["valid"] = False
            
            if not self._is_valid_range(rel.target_range):
                results["errors"].append(f"Invalid target range in relationship: {rel.target_range}")
                results["valid"] = False
        
        return results
    
    def _check_circular_dependencies(self, structure: ExcelStructure) -> List[str]:
        """Check for circular dependencies in formulas"""
        
        dependencies = {}
        
        # Build dependency graph
        for sheet in structure.sheets:
            if sheet.formulas:
                for formula in sheet.formulas:
                    cell_ref = f"{sheet.name}!{formula.cell_reference}"
                    deps = self._extract_dependencies(formula.formula, sheet.name)
                    dependencies[cell_ref] = deps
        
        # Check for cycles
        cycles = []
        visited = set()
        rec_stack = set()
        
        def has_cycle(node: str, path: List[str]) -> bool:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in dependencies.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor, path):
                        return True
                elif neighbor in rec_stack:
                    cycle_start = path.index(neighbor)
                    cycles.append(" -> ".join(path[cycle_start:] + [neighbor]))
                    return True
            
            path.pop()
            rec_stack.remove(node)
            return False
        
        for node in dependencies:
            if node not in visited:
                has_cycle(node, [])
        
        return cycles
    
    def _is_valid_cell_reference(self, ref: str) -> bool:
        """Check if cell reference is valid"""
        # Simple validation - can be enhanced
        pattern = r'^[A-Z]{1,3}\d{1,7}$'
        return bool(re.match(pattern, ref))
    
    def _is_valid_range(self, range_ref: str) -> bool:
        """Check if range reference is valid"""
        # Handle single cell or range
        if ':' in range_ref:
            parts = range_ref.split(':')
            if len(parts) != 2:
                return False
            return all(self._is_valid_cell_reference(part) for part in parts)
        else:
            return self._is_valid_cell_reference(range_ref)
    
    def _validate_formula_syntax(self, formula: str) -> Dict[str, Any]:
        """Validate Excel formula syntax"""
        
        results = {"valid": True, "errors": []}
        
        # Check if formula starts with =
        if not formula.startswith('='):
            results["errors"].append("Formula must start with '='")
            results["valid"] = False
            return results
        
        # Check parentheses balance
        if formula.count('(') != formula.count(')'):
            results["errors"].append("Unbalanced parentheses in formula")
            results["valid"] = False
        
        # Extract function names and validate
        function_pattern = r'([A-Z]+)\s*\('
        functions = re.findall(function_pattern, formula.upper())
        
        for func in functions:
            if func not in self.excel_functions:
                results["errors"].append(f"Unknown Excel function: {func}")
                results["valid"] = False
        
        return results
    
    def _extract_cell_references(self, formula: str) -> Set[str]:
        """Extract all cell references from a formula"""
        # Simple pattern - can be enhanced
        pattern = r'[A-Z]{1,3}\d{1,7}'
        return set(re.findall(pattern, formula))
    
    def _extract_dependencies(self, formula: str, current_sheet: str) -> List[str]:
        """Extract dependencies from formula"""
        deps = []
        
        # Extract sheet references
        sheet_pattern = r"'?([^'!]+)'?!([A-Z]{1,3}\d{1,7})"
        for match in re.finditer(sheet_pattern, formula):
            sheet_name = match.group(1)
            cell_ref = match.group(2)
            deps.append(f"{sheet_name}!{cell_ref}")
        
        # Extract local references
        local_refs = self._extract_cell_references(formula)
        for ref in local_refs:
            if f"!{ref}" not in formula:  # Not already part of sheet reference
                deps.append(f"{current_sheet}!{ref}")
        
        return deps
    
    def _cell_exists_in_sheet(self, cell_ref: str, sheet: SheetSchema) -> bool:
        """Check if cell reference exists within sheet bounds"""
        # Extract column and row
        match = re.match(r'^([A-Z]{1,3})(\d{1,7})$', cell_ref)
        if not match:
            return False
        
        col_letters = match.group(1)
        row_num = int(match.group(2))
        
        # Convert column letters to number
        col_num = 0
        for char in col_letters:
            col_num = col_num * 26 + (ord(char) - ord('A') + 1)
        
        # Check bounds
        return 1 <= col_num <= len(sheet.columns) and 1 <= row_num <= sheet.row_count + 10  # Allow some buffer
    
    def _range_exists_in_sheet(self, range_ref: str, sheet: SheetSchema) -> bool:
        """Check if range exists within sheet bounds"""
        if ':' in range_ref:
            parts = range_ref.split(':')
            return all(self._cell_exists_in_sheet(part, sheet) for part in parts)
        else:
            return self._cell_exists_in_sheet(range_ref, sheet)
    
    
    def _load_excel_functions(self) -> Set[str]:
        """Load list of valid Excel functions"""
        
        # Common Excel functions
        return {
            'SUM', 'AVERAGE', 'COUNT', 'COUNTA', 'COUNTIF', 'SUMIF',
            'VLOOKUP', 'HLOOKUP', 'INDEX', 'MATCH', 'OFFSET',
            'IF', 'IFS', 'AND', 'OR', 'NOT',
            'DATE', 'TODAY', 'NOW', 'YEAR', 'MONTH', 'DAY',
            'TEXT', 'VALUE', 'LEN', 'CONCATENATE', 'CONCAT',
            'MAX', 'MIN', 'ROUND', 'ROUNDUP', 'ROUNDDOWN',
            'IFERROR', 'ISNA', 'ISBLANK', 'ISERROR',
            'SUBTOTAL', 'SUMPRODUCT', 'INDIRECT'
        }