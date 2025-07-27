"""
AI Coordinator for orchestrating the Excel generation process
Manages the flow between different components and ensures quality
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio

from ..context.builder import ContextBuilder
from ..context.analyzer import ContextAnalyzer
from ..structure.schema_generator import SchemaGenerator
from ..structure.validators import SchemaValidator
from ..generators.ai_data_generator import AIDataGenerator
from .template_bridge import TemplateBridge
from ...core.excel_builder import ExcelBuilder
from ...core.style_manager import StyleManager

logger = logging.getLogger(__name__)


class AICoordinator:
    """Coordinates AI Excel generation process"""
    
    def __init__(self):
        self.context_builder = ContextBuilder()
        self.context_analyzer = ContextAnalyzer()
        self.schema_generator = SchemaGenerator()
        self.schema_validator = SchemaValidator()
        self.data_generator = AIDataGenerator()
        self.template_bridge = TemplateBridge()
        self.excel_builder = ExcelBuilder()
        self.style_manager = StyleManager()
        
        self.generation_stats = {}
    
    async def generate_excel(
        self,
        user_request: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Main entry point for Excel generation"""
        
        start_time = datetime.now()
        generation_id = f"gen_{start_time.strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Stage 1: Context Building
            logger.info(f"Starting generation {generation_id}")
            context = await self._build_context(user_request, options)
            
            # Stage 2: Context Analysis
            analysis = await self._analyze_context(context)
            
            # Stage 3: Strategy Decision
            strategy = self._decide_strategy(context, analysis)
            
            # Stage 4: Structure Generation
            structure = await self._generate_structure(context, analysis, strategy)
            
            # Stage 5: Data Generation
            data = await self._generate_data(structure, context, analysis)
            
            # Stage 6: Excel Creation
            excel_file = await self._create_excel(structure, data, context)
            
            # Stage 7: Quality Check
            quality_report = await self._quality_check(excel_file, structure)
            
            # Prepare response
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            response = {
                "status": "success",
                "file_path": excel_file,
                "generation_id": generation_id,
                "structure": structure.to_generation_spec(),
                "strategy_used": strategy,
                "quality_report": quality_report,
                "metadata": {
                    "duration_seconds": duration,
                    "context_confidence": analysis.get("ai_insights", {}).get("confidence", 0),
                    "template_used": strategy.get("template_id"),
                    "sheets_created": len(structure.sheets),
                    "total_cells": sum(sheet.row_count * len(sheet.columns) for sheet in structure.sheets)
                }
            }
            
            # Store stats
            self._store_generation_stats(generation_id, response)
            
            return response
            
        except Exception as e:
            logger.error(f"Generation {generation_id} failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "generation_id": generation_id,
                "partial_result": self._get_partial_result(generation_id)
            }
    
    async def _build_context(self, user_request: str, options: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Build comprehensive context"""
        
        logger.info("Building context from user request")
        
        # Extract additional context from options
        additional_context = {
            "generation_options": options or {},
            "timestamp": datetime.now().isoformat(),
            "session_id": options.get("session_id") if options else None
        }
        
        # Build context
        context = self.context_builder.build(user_request, additional_context)
        
        return context
    
    async def _analyze_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze context for insights"""
        
        logger.info("Analyzing context")
        analysis = await self.context_analyzer.analyze(context)
        
        return analysis
    
    def _decide_strategy(self, context: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Decide generation strategy"""
        
        strategy = {
            "approach": "hybrid",  # default
            "use_template": False,
            "template_id": None,
            "ai_scope": "full",
            "optimization_level": "standard"
        }
        
        # Check for template relevance
        template_relevance = analysis.get("template_relevance", {})
        if template_relevance.get("score", 0) > 0.7:
            # Use template-based approach
            strategy["approach"] = "template_enhanced"
            strategy["use_template"] = True
            strategy["ai_scope"] = "enhancement"
        elif template_relevance.get("score", 0) < 0.3:
            # Pure AI approach
            strategy["approach"] = "pure_ai"
            strategy["ai_scope"] = "full"
        
        # Adjust optimization based on complexity
        complexity = analysis.get("complexity")
        if complexity in ["advanced", "expert"]:
            strategy["optimization_level"] = "advanced"
        
        return strategy
    
    async def _generate_structure(
        self,
        context: Dict[str, Any],
        analysis: Dict[str, Any],
        strategy: Dict[str, Any]
    ) -> Any:  # Returns ExcelStructure
        """Generate Excel structure"""
        
        logger.info(f"Generating structure with strategy: {strategy['approach']}")
        
        if strategy["use_template"]:
            # Find and enhance template
            template = await self.template_bridge.find_relevant_template(
                context["original_text"], context
            )
            
            if template:
                strategy["template_id"] = template["template_id"]
                structure = await self.template_bridge.enhance_template_with_ai(
                    template, context, analysis
                )
            else:
                # Fallback to pure AI
                structure = await self.schema_generator.generate(context, analysis)
        else:
            # Pure AI generation
            structure = await self.schema_generator.generate(context, analysis)
        
        # Validate structure
        validation_results = self.schema_validator.validate_structure(structure)
        if not validation_results["valid"]:
            logger.warning(f"Structure validation warnings: {validation_results['warnings']}")
            # Fix critical errors
            structure = self._fix_structure_errors(structure, validation_results)
        
        return structure
    
    async def _generate_data(
        self,
        structure: Any,  # ExcelStructure
        context: Dict[str, Any],
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:  # Sheet name -> DataFrame
        """Generate data for all sheets"""
        
        logger.info("Generating data for Excel structure")
        
        data = {}
        
        # Generate data for each sheet
        for sheet in structure.sheets:
            logger.info(f"Generating data for sheet: {sheet.name}")
            
            # Prepare schema for data generation
            sheet_schema = {
                "columns": [col.dict() for col in sheet.columns],
                "row_count": sheet.row_count
            }
            
            # Generate contextual data
            sheet_data = await self.data_generator.generate_contextual_data(
                schema=sheet_schema,
                context=context,
                constraints=self._get_sheet_constraints(sheet, analysis)
            )
            
            data[sheet.name] = sheet_data
        
        return data
    
    async def _create_excel(
        self,
        structure: Any,  # ExcelStructure
        data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """Create Excel file from structure and data"""
        
        logger.info("Creating Excel file")
        
        # Import here to avoid circular dependency
        from ..generators.finance import FinanceGenerator
        
        # Get appropriate generator based on domain
        domain = context.get("domain", "general")
        
        if domain == "finance":
            generator = FinanceGenerator()
        else:
            # Use base generator for other domains
            from ...core.base_generator import BaseExcelGenerator
            generator = BaseExcelGenerator()
        
        # Set context
        generator.context = context
        
        # Generate Excel file
        file_path = await generator.generate(
            request=context["original_text"],
            context=context
        )
        
        return file_path
    
    async def _quality_check(self, excel_file: str, structure: Any) -> Dict[str, Any]:
        """Perform quality checks on generated Excel"""
        
        logger.info("Performing quality check")
        
        quality_report = {
            "passed": True,
            "checks": [],
            "warnings": [],
            "suggestions": []
        }
        
        try:
            # Basic file checks
            import os
            if not os.path.exists(excel_file):
                quality_report["passed"] = False
                quality_report["checks"].append({
                    "name": "file_exists",
                    "passed": False,
                    "message": "Generated file not found"
                })
                return quality_report
            
            file_size = os.path.getsize(excel_file)
            quality_report["checks"].append({
                "name": "file_size",
                "passed": file_size > 0,
                "value": file_size
            })
            
            # Structure validation
            structure_validation = self.schema_validator.validate_structure(structure)
            quality_report["checks"].append({
                "name": "structure_validation",
                "passed": structure_validation["valid"],
                "errors": structure_validation.get("errors", [])
            })
            
            if structure_validation["warnings"]:
                quality_report["warnings"].extend(structure_validation["warnings"])
            
            if structure_validation["suggestions"]:
                quality_report["suggestions"].extend(structure_validation["suggestions"])
            
            # Set overall pass status
            quality_report["passed"] = all(
                check["passed"] for check in quality_report["checks"]
            )
            
        except Exception as e:
            logger.error(f"Quality check failed: {str(e)}")
            quality_report["passed"] = False
            quality_report["checks"].append({
                "name": "quality_check",
                "passed": False,
                "error": str(e)
            })
        
        return quality_report
    
    def _get_sheet_constraints(self, sheet: Any, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Get constraints for sheet data generation"""
        
        constraints = {
            "columns": {}
        }
        
        # Add column-specific constraints
        for column in sheet.columns:
            col_constraints = {}
            
            # Add data type constraints
            if column.data_type == "percentage":
                col_constraints["min"] = 0
                col_constraints["max"] = 1
            elif column.data_type == "currency":
                col_constraints["min"] = 0
            
            if col_constraints:
                constraints["columns"][column.name] = col_constraints
        
        # Add domain-specific constraints
        domain = analysis.get("context", {}).get("domain")
        if domain == "finance":
            # Financial constraints
            constraints["balance_rules"] = True
            constraints["non_negative"] = ["revenue", "costs", "assets"]
        
        return constraints
    
    def _fix_structure_errors(self, structure: Any, validation_results: Dict[str, Any]) -> Any:
        """Fix critical errors in structure"""
        
        # Fix sheet name errors
        for error in validation_results.get("errors", []):
            if "Sheet name" in error:
                # Fix sheet names
                for sheet in structure.sheets:
                    # Remove invalid characters
                    invalid_chars = ['\\', '/', '*', '[', ']', ':', '?']
                    for char in invalid_chars:
                        sheet.name = sheet.name.replace(char, "_")
                    
                    # Truncate if too long
                    if len(sheet.name) > 31:
                        sheet.name = sheet.name[:31]
        
        return structure
    
    def _store_generation_stats(self, generation_id: str, response: Dict[str, Any]) -> None:
        """Store generation statistics for analysis"""
        
        self.generation_stats[generation_id] = {
            "timestamp": datetime.now().isoformat(),
            "status": response["status"],
            "duration": response.get("metadata", {}).get("duration_seconds"),
            "strategy": response.get("strategy_used"),
            "sheets": response.get("metadata", {}).get("sheets_created"),
            "cells": response.get("metadata", {}).get("total_cells")
        }
    
    def _get_partial_result(self, generation_id: str) -> Optional[Dict[str, Any]]:
        """Get any partial results from failed generation"""
        
        # This would retrieve any partial results saved during generation
        # For now, return None
        return None
    
    def get_generation_stats(self) -> Dict[str, Any]:
        """Get generation statistics"""
        
        total_generations = len(self.generation_stats)
        successful = sum(1 for stat in self.generation_stats.values() if stat["status"] == "success")
        
        avg_duration = 0
        if successful > 0:
            durations = [stat["duration"] for stat in self.generation_stats.values() 
                        if stat["status"] == "success" and stat["duration"]]
            avg_duration = sum(durations) / len(durations) if durations else 0
        
        return {
            "total_generations": total_generations,
            "successful": successful,
            "success_rate": successful / total_generations if total_generations > 0 else 0,
            "average_duration": avg_duration,
            "recent_generations": list(self.generation_stats.keys())[-10:]
        }