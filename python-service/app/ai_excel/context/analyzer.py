"""
Context analyzer for deep understanding of user intent
Analyzes context to determine the best generation approach
"""

from typing import Dict, List, Any, Optional, Tuple
import logging
from enum import Enum

from ...services.openai_service import openai_service

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    """Types of user intent"""
    CREATE_NEW = "create_new"
    MODIFY_EXISTING = "modify_existing"
    ANALYZE_DATA = "analyze_data"
    GENERATE_REPORT = "generate_report"
    TRACK_METRICS = "track_metrics"
    PLAN_FORECAST = "plan_forecast"


class ComplexityLevel(str, Enum):
    """Complexity levels for Excel generation"""
    SIMPLE = "simple"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class ContextAnalyzer:
    """Analyzes context to guide Excel generation"""
    
    def __init__(self):
        self.intent_keywords = {
            IntentType.CREATE_NEW: ["만들어", "생성", "작성", "새로", "신규"],
            IntentType.MODIFY_EXISTING: ["수정", "변경", "업데이트", "개선", "보완"],
            IntentType.ANALYZE_DATA: ["분석", "검토", "평가", "조사", "파악"],
            IntentType.GENERATE_REPORT: ["보고서", "리포트", "정리", "요약", "보고"],
            IntentType.TRACK_METRICS: ["추적", "모니터링", "관리", "기록", "추이"],
            IntentType.PLAN_FORECAST: ["계획", "예측", "전망", "예상", "시뮬레이션"]
        }
    
    async def analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Perform deep analysis of context"""
        analysis = {
            "intent": self._analyze_intent(context),
            "complexity": self._analyze_complexity(context),
            "priority_features": self._determine_priorities(context),
            "generation_strategy": await self._determine_strategy(context),
            "template_relevance": self._assess_template_relevance(context),
            "ai_generation_scope": self._determine_ai_scope(context)
        }
        
        # Add AI insights
        analysis["ai_insights"] = await self._get_ai_insights(context)
        
        return analysis
    
    def _analyze_intent(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze user intent from context"""
        text = context.get("original_text", "").lower()
        intents = []
        
        # Check for each intent type
        for intent_type, keywords in self.intent_keywords.items():
            if any(keyword in text for keyword in keywords):
                intents.append(intent_type.value)
        
        # Default to create_new if no specific intent found
        if not intents:
            intents.append(IntentType.CREATE_NEW.value)
        
        return {
            "primary": intents[0],
            "secondary": intents[1:] if len(intents) > 1 else [],
            "confidence": self._calculate_intent_confidence(intents, text)
        }
    
    def _analyze_complexity(self, context: Dict[str, Any]) -> ComplexityLevel:
        """Analyze complexity level required"""
        score = 0
        
        # Check requirements count
        requirements = context.get("requirements", [])
        score += min(len(requirements) * 10, 30)
        
        # Check for multiple sheets
        sheets = context.get("sheets", [])
        if len(sheets) > 3:
            score += 20
        elif len(sheets) > 1:
            score += 10
        
        # Check for advanced features
        if context.get("output_preferences", {}).get("include_charts"):
            score += 15
        
        # Check for calculations
        if context.get("data_specs", {}).get("calculations"):
            score += 15
        
        # Check for business rules
        if context.get("business_rules"):
            score += 10
        
        # Map score to complexity level
        if score >= 70:
            return ComplexityLevel.EXPERT
        elif score >= 50:
            return ComplexityLevel.ADVANCED
        elif score >= 30:
            return ComplexityLevel.INTERMEDIATE
        else:
            return ComplexityLevel.SIMPLE
    
    def _determine_priorities(self, context: Dict[str, Any]) -> List[str]:
        """Determine priority features for generation"""
        priorities = []
        
        # Domain-specific priorities
        domain = context.get("domain")
        if domain == "finance":
            priorities.extend(["accuracy", "formulas", "compliance"])
        elif domain == "sales":
            priorities.extend(["visualization", "trends", "performance"])
        elif domain == "hr":
            priorities.extend(["privacy", "structure", "calculations"])
        
        # Requirement-based priorities
        requirements = context.get("requirements", [])
        if "forecast" in requirements:
            priorities.append("projections")
        if "analysis" in requirements:
            priorities.append("insights")
        
        # Remove duplicates and return top 5
        return list(dict.fromkeys(priorities))[:5]
    
    async def _determine_strategy(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Determine the generation strategy"""
        strategy = {
            "approach": "hybrid",  # pure_ai, template_based, hybrid
            "data_source": "generated",  # generated, template, mixed
            "customization_level": "high",  # low, medium, high
            "stages": []
        }
        
        # Determine approach based on template availability
        if context.get("template_relevance", {}).get("score", 0) > 0.8:
            strategy["approach"] = "template_based"
            strategy["data_source"] = "mixed"
        elif context.get("template_relevance", {}).get("score", 0) < 0.3:
            strategy["approach"] = "pure_ai"
            strategy["data_source"] = "generated"
        
        # Determine stages
        complexity = self._analyze_complexity(context)
        if complexity in [ComplexityLevel.ADVANCED, ComplexityLevel.EXPERT]:
            strategy["stages"] = [
                "structure_design",
                "data_modeling",
                "formula_generation",
                "visualization_creation",
                "validation",
                "optimization"
            ]
        else:
            strategy["stages"] = [
                "structure_design",
                "data_generation",
                "basic_formatting"
            ]
        
        return strategy
    
    def _assess_template_relevance(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Assess how relevant existing templates are"""
        relevance = {
            "score": 0.0,
            "matching_templates": [],
            "adaptations_needed": []
        }
        
        # Simple heuristic for now
        domain = context.get("domain")
        if domain:
            relevance["score"] = 0.7  # Assume moderate relevance if domain matches
            relevance["matching_templates"].append(f"{domain}_standard")
        
        # Check for specific requirements that might need adaptation
        requirements = context.get("requirements", [])
        for req in requirements:
            if req not in ["visualization", "analysis", "comparison"]:
                relevance["adaptations_needed"].append(req)
                relevance["score"] -= 0.1
        
        relevance["score"] = max(0, min(1, relevance["score"]))
        return relevance
    
    def _determine_ai_scope(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Determine scope of AI generation"""
        scope = {
            "structure_generation": True,
            "data_generation": True,
            "formula_creation": True,
            "visualization_design": False,
            "insight_generation": False
        }
        
        # Adjust based on requirements
        requirements = context.get("requirements", [])
        if "visualization" in requirements:
            scope["visualization_design"] = True
        if "analysis" in requirements:
            scope["insight_generation"] = True
        
        # Adjust based on template relevance
        template_relevance = context.get("template_relevance", {}).get("score", 0)
        if template_relevance > 0.8:
            scope["structure_generation"] = False  # Use template structure
        
        return scope
    
    async def _get_ai_insights(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get AI insights about the context"""
        try:
            system_prompt = """You are an Excel generation expert. Analyze the context and provide insights about:
            1. Potential challenges in generating this Excel file
            2. Suggestions for optimal structure
            3. Data relationships to consider
            4. Best practices for this type of Excel file
            
            Provide concise, actionable insights in JSON format."""
            
            user_prompt = f"""Context:
            Domain: {context.get('domain')}
            Requirements: {context.get('requirements')}
            Time Context: {context.get('time_context')}
            Entities: {context.get('entities')}
            
            Provide insights for generating this Excel file."""
            
            response = await openai_service.chat_completion([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ])
            
            # Parse response
            import json
            try:
                insights = json.loads(response)
            except:
                insights = {
                    "challenges": ["Complex requirements may need iterative refinement"],
                    "suggestions": ["Use structured approach with clear data relationships"],
                    "best_practices": ["Follow domain-specific conventions"]
                }
            
            return insights
            
        except Exception as e:
            logger.error(f"Error getting AI insights: {str(e)}")
            return {
                "challenges": [],
                "suggestions": [],
                "best_practices": []
            }
    
    def _calculate_intent_confidence(self, intents: List[str], text: str) -> float:
        """Calculate confidence score for intent detection"""
        if not intents:
            return 0.3
        
        # Higher confidence if multiple intent keywords found
        keyword_count = sum(
            1 for intent in intents
            for keyword in self.intent_keywords.get(IntentType(intent), [])
            if keyword in text
        )
        
        confidence = min(0.5 + (keyword_count * 0.1), 1.0)
        return confidence