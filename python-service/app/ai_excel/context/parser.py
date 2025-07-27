"""
Context parser for extracting meaningful information from user requests
Uses NLP to understand user intent and extract key entities
"""

import re
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dateutil import parser as date_parser
import logging

logger = logging.getLogger(__name__)


class ContextParser:
    """Parses and extracts context from natural language requests"""
    
    def __init__(self):
        self.domain_keywords = {
            "finance": ["재무", "회계", "손익", "재무제표", "대차대조표", "현금흐름", "예산", "비용", "매출", "이익"],
            "hr": ["인사", "직원", "급여", "인력", "채용", "평가", "근태", "휴가", "조직", "부서"],
            "sales": ["영업", "판매", "매출", "고객", "거래처", "실적", "목표", "달성률", "영업이익"],
            "inventory": ["재고", "입고", "출고", "재고관리", "발주", "창고", "물류", "재고회전율"],
            "project": ["프로젝트", "일정", "진행", "마일스톤", "간트차트", "리소스", "작업", "완료율"]
        }
        
        self.time_patterns = {
            "year": r"(\d{4})년",
            "month": r"(\d{1,2})월",
            "quarter": r"([1-4])분기",
            "date": r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})",
            "relative": r"(이번|지난|다음|올해|작년|내년|이번달|지난달|다음달)"
        }
        
        self.entity_patterns = {
            "company": r"(주식회사|회사|기업|법인)\s*([가-힣A-Za-z0-9]+)",
            "amount": r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(원|달러|엔|위안|유로)?",
            "percentage": r"(\d+(?:\.\d+)?)\s*(%|퍼센트|프로)",
            "count": r"(\d+)\s*(명|개|건|회|번)"
        }
    
    def parse(self, text: str) -> Dict[str, Any]:
        """Parse text and extract context"""
        context = {
            "original_text": text,
            "domain": self._detect_domain(text),
            "entities": self._extract_entities(text),
            "time_context": self._extract_time_context(text),
            "requirements": self._extract_requirements(text),
            "constraints": self._extract_constraints(text),
            "output_preferences": self._extract_output_preferences(text)
        }
        
        # Post-process and enrich context
        context = self._enrich_context(context)
        
        return context
    
    def _detect_domain(self, text: str) -> Optional[str]:
        """Detect the primary domain from text"""
        domain_scores = {}
        
        for domain, keywords in self.domain_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text.lower())
            if score > 0:
                domain_scores[domain] = score
        
        if domain_scores:
            return max(domain_scores, key=domain_scores.get)
        
        return None
    
    def _extract_entities(self, text: str) -> Dict[str, List[Any]]:
        """Extract named entities from text"""
        entities = {
            "companies": [],
            "amounts": [],
            "percentages": [],
            "counts": [],
            "custom": []
        }
        
        # Extract companies
        company_matches = re.findall(self.entity_patterns["company"], text)
        for match in company_matches:
            company_name = match[1].strip()
            if company_name:
                entities["companies"].append(company_name)
        
        # Extract amounts
        amount_matches = re.findall(self.entity_patterns["amount"], text)
        for match in amount_matches:
            amount = float(match[0].replace(',', ''))
            currency = match[1] or "원"
            entities["amounts"].append({"value": amount, "currency": currency})
        
        # Extract percentages
        percentage_matches = re.findall(self.entity_patterns["percentage"], text)
        for match in percentage_matches:
            value = float(match[0])
            entities["percentages"].append(value)
        
        # Extract counts
        count_matches = re.findall(self.entity_patterns["count"], text)
        for match in count_matches:
            count = int(match[0])
            unit = match[1]
            entities["counts"].append({"value": count, "unit": unit})
        
        return entities
    
    def _extract_time_context(self, text: str) -> Dict[str, Any]:
        """Extract time-related context"""
        time_context = {
            "period_type": None,
            "specific_dates": [],
            "relative_time": None,
            "duration": None
        }
        
        # Check for year
        year_matches = re.findall(self.time_patterns["year"], text)
        if year_matches:
            time_context["specific_dates"].extend([{"type": "year", "value": int(y)} for y in year_matches])
        
        # Check for month
        month_matches = re.findall(self.time_patterns["month"], text)
        if month_matches:
            time_context["specific_dates"].extend([{"type": "month", "value": int(m)} for m in month_matches])
        
        # Check for quarter
        quarter_matches = re.findall(self.time_patterns["quarter"], text)
        if quarter_matches:
            time_context["period_type"] = "quarterly"
            time_context["specific_dates"].extend([{"type": "quarter", "value": int(q)} for q in quarter_matches])
        
        # Check for relative time
        relative_matches = re.findall(self.time_patterns["relative"], text)
        if relative_matches:
            time_context["relative_time"] = self._parse_relative_time(relative_matches[0])
        
        # Detect duration
        if "개월" in text:
            duration_match = re.search(r"(\d+)\s*개월", text)
            if duration_match:
                time_context["duration"] = {"value": int(duration_match.group(1)), "unit": "months"}
        
        return time_context
    
    def _parse_relative_time(self, relative_term: str) -> Dict[str, Any]:
        """Parse relative time terms"""
        now = datetime.now()
        
        mappings = {
            "이번": {"period": "current"},
            "지난": {"period": "previous"},
            "다음": {"period": "next"},
            "올해": {"year": now.year},
            "작년": {"year": now.year - 1},
            "내년": {"year": now.year + 1},
            "이번달": {"year": now.year, "month": now.month},
            "지난달": {"year": now.year, "month": now.month - 1},
            "다음달": {"year": now.year, "month": now.month + 1}
        }
        
        return mappings.get(relative_term, {"term": relative_term})
    
    def _extract_requirements(self, text: str) -> List[str]:
        """Extract specific requirements from text"""
        requirements = []
        
        # Common requirement patterns
        requirement_patterns = [
            r"포함(?:해|하여|해서)(?:\s*)(?:주세요|줘)",
            r"필요(?:해요|합니다)",
            r"있어야(?:\s*)(?:해요|합니다)",
            r"만들어(?:\s*)(?:주세요|줘)",
            r"생성(?:해|하여)(?:\s*)(?:주세요|줘)",
            r"추가(?:해|하여)(?:\s*)(?:주세요|줘)"
        ]
        
        for pattern in requirement_patterns:
            matches = re.findall(f"([^.!?]+)(?:{pattern})", text)
            requirements.extend(matches)
        
        # Extract specific feature requirements
        if "차트" in text or "그래프" in text:
            requirements.append("visualization")
        if "분석" in text:
            requirements.append("analysis")
        if "비교" in text:
            requirements.append("comparison")
        if "예측" in text or "전망" in text:
            requirements.append("forecast")
        
        return list(set(requirements))
    
    def _extract_constraints(self, text: str) -> Dict[str, Any]:
        """Extract constraints and limitations"""
        constraints = {
            "size_limits": None,
            "data_constraints": [],
            "format_constraints": []
        }
        
        # Check for size constraints
        size_patterns = [
            r"(\d+)\s*행",
            r"(\d+)\s*열",
            r"(\d+)\s*개?\s*이하",
            r"최대\s*(\d+)"
        ]
        
        for pattern in size_patterns:
            match = re.search(pattern, text)
            if match:
                constraints["size_limits"] = int(match.group(1))
        
        # Check for format constraints
        if "간단" in text or "심플" in text:
            constraints["format_constraints"].append("simple")
        if "상세" in text or "자세" in text:
            constraints["format_constraints"].append("detailed")
        
        return constraints
    
    def _extract_output_preferences(self, text: str) -> Dict[str, Any]:
        """Extract output format preferences"""
        preferences = {
            "language": "ko",  # Default Korean
            "format_style": "standard",
            "include_charts": False,
            "include_summary": False
        }
        
        # Check for language preference
        if any(word in text.lower() for word in ["english", "영어", "영문"]):
            preferences["language"] = "en"
        
        # Check for chart preference
        if any(word in text for word in ["차트", "그래프", "시각화"]):
            preferences["include_charts"] = True
        
        # Check for summary preference
        if any(word in text for word in ["요약", "정리", "개요"]):
            preferences["include_summary"] = True
        
        return preferences
    
    def _enrich_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich context with derived information"""
        # Add fiscal year info if dealing with finance
        if context["domain"] == "finance":
            current_year = datetime.now().year
            if not context["time_context"]["specific_dates"]:
                context["time_context"]["specific_dates"].append({
                    "type": "year",
                    "value": current_year
                })
        
        # Add default company if none specified
        if context["domain"] in ["finance", "hr"] and not context["entities"]["companies"]:
            context["entities"]["companies"].append("우리회사")
        
        # Add metadata
        context["metadata"] = {
            "parsed_at": datetime.now().isoformat(),
            "confidence": self._calculate_confidence(context)
        }
        
        return context
    
    def _calculate_confidence(self, context: Dict[str, Any]) -> float:
        """Calculate confidence score for parsed context"""
        score = 0.0
        
        # Domain detection adds confidence
        if context["domain"]:
            score += 0.3
        
        # Entities add confidence
        total_entities = sum(len(v) if isinstance(v, list) else 1 
                           for v in context["entities"].values() if v)
        score += min(0.3, total_entities * 0.1)
        
        # Time context adds confidence
        if context["time_context"]["specific_dates"] or context["time_context"]["relative_time"]:
            score += 0.2
        
        # Requirements add confidence
        if context["requirements"]:
            score += 0.2
        
        return min(1.0, score)