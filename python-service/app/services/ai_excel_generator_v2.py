"""
AI Excel Generator v2 - Refactored version using modular architecture
This replaces the original ai_excel_generator.py with a cleaner implementation
"""

import logging
from typing import Dict, Any, Optional

from ..ai_excel import generate_excel_with_ai, ai_excel_coordinator
from ..ai_excel.structure.excel_schema import GenerationRequest, GenerationResponse

logger = logging.getLogger(__name__)


class AIExcelGeneratorV2:
    """
    AI-based Excel generator with true dynamic generation capabilities
    Uses modular architecture for better maintainability and extensibility
    """
    
    def __init__(self):
        self.coordinator = ai_excel_coordinator
        self.generation_cache = {}
    
    async def generate_from_natural_language(
        self,
        user_request: str,
        context: Optional[Dict[str, Any]] = None,
        language: str = "ko"
    ) -> Dict[str, Any]:
        """
        Generate Excel file from natural language request
        
        Args:
            user_request: Natural language request
            context: Additional context information
            language: Language code (default: ko)
            
        Returns:
            Generation result with file path and metadata
        """
        
        try:
            # Prepare generation options
            options = {
                "language": language,
                "context": context or {},
                "enable_templates": True,  # Enable template integration
                "quality_check": True,     # Enable quality checks
                "optimization": "auto"     # Auto-optimize based on complexity
            }
            
            # Generate Excel using new system
            result = await generate_excel_with_ai(user_request, options)
            
            # Transform result to match existing API
            return self._transform_result(result)
            
        except Exception as e:
            logger.error(f"AI Excel generation failed: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "error_type": type(e).__name__
            }
    
    async def generate_with_template_enhancement(
        self,
        user_request: str,
        template_preference: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate Excel with explicit template enhancement
        
        Args:
            user_request: Natural language request
            template_preference: Preferred template category
            context: Additional context
            
        Returns:
            Generation result
        """
        
        options = {
            "context": context or {},
            "template_preference": template_preference,
            "force_template": template_preference is not None
        }
        
        result = await generate_excel_with_ai(user_request, options)
        return self._transform_result(result)
    
    async def generate_pure_ai(
        self,
        user_request: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate Excel using pure AI without templates
        
        Args:
            user_request: Natural language request
            context: Additional context
            
        Returns:
            Generation result
        """
        
        options = {
            "context": context or {},
            "enable_templates": False,  # Disable template integration
            "generation_mode": "pure_ai"
        }
        
        result = await generate_excel_with_ai(user_request, options)
        return self._transform_result(result)
    
    async def get_generation_insights(
        self,
        user_request: str,
        language: str = "ko"
    ) -> Dict[str, Any]:
        """
        Get AI insights about the generation without creating Excel
        
        Args:
            user_request: Natural language request
            language: Language code
            
        Returns:
            Insights and recommendations
        """
        
        try:
            # Build context
            context = await self.coordinator.context_builder.build(user_request, {"language": language})
            
            # Analyze context
            analysis = await self.coordinator.context_analyzer.analyze(context)
            
            # Extract insights
            insights = {
                "intent": analysis.get("intent"),
                "complexity": analysis.get("complexity"),
                "recommended_approach": analysis.get("generation_strategy", {}).get("approach"),
                "estimated_sheets": len(analysis.get("priority_features", [])),
                "ai_suggestions": analysis.get("ai_insights"),
                "template_relevance": analysis.get("template_relevance"),
                "confidence_score": analysis.get("ai_insights", {}).get("confidence", 0.5)
            }
            
            return {
                "status": "success",
                "insights": insights
            }
            
        except Exception as e:
            logger.error(f"Failed to get insights: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def get_generation_statistics(self) -> Dict[str, Any]:
        """Get statistics about AI generations"""
        
        stats = self.coordinator.get_generation_stats()
        
        return {
            "total_generations": stats.get("total_generations", 0),
            "success_rate": stats.get("success_rate", 0),
            "average_generation_time": stats.get("average_duration", 0),
            "recent_generations": stats.get("recent_generations", []),
            "cache_size": len(self.generation_cache)
        }
    
    def _transform_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Transform internal result to API format"""
        
        if result.get("status") == "success":
            structure = result.get("structure", {})
            sheets_info = []
            
            for sheet in structure.get("structure", {}).get("sheets", []):
                sheets_info.append({
                    "name": sheet.get("name"),
                    "columns": len(sheet.get("columns", [])),
                    "rows": sheet.get("row_count", 0),
                    "has_charts": len(sheet.get("charts", [])) > 0,
                    "has_formulas": len(sheet.get("formulas", [])) > 0
                })
            
            return {
                "status": "success",
                "file_path": result.get("file_path"),
                "generation_id": result.get("generation_id"),
                "sheets": sheets_info,
                "domain": structure.get("structure", {}).get("domain"),
                "template_used": result.get("strategy_used", {}).get("template_id"),
                "generation_approach": result.get("strategy_used", {}).get("approach"),
                "quality_score": self._calculate_quality_score(result.get("quality_report", {})),
                "metadata": {
                    "duration": result.get("metadata", {}).get("duration_seconds"),
                    "total_cells": result.get("metadata", {}).get("total_cells"),
                    "complexity": structure.get("generation_hints", {}).get("complexity")
                }
            }
        else:
            return {
                "status": "error",
                "message": result.get("error", "Unknown error"),
                "generation_id": result.get("generation_id"),
                "partial_result": result.get("partial_result")
            }
    
    def _calculate_quality_score(self, quality_report: Dict[str, Any]) -> float:
        """Calculate quality score from report"""
        
        if not quality_report:
            return 0.0
        
        # Base score
        score = 1.0 if quality_report.get("passed", False) else 0.5
        
        # Deduct for warnings
        warnings = len(quality_report.get("warnings", []))
        score -= warnings * 0.05
        
        # Bonus for suggestions implemented
        suggestions = len(quality_report.get("suggestions", []))
        if suggestions == 0:
            score += 0.1  # No suggestions needed
        
        return max(0.0, min(1.0, score))


# Create global instance
ai_excel_generator_v2 = AIExcelGeneratorV2()


# Compatibility layer - drop-in replacement for original
class AIExcelGenerator:
    """Compatibility wrapper for existing code"""
    
    async def generate_from_natural_language(self, *args, **kwargs):
        return await ai_excel_generator_v2.generate_from_natural_language(*args, **kwargs)
    
    async def find_or_generate_template(self, request: str, language: str = "ko"):
        """Compatibility method"""
        insights = await ai_excel_generator_v2.get_generation_insights(request, language)
        return insights.get("insights", {})


# Export for compatibility
ai_excel_generator = AIExcelGenerator()