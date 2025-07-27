"""
AI Excel Generation System
True AI-powered Excel generation with template integration
"""

from .integration.ai_coordinator import AICoordinator
from .structure.excel_schema import (
    ExcelStructure, SheetSchema, ColumnDefinition,
    DataType, ChartType, FormulaType,
    GenerationRequest, GenerationResponse
)

# Create global coordinator instance
ai_excel_coordinator = AICoordinator()

# Main API
async def generate_excel_with_ai(
    user_request: str,
    options: dict = None
) -> dict:
    """
    Generate Excel file using AI
    
    Args:
        user_request: Natural language request from user
        options: Optional generation options
        
    Returns:
        Generation response with file path and metadata
    """
    return await ai_excel_coordinator.generate_excel(user_request, options)


# Export main components
__all__ = [
    'ai_excel_coordinator',
    'generate_excel_with_ai',
    'ExcelStructure',
    'SheetSchema', 
    'ColumnDefinition',
    'DataType',
    'ChartType',
    'FormulaType',
    'GenerationRequest',
    'GenerationResponse'
]