"""
Enhanced Template Metadata Model
템플릿 메타데이터 확장 모델
"""
from typing import Dict, List, Any, Optional, Union
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime


class TemplateCategory(Enum):
    FINANCE = "finance"
    HR = "hr" 
    SALES = "sales"
    OPERATIONS = "operations"
    MARKETING = "marketing"
    PROJECT_MANAGEMENT = "project_management"
    INVENTORY = "inventory"
    GENERAL = "general"


class TemplateComplexity(Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class UsageContext(Enum):
    DAILY_OPERATIONS = "daily_operations"
    MONTHLY_REPORTS = "monthly_reports"
    QUARTERLY_ANALYSIS = "quarterly_analysis"
    ANNUAL_PLANNING = "annual_planning"
    AD_HOC_ANALYSIS = "ad_hoc_analysis"


@dataclass
class FieldDefinition:
    """개별 필드 정의"""
    name: str
    data_type: str  # text, number, date, currency, percentage, boolean
    description: str
    is_required: bool = False
    validation_rules: Dict[str, Any] = field(default_factory=dict)
    example_values: List[str] = field(default_factory=list)
    calculation_formula: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)  # 의존하는 다른 필드들
    business_logic: Optional[str] = None


@dataclass
class SectionDefinition:
    """템플릿 섹션 정의"""
    name: str
    description: str
    purpose: str
    fields: List[FieldDefinition] = field(default_factory=list)
    calculation_logic: Optional[str] = None
    validation_rules: List[str] = field(default_factory=list)


@dataclass
class WorkflowStep:
    """사용 워크플로우 단계"""
    step_number: int
    title: str
    description: str
    required_fields: List[str] = field(default_factory=list)
    tips: List[str] = field(default_factory=list)
    common_mistakes: List[str] = field(default_factory=list)


@dataclass
class EnhancedTemplateMetadata:
    """확장된 템플릿 메타데이터"""
    
    # 기본 정보
    template_id: str
    name: str
    description: str
    category: TemplateCategory
    purpose: str  # 이 템플릿의 주요 목적
    subcategory: Optional[str] = None
    business_use_cases: List[str] = field(default_factory=list)  # 구체적인 사용 사례들
    target_audience: List[str] = field(default_factory=list)  # 대상 사용자 (CFO, 회계사, 매니저 등)
    usage_context: List[UsageContext] = field(default_factory=list)
    
    # 기술적 정보
    complexity: TemplateComplexity = TemplateComplexity.INTERMEDIATE
    estimated_completion_time: str = "30 minutes"  # 예상 작성 시간
    prerequisites: List[str] = field(default_factory=list)  # 사전 준비사항
    
    # 구조적 정보
    sections: List[SectionDefinition] = field(default_factory=list)
    key_metrics: List[str] = field(default_factory=list)  # 주요 지표들
    calculation_methods: Dict[str, str] = field(default_factory=dict)
    
    # 사용 가이드
    workflow_steps: List[WorkflowStep] = field(default_factory=list)
    tips_and_best_practices: List[str] = field(default_factory=list)
    common_errors: List[str] = field(default_factory=list)
    troubleshooting_guide: Dict[str, str] = field(default_factory=dict)
    
    # AI 지원 정보
    ai_prompts: Dict[str, str] = field(default_factory=dict)  # AI가 사용할 프롬프트들
    context_keywords: List[str] = field(default_factory=list)  # 맥락 이해를 위한 키워드
    semantic_tags: List[str] = field(default_factory=list)  # 의미적 태그
    
    # 다국어 지원
    supported_languages: List[str] = field(default_factory=lambda: ["ko", "en"])
    localization_notes: Dict[str, str] = field(default_factory=dict)
    
    # 메타데이터
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    version: str = "1.0"
    author: Optional[str] = None
    source: Optional[str] = None  # 출처 (회사, 기관 등)
    
    # 관련 템플릿
    related_templates: List[str] = field(default_factory=list)
    parent_template: Optional[str] = None
    variations: List[str] = field(default_factory=list)


