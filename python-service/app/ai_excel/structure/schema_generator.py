"""
Schema generator for creating Excel structures from context
Uses AI to generate appropriate schemas based on user requirements
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from .excel_schema import (
    ExcelStructure, SheetSchema, ColumnDefinition, 
    DataType, ChartSpecification, FormulaDefinition,
    ChartType, FormulaType, DataRelationship
)
from ...services.openai_service import openai_service

logger = logging.getLogger(__name__)


class SchemaGenerator:
    """Generates Excel schemas using AI"""
    
    def __init__(self):
        self.domain_templates = self._load_domain_templates()
    
    async def generate(self, context: Dict[str, Any], analysis: Dict[str, Any]) -> ExcelStructure:
        """Generate Excel structure from context and analysis"""
        try:
            # Use structured output for schema generation
            schema_json = await self._generate_structure_with_ai(context, analysis)
            
            # Parse and validate the structure
            structure = self._parse_structure(schema_json)
            
            # Enhance with domain knowledge
            structure = self._enhance_with_domain_knowledge(structure, context)
            
            # Add calculated columns and formulas
            structure = self._add_calculations(structure, context)
            
            # Add visualizations if requested
            if context.get("output_preferences", {}).get("include_charts"):
                structure = self._add_visualizations(structure, context)
            
            return structure
            
        except Exception as e:
            logger.error(f"Schema generation failed: {str(e)}")
            # Return a basic fallback structure
            return self._create_fallback_structure(context)
    
    async def _generate_structure_with_ai(self, context: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate structure using OpenAI with structured output"""
        
        system_prompt = """You are an Excel structure designer. Based on the context and analysis provided, 
        design an optimal Excel structure. Return a JSON object with the following structure:
        
        {
            "filename": "suggested_filename.xlsx",
            "title": "Document Title",
            "sheets": [
                {
                    "name": "Sheet Name",
                    "columns": [
                        {
                            "name": "Column Name",
                            "data_type": "text|number|currency|percentage|date|formula",
                            "width": 15,
                            "description": "Column description"
                        }
                    ],
                    "row_count": 100,
                    "has_totals": true/false,
                    "description": "Sheet description"
                }
            ],
            "relationships": [
                {
                    "source_sheet": "Sheet1",
                    "source_range": "A2:A100",
                    "target_sheet": "Sheet2",
                    "target_range": "B2:B100",
                    "relationship_type": "lookup"
                }
            ]
        }
        
        Consider the domain, requirements, and best practices for Excel design."""
        
        user_prompt = f"""Context:
        Domain: {context.get('domain')}
        Requirements: {json.dumps(context.get('requirements', []))}
        Entities: {json.dumps(context.get('entities', {}))}
        Time Context: {json.dumps(context.get('time_context', {}))}
        Data Specifications: {json.dumps(context.get('data_specs', {}))}
        
        Analysis:
        Intent: {analysis.get('intent')}
        Complexity: {analysis.get('complexity')}
        Priority Features: {analysis.get('priority_features')}
        
        Design an Excel structure that best serves these requirements."""
        
        response = await openai_service.chat_completion([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse AI response: {response}")
            return self._get_default_structure(context)
    
    def _parse_structure(self, schema_json: Dict[str, Any]) -> ExcelStructure:
        """Parse JSON schema into ExcelStructure model"""
        
        # Convert JSON to Pydantic models
        sheets = []
        for sheet_data in schema_json.get("sheets", []):
            columns = []
            for col_data in sheet_data.get("columns", []):
                column = ColumnDefinition(
                    name=col_data.get("name", "Column"),
                    data_type=DataType(col_data.get("data_type", "text")),
                    width=col_data.get("width", 15),
                    description=col_data.get("description")
                )
                columns.append(column)
            
            sheet = SheetSchema(
                name=sheet_data.get("name", "Sheet1"),
                columns=columns,
                row_count=sheet_data.get("row_count", 100),
                has_totals=sheet_data.get("has_totals", False),
                description=sheet_data.get("description")
            )
            sheets.append(sheet)
        
        # Create relationships
        relationships = []
        for rel_data in schema_json.get("relationships", []):
            relationship = DataRelationship(
                source_sheet=rel_data.get("source_sheet"),
                source_range=rel_data.get("source_range"),
                target_sheet=rel_data.get("target_sheet"),
                target_range=rel_data.get("target_range"),
                relationship_type=rel_data.get("relationship_type")
            )
            relationships.append(relationship)
        
        structure = ExcelStructure(
            filename=schema_json.get("filename"),
            title=schema_json.get("title"),
            sheets=sheets,
            relationships=relationships,
            domain=schema_json.get("domain")
        )
        
        return structure
    
    def _enhance_with_domain_knowledge(self, structure: ExcelStructure, context: Dict[str, Any]) -> ExcelStructure:
        """Enhance structure with domain-specific knowledge"""
        
        domain = context.get("domain")
        if not domain or domain not in self.domain_templates:
            return structure
        
        template = self.domain_templates[domain]
        
        # Add domain-specific formulas
        for sheet in structure.sheets:
            if sheet.name in template.get("sheet_formulas", {}):
                formulas = template["sheet_formulas"][sheet.name]
                for formula_spec in formulas:
                    formula = FormulaDefinition(
                        cell_reference=formula_spec["cell"],
                        formula_type=FormulaType(formula_spec["type"]),
                        formula=formula_spec["formula"],
                        description=formula_spec.get("description")
                    )
                    if sheet.formulas is None:
                        sheet.formulas = []
                    sheet.formulas.append(formula)
        
        # Add domain-specific metadata
        if structure.metadata is None:
            structure.metadata = {}
        structure.metadata.update(template.get("metadata", {}))
        
        return structure
    
    def _add_calculations(self, structure: ExcelStructure, context: Dict[str, Any]) -> ExcelStructure:
        """Add calculated columns and formulas"""
        
        calculations = context.get("data_specs", {}).get("calculations", [])
        
        for calc in calculations:
            calc_type = calc.get("type")
            
            if calc_type == "sum":
                self._add_sum_formulas(structure, calc)
            elif calc_type == "average":
                self._add_average_formulas(structure, calc)
            elif calc_type == "percentage_change":
                self._add_percentage_change_formulas(structure, calc)
            elif calc_type == "running_total":
                self._add_running_total_formulas(structure, calc)
        
        return structure
    
    def _add_sum_formulas(self, structure: ExcelStructure, calc_spec: Dict[str, Any]) -> None:
        """Add SUM formulas to appropriate columns"""
        
        for sheet in structure.sheets:
            if sheet.has_totals:
                for col_idx, column in enumerate(sheet.columns):
                    if column.data_type in [DataType.NUMBER, DataType.CURRENCY]:
                        col_letter = self._get_column_letter(col_idx + 1)
                        formula = FormulaDefinition(
                            cell_reference=f"{col_letter}{sheet.row_count + 2}",
                            formula_type=FormulaType.SUM,
                            formula=f"=SUM({col_letter}2:{col_letter}{sheet.row_count + 1})",
                            description=f"Total for {column.name}"
                        )
                        if sheet.formulas is None:
                            sheet.formulas = []
                        sheet.formulas.append(formula)
    
    def _add_average_formulas(self, structure: ExcelStructure, calc_spec: Dict[str, Any]) -> None:
        """Add AVERAGE formulas"""
        # Implementation similar to sum formulas
        pass
    
    def _add_percentage_change_formulas(self, structure: ExcelStructure, calc_spec: Dict[str, Any]) -> None:
        """Add percentage change formulas"""
        # Implementation for percentage change calculations
        pass
    
    def _add_running_total_formulas(self, structure: ExcelStructure, calc_spec: Dict[str, Any]) -> None:
        """Add running total formulas"""
        # Implementation for running totals
        pass
    
    def _add_visualizations(self, structure: ExcelStructure, context: Dict[str, Any]) -> ExcelStructure:
        """Add charts and visualizations"""
        
        domain = context.get("domain")
        
        for sheet in structure.sheets:
            charts_to_add = self._determine_charts(sheet, domain)
            
            for chart_spec in charts_to_add:
                chart = ChartSpecification(
                    chart_type=chart_spec["type"],
                    title=chart_spec["title"],
                    data_range=chart_spec["data_range"],
                    categories_range=chart_spec.get("categories_range"),
                    position=chart_spec.get("position", "E5")
                )
                
                if sheet.charts is None:
                    sheet.charts = []
                sheet.charts.append(chart)
        
        return structure
    
    def _determine_charts(self, sheet: SheetSchema, domain: Optional[str]) -> List[Dict[str, Any]]:
        """Determine appropriate charts for a sheet"""
        
        charts = []
        
        # Analyze columns to determine chart types
        numeric_columns = [col for col in sheet.columns if col.data_type in [DataType.NUMBER, DataType.CURRENCY]]
        date_columns = [col for col in sheet.columns if col.data_type == DataType.DATE]
        
        if date_columns and numeric_columns:
            # Time series chart
            charts.append({
                "type": ChartType.LINE,
                "title": f"{numeric_columns[0].name} Trend",
                "data_range": f"B1:C{sheet.row_count + 1}",
                "categories_range": f"A2:A{sheet.row_count + 1}"
            })
        
        if domain == "sales" and len(numeric_columns) > 1:
            # Comparison chart
            charts.append({
                "type": ChartType.BAR,
                "title": "Sales Comparison",
                "data_range": f"A1:D{min(20, sheet.row_count + 1)}",
                "position": "G5"
            })
        
        return charts
    
    def _create_fallback_structure(self, context: Dict[str, Any]) -> ExcelStructure:
        """Create a basic fallback structure"""
        
        columns = [
            ColumnDefinition(name="항목", data_type=DataType.TEXT),
            ColumnDefinition(name="값", data_type=DataType.NUMBER),
            ColumnDefinition(name="비고", data_type=DataType.TEXT)
        ]
        
        sheet = SheetSchema(
            name="데이터",
            columns=columns,
            row_count=50
        )
        
        structure = ExcelStructure(
            filename=f"excel_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            title="Generated Excel",
            sheets=[sheet],
            domain=context.get("domain")
        )
        
        return structure
    
    def _get_column_letter(self, col_idx: int) -> str:
        """Convert column index to Excel letter"""
        letter = ""
        while col_idx > 0:
            col_idx -= 1
            letter = chr(65 + col_idx % 26) + letter
            col_idx //= 26
        return letter
    
    def _get_default_structure(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get default structure based on domain"""
        
        domain = context.get("domain", "general")
        
        default_structures = {
            "finance": {
                "filename": "financial_report.xlsx",
                "title": "Financial Report",
                "sheets": [
                    {
                        "name": "손익계산서",
                        "columns": [
                            {"name": "계정과목", "data_type": "text", "width": 20},
                            {"name": "당기", "data_type": "currency", "width": 15},
                            {"name": "전기", "data_type": "currency", "width": 15},
                            {"name": "증감액", "data_type": "currency", "width": 15},
                            {"name": "증감률", "data_type": "percentage", "width": 12}
                        ],
                        "has_totals": True
                    }
                ]
            },
            "general": {
                "filename": "data.xlsx",
                "title": "Data",
                "sheets": [
                    {
                        "name": "Sheet1",
                        "columns": [
                            {"name": "항목", "data_type": "text", "width": 20},
                            {"name": "값", "data_type": "number", "width": 15}
                        ]
                    }
                ]
            }
        }
        
        return default_structures.get(domain, default_structures["general"])
    
    def _load_domain_templates(self) -> Dict[str, Dict[str, Any]]:
        """Load domain-specific templates"""
        
        return {
            "finance": {
                "sheet_formulas": {
                    "손익계산서": [
                        {
                            "cell": "B20",
                            "type": "sum",
                            "formula": "=SUM(B2:B19)",
                            "description": "Total Revenue"
                        }
                    ]
                },
                "metadata": {
                    "standards": ["K-GAAP", "IFRS"],
                    "period_type": "annual"
                }
            },
            "hr": {
                "sheet_formulas": {
                    "급여현황": [
                        {
                            "cell": "F2",
                            "type": "custom",
                            "formula": "=C2+D2-E2",
                            "description": "Net Salary Calculation"
                        }
                    ]
                },
                "metadata": {
                    "privacy": "high",
                    "compliance": ["Labor Standards Act"]
                }
            }
        }