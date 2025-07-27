"""
AI Analysis Prompts Management System
Implements hybrid approach: explicit rules + AI autonomy
"""
from typing import Dict, Any, List, Optional
from enum import Enum
import json


class AnalysisContext(Enum):
    """Context types for different analysis scenarios"""
    FINANCIAL = "financial"
    INVENTORY = "inventory"
    HR = "hr"
    SALES = "sales"
    GENERAL = "general"
    SCIENTIFIC = "scientific"
    PROJECT = "project"


class AIAnalysisPrompts:
    """
    Manages AI prompts with hybrid approach:
    - Explicit business rules for consistency
    - AI autonomy for complex reasoning
    """
    
    # Level 1: Explicit Business Rules (명시적 규칙)
    BUSINESS_RULES = {
        "universal": """
        필수 비즈니스 로직 검증:
        1. 수익 = 매출 - 비용 (Revenue = Sales - Costs)
        2. 비율의 합 = 100% (구성 비율인 경우)
        3. 시계열 데이터의 순서 일관성
        4. 양수여야 하는 값: 수량, 단가, 면적
        5. 날짜 순서: 시작일 <= 종료일
        """,
        
        "financial": """
        재무 관련 필수 규칙:
        1. 자산 = 부채 + 자본 (대차대조표 균형)
        2. 현금흐름 = 영업활동 + 투자활동 + 재무활동
        3. 이익률 = (이익 / 매출) * 100
        4. ROE = 당기순이익 / 자기자본
        5. 부채비율 = 부채 / 자기자본
        """,
        
        "inventory": """
        재고 관련 필수 규칙:
        1. 기말재고 = 기초재고 + 매입 - 매출
        2. 재고회전율 = 매출원가 / 평균재고
        3. 안전재고 >= 0
        4. 리드타임 > 0
        """,
        
        "sales": """
        판매 관련 필수 규칙:
        1. 총 판매액 = 단가 × 수량
        2. 할인율 <= 100%
        3. 순매출 = 총매출 - 반품 - 할인
        4. 판매수수료 = 판매액 × 수수료율
        """
    }
    
    # Level 2: Pattern Detection Thresholds (패턴 감지 임계값)
    PATTERN_THRESHOLDS = {
        "universal": {
            "monthly_change": 30,  # 월별 변화율 ±30% 초과 시 이상
            "ratio_bounds": (0, 100),  # 비율 데이터 범위
            "date_range": (1900, 2100),  # 유효 날짜 범위
            "outlier_std": 3,  # 표준편차 3배 초과 시 이상값
        },
        
        "financial": {
            "profit_margin_range": (-50, 50),  # 이익률 정상 범위 %
            "debt_ratio_warning": 200,  # 부채비율 경고 수준 %
            "growth_rate_extreme": 100,  # 성장률 이상치 %
        },
        
        "inventory": {
            "stockout_threshold": 0,  # 재고 부족 임계값
            "overstock_ratio": 3,  # 과잉재고 비율 (평균 대비)
            "turnover_low": 2,  # 낮은 재고회전율
            "turnover_high": 12,  # 높은 재고회전율
        }
    }
    
    # Level 3: AI Autonomous Guidelines (AI 자율 판단 가이드라인)
    AUTONOMOUS_GUIDELINES = """
    다음 영역은 당신의 전문적 판단으로 분석하세요:
    
    1. **컨텍스트 기반 이상 감지**
       - 업종별 특성을 고려한 정상 범위 판단
       - 계절성, 트렌드 등 시계열 패턴 인식
       - 연관 데이터 간 논리적 일관성
    
    2. **복잡한 관계 분석**
       - 다중 시트 간 데이터 정합성
       - 간접적 참조 관계의 타당성
       - 숨겨진 순환 참조 위험
    
    3. **데이터 품질 평가**
       - 누락된 핵심 데이터 식별
       - 중복 데이터의 의도성 판단
       - 이상값의 비즈니스적 타당성
    
    4. **최적화 제안**
       - 구조 개선 기회
       - 성능 최적화 방안
       - 가독성 및 유지보수성 향상
    
    분석 시 고려사항:
    - 파일의 전체적인 목적과 맥락
    - 사용자의 의도 추론
    - 최소 변경으로 최대 효과
    - 실무적 타당성
    """
    
    def __init__(self):
        self.custom_rules = {}
        self.context_cache = {}
    
    def generate_analysis_prompt(
        self, 
        file_context: Dict[str, Any], 
        analysis_options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate comprehensive analysis prompt with hybrid approach
        
        Args:
            file_context: Information about the Excel file
            analysis_options: Optional analysis preferences
            
        Returns:
            Complete prompt for AI analysis
        """
        # Determine context type
        context_type = self._determine_context_type(file_context)
        
        # Build layered prompt
        prompt_parts = []
        
        # 1. Add explicit business rules
        prompt_parts.append("=== 명시적 비즈니스 규칙 ===")
        prompt_parts.append(self.BUSINESS_RULES["universal"])
        if context_type != AnalysisContext.GENERAL:
            specific_rules = self.BUSINESS_RULES.get(context_type.value, "")
            if specific_rules:
                prompt_parts.append(f"\n{context_type.value.upper()} 특화 규칙:")
                prompt_parts.append(specific_rules)
        
        # 2. Add pattern thresholds
        prompt_parts.append("\n=== 패턴 감지 기준 ===")
        thresholds = self._get_applicable_thresholds(context_type)
        prompt_parts.append(self._format_thresholds(thresholds))
        
        # 3. Add file-specific context
        prompt_parts.append("\n=== 파일 컨텍스트 ===")
        prompt_parts.append(self._format_file_context(file_context))
        
        # 4. Add AI autonomous guidelines
        prompt_parts.append("\n=== AI 자율 분석 영역 ===")
        prompt_parts.append(self.AUTONOMOUS_GUIDELINES)
        
        # 5. Add specific analysis focus if provided
        if analysis_options and "focus_areas" in analysis_options:
            prompt_parts.append("\n=== 중점 분석 영역 ===")
            prompt_parts.append(self._format_focus_areas(analysis_options["focus_areas"]))
        
        # 6. Add output format specification
        prompt_parts.append("\n=== 출력 형식 ===")
        prompt_parts.append(self._get_output_format())
        
        return "\n".join(prompt_parts)
    
    def add_custom_rule(self, rule_name: str, rule_content: str, context: Optional[str] = None):
        """Add custom business rule"""
        if context not in self.custom_rules:
            self.custom_rules[context] = {}
        self.custom_rules[context][rule_name] = rule_content
    
    def _determine_context_type(self, file_context: Dict[str, Any]) -> AnalysisContext:
        """Determine the context type based on file content"""
        # Check sheet names and column headers for context clues
        sheets = file_context.get("sheets", [])
        all_columns = []
        
        for sheet in sheets:
            columns = sheet.get("columns", [])
            all_columns.extend([col.lower() for col in columns])
        
        # Financial indicators
        financial_keywords = ["revenue", "profit", "asset", "liability", "balance", 
                            "매출", "이익", "자산", "부채", "손익"]
        if any(keyword in str(all_columns) for keyword in financial_keywords):
            return AnalysisContext.FINANCIAL
        
        # Inventory indicators
        inventory_keywords = ["inventory", "stock", "quantity", "warehouse",
                            "재고", "수량", "입고", "출고"]
        if any(keyword in str(all_columns) for keyword in inventory_keywords):
            return AnalysisContext.INVENTORY
        
        # Sales indicators
        sales_keywords = ["sales", "customer", "order", "price",
                         "판매", "고객", "주문", "단가"]
        if any(keyword in str(all_columns) for keyword in sales_keywords):
            return AnalysisContext.SALES
        
        # HR indicators
        hr_keywords = ["employee", "salary", "department", "position",
                      "직원", "급여", "부서", "직급"]
        if any(keyword in str(all_columns) for keyword in hr_keywords):
            return AnalysisContext.HR
        
        return AnalysisContext.GENERAL
    
    def _get_applicable_thresholds(self, context_type: AnalysisContext) -> Dict[str, Any]:
        """Get applicable thresholds for the context"""
        thresholds = self.PATTERN_THRESHOLDS["universal"].copy()
        
        if context_type.value in self.PATTERN_THRESHOLDS:
            thresholds.update(self.PATTERN_THRESHOLDS[context_type.value])
        
        return thresholds
    
    def _format_thresholds(self, thresholds: Dict[str, Any]) -> str:
        """Format thresholds for prompt"""
        lines = []
        for key, value in thresholds.items():
            if isinstance(value, tuple):
                lines.append(f"- {key}: {value[0]} ~ {value[1]}")
            else:
                lines.append(f"- {key}: {value}")
        return "\n".join(lines)
    
    def _format_file_context(self, file_context: Dict[str, Any]) -> str:
        """Format file context information"""
        context_info = []
        
        # Basic info
        context_info.append(f"파일명: {file_context.get('filename', 'Unknown')}")
        context_info.append(f"시트 수: {len(file_context.get('sheets', []))}")
        
        # Sheet summaries
        for sheet in file_context.get('sheets', [])[:3]:  # First 3 sheets
            context_info.append(f"\n시트 '{sheet.get('name', 'Unknown')}':")
            context_info.append(f"  - 크기: {sheet.get('rows', 0)} x {sheet.get('columns', 0)}")
            context_info.append(f"  - 데이터 타입: {', '.join(sheet.get('data_types', []))}")
        
        return "\n".join(context_info)
    
    def _format_focus_areas(self, focus_areas: List[str]) -> str:
        """Format specific focus areas for analysis"""
        return "다음 영역에 특별히 주의하여 분석하세요:\n" + "\n".join(f"- {area}" for area in focus_areas)
    
    def _get_output_format(self) -> str:
        """Specify the expected output format"""
        return """
        발견된 오류를 다음 JSON 형식으로 반환하세요:
        
        ```json
        {
            "errors": [
                {
                    "type": "logic|semantic|quality|structural|relationship",
                    "severity": "critical|high|medium|low",
                    "location": {
                        "sheet": "시트명",
                        "cell": "A1" 또는 "range": "A1:B10"
                    },
                    "description": "오류에 대한 명확한 설명",
                    "business_impact": "비즈니스 영향도 설명",
                    "confidence": 0.0-1.0,
                    "fix": "구체적인 수정 방안",
                    "alternative_fixes": ["대안1", "대안2"],
                    "metadata": {
                        "rule_violated": "위반된 규칙명",
                        "actual_value": "실제값",
                        "expected_value": "기대값"
                    }
                }
            ],
            "insights": [
                "전체적인 데이터 품질에 대한 통찰",
                "개선 기회에 대한 제안",
                "잠재적 위험 요소"
            ],
            "summary": {
                "total_errors": 0,
                "critical_issues": 0,
                "data_quality_score": 0.0-1.0,
                "main_concerns": ["주요 우려사항 1", "주요 우려사항 2"]
            }
        }
        ```
        
        주의사항:
        - 확신도가 낮은 경우(< 0.7) 명시적으로 표시
        - 비즈니스 영향이 큰 오류를 우선 보고
        - 실무적으로 실행 가능한 수정안 제시
        """
    
    def generate_domain_specific_prompt(
        self,
        domain: str,
        file_data: Dict[str, Any],
        user_concern: Optional[str] = None
    ) -> str:
        """Generate domain-specific analysis prompt"""
        
        base_prompt = self.generate_analysis_prompt(
            file_data,
            {"focus_areas": [domain]}
        )
        
        # Add domain-specific enhancements
        domain_prompts = {
            "korean_financial": """
            
            한국 재무제표 특화 분석:
            - K-IFRS/K-GAAP 준수 여부
            - 계정과목 한글/영문 일관성
            - 단위 표시 일관성 (원, 천원, 백만원)
            - 연결/별도 재무제표 구분
            - 주석 참조 정합성
            """,
            
            "korean_tax": """
            
            한국 세무 관련 검증:
            - 부가가치세 계산 정확성
            - 원천징수 계산 검증
            - 세금계산서 발행 내역 정합성
            - 과세/면세 구분 정확성
            """,
            
            "multi_currency": """
            
            다중 통화 거래 검증:
            - 환율 적용 일관성
            - 환산손익 계산 정확성
            - 통화별 잔액 정합성
            - 환율 날짜 일치 여부
            """
        }
        
        if domain in domain_prompts:
            base_prompt += domain_prompts[domain]
        
        if user_concern:
            base_prompt += f"\n\n사용자 특별 관심사항:\n{user_concern}"
        
        return base_prompt
    
    def adjust_for_confidence(self, prompt: str, confidence_level: str = "balanced") -> str:
        """Adjust prompt based on desired confidence level"""
        
        confidence_adjustments = {
            "conservative": """
            
            보수적 분석 접근:
            - 확신도 0.8 이상인 오류만 보고
            - 명확한 규칙 위반 중심으로 분석
            - 가능성보다는 확실성 위주
            """,
            
            "balanced": """
            
            균형잡힌 분석 접근:
            - 확신도 0.6 이상 오류 보고
            - 규칙 기반과 패턴 기반 균형
            - 중요도에 따른 선별적 보고
            """,
            
            "aggressive": """
            
            적극적 분석 접근:
            - 확신도 0.4 이상 모든 잠재 오류 보고
            - 패턴과 이상징후 적극 탐지
            - 예방적 차원의 포괄적 분석
            """
        }
        
        return prompt + confidence_adjustments.get(confidence_level, confidence_adjustments["balanced"])