# 예시: Cash Flow 템플릿 메타데이터
CASH_FLOW_METADATA = EnhancedTemplateMetadata(
    template_id="cash_flow_management_v2",
    name="현금흐름 관리 템플릿",
    description="기업의 현금 유입과 유출을 체계적으로 관리하고 예측하기 위한 종합적인 템플릿",
    category=TemplateCategory.FINANCE,
    subcategory="현금관리",
    
    purpose="기업의 현금흐름을 월별로 추적하고 향후 6개월간의 현금 포지션을 예측하여 자금 운용 계획을 수립",
    business_use_cases=[
        "월별 현금흐름 모니터링",
        "자금 부족 시점 사전 예측",
        "투자 및 대출 계획 수립",
        "계절성 비즈니스의 현금 관리",
        "은행 대출 신청 시 현금흐름 증빙"
    ],
    target_audience=["CFO", "재무팀장", "회계담당자", "중소기업 대표"],
    usage_context=[UsageContext.MONTHLY_REPORTS, UsageContext.QUARTERLY_ANALYSIS],
    
    complexity=TemplateComplexity.INTERMEDIATE,
    estimated_completion_time="45분",
    prerequisites=[
        "과거 3개월간의 수입/지출 데이터",
        "고정비 및 변동비 분류",
        "예상 매출 계획",
        "기존 대출 및 리스 정보"
    ],
    
    sections=[
        SectionDefinition(
            name="수입 섹션",
            description="모든 현금 유입 항목을 기록",
            purpose="매출, 투자 수익, 기타 수입을 체계적으로 추적",
            fields=[
                FieldDefinition(
                    name="매출액",
                    data_type="currency",
                    description="제품/서비스 판매로 인한 현금 수입",
                    is_required=True,
                    example_values=["50,000,000", "75,000,000"],
                    business_logic="세금 제외한 실제 수취 가능한 금액"
                ),
                FieldDefinition(
                    name="기타수입",
                    data_type="currency", 
                    description="이자수익, 배당금, 기타 운영외 수입",
                    is_required=False,
                    example_values=["500,000", "1,200,000"]
                )
            ]
        ),
        SectionDefinition(
            name="지출 섹션",
            description="모든 현금 유출 항목을 기록",
            purpose="운영비, 투자, 금융비용을 체계적으로 관리",
            fields=[
                FieldDefinition(
                    name="인건비",
                    data_type="currency",
                    description="급여, 상여금, 사회보험료 등 인건비 총액",
                    is_required=True,
                    example_values=["25,000,000", "30,000,000"],
                    business_logic="실제 지급되는 현금 기준"
                )
            ]
        )
    ],
    
    key_metrics=[
        "순현금흐름 (Net Cash Flow)",
        "누적현금잔액 (Cumulative Cash Balance)", 
        "현금전환주기 (Cash Conversion Cycle)",
        "현금안전마진 (Cash Safety Margin)"
    ],
    
    calculation_methods={
        "순현금흐름": "총수입 - 총지출",
        "누적현금잔액": "기초현금 + 순현금흐름",
        "현금비율": "현금잔액 / 월평균지출"
    },
    
    workflow_steps=[
        WorkflowStep(
            step_number=1,
            title="기초 데이터 수집",
            description="현금흐름 작성에 필요한 기본 데이터를 수집합니다",
            required_fields=["기초현금잔액", "전월실적"],
            tips=[
                "은행 잔액증명서를 통해 정확한 기초잔액 확인",
                "미수금/미지급금 고려하여 실제 현금기준으로 작성"
            ],
            common_mistakes=[
                "장부상 매출과 현금수입 혼동",
                "미지급 비용을 현금지출로 오인"
            ]
        ),
        WorkflowStep(
            step_number=2,
            title="수입 항목 입력",
            description="예상되는 모든 현금 유입을 월별로 입력합니다",
            required_fields=["매출액", "기타수입"],
            tips=[
                "계절성이 있는 경우 과거 패턴 참고",
                "보수적으로 추정하여 리스크 관리"
            ]
        )
    ],
    
    tips_and_best_practices=[
        "보수적 추정: 수입은 90%, 지출은 110%로 계산하여 안전마진 확보",
        "주간 단위로 검토하여 실제와 예측의 차이 분석",
        "시나리오 분석: 최선/보통/최악의 경우를 모두 준비"
    ],
    
    ai_prompts={
        "data_validation": "이 현금흐름표에서 비정상적인 수치나 패턴이 있는지 검토해주세요",
        "trend_analysis": "과거 3개월 데이터를 바탕으로 향후 현금흐름 트렌드를 분석해주세요", 
        "optimization": "현금 관리 효율성을 높일 수 있는 개선 방안을 제안해주세요"
    },
    
    context_keywords=[
        "현금흐름", "cash flow", "자금관리", "유동성", "운전자본",
        "매출채권", "재고자산", "매입채무", "현금전환주기"
    ],
    
    semantic_tags=[
        "재무관리", "현금예측", "자금계획", "리스크관리", "의사결정지원"
    ]
)