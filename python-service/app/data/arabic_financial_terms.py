#!/usr/bin/env python3
"""
아랍어 재무 용어 사전
Arabic Financial Terms Dictionary

다국어 OCR 시스템에서 아랍어 재무 문서 인식을 위한 포괄적인 용어 사전
Comprehensive terminology dictionary for Arabic financial document recognition in multilingual OCR system
"""

ARABIC_FINANCIAL_TERMS = {
    # 재무제표 및 보고서 - Financial Statements & Reports
    "financial_statements": [
        "القوائم المالية",           # Financial Statements
        "البيانات المالية",         # Financial Data
        "التقارير المالية",         # Financial Reports
        "الحسابات الختامية",        # Final Accounts
        "التقرير السنوي",           # Annual Report
        "التقرير الربعي",           # Quarterly Report
        "التقرير الشهري",           # Monthly Report
    ],
    
    # 손익계산서 - Income Statement
    "income_statement": [
        "قائمة الدخل",              # Income Statement
        "قائمة الأرباح والخسائر",   # Profit & Loss Statement
        "بيان الدخل",               # Income Statement
        "قائمة النتائج",            # Results Statement
        "قائمة العمليات",           # Operations Statement
    ],
    
    # 대차대조표 - Balance Sheet
    "balance_sheet": [
        "الميزانية العمومية",       # Balance Sheet
        "قائمة المركز المالي",      # Statement of Financial Position
        "بيان المركز المالي",       # Financial Position Statement
        "الميزانية",                # Balance
        "قائمة الأصول والخصوم",     # Assets & Liabilities Statement
    ],
    
    # 현금흐름표 - Cash Flow Statement
    "cash_flow": [
        "قائمة التدفقات النقدية",    # Cash Flow Statement
        "بيان التدفق النقدي",       # Cash Flow Statement
        "تدفق الأموال",             # Money Flow
        "التدفقات النقدية",         # Cash Flows
        "الحركة النقدية",           # Cash Movement
    ],
    
    # 수익 및 매출 - Revenue & Sales
    "revenue": [
        "الإيرادات",                # Revenue
        "المبيعات",                 # Sales
        "الدخل",                    # Income
        "العائدات",                 # Returns/Revenue
        "الأرباح",                  # Profits
        "الإيرادات التشغيلية",      # Operating Revenue
        "إيرادات المبيعات",         # Sales Revenue
        "الدخل الإجمالي",           # Gross Income
    ],
    
    # 비용 및 지출 - Costs & Expenses
    "expenses": [
        "التكاليف",                 # Costs
        "المصروفات",               # Expenses
        "النفقات",                  # Expenditures
        "المصاريف",                # Expenses
        "التكاليف التشغيلية",       # Operating Costs
        "المصاريف الإدارية",        # Administrative Expenses
        "مصاريف البيع",             # Selling Expenses
        "التكاليف المباشرة",        # Direct Costs
        "التكاليف غير المباشرة",    # Indirect Costs
    ],
    
    # 이익 - Profit
    "profit": [
        "الربح",                    # Profit
        "الأرباح",                  # Profits
        "الربح الإجمالي",           # Gross Profit
        "الربح الصافي",             # Net Profit
        "الربح التشغيلي",           # Operating Profit
        "ربح السهم",                # Earnings Per Share
        "الأرباح المحتجزة",         # Retained Earnings
        "الأرباح الموزعة",          # Distributed Profits
    ],
    
    # 손실 - Loss
    "loss": [
        "الخسارة",                  # Loss
        "الخسائر",                  # Losses
        "الخسارة الصافية",          # Net Loss
        "خسارة تشغيلية",            # Operating Loss
        "خسائر الائتمان",           # Credit Losses
    ],
    
    # 자산 - Assets
    "assets": [
        "الأصول",                   # Assets
        "الممتلكات",                # Properties
        "الأصول الثابتة",           # Fixed Assets
        "الأصول المتداولة",         # Current Assets
        "الأصول غير الملموسة",      # Intangible Assets
        "الاستثمارات",              # Investments
        "النقدية",                  # Cash
        "البنوك",                   # Banks
        "المخزون",                  # Inventory
        "المدينون",                 # Debtors
        "الذمم المدينة",            # Accounts Receivable
    ],
    
    # 부채 - Liabilities
    "liabilities": [
        "الخصوم",                   # Liabilities
        "الالتزامات",               # Obligations
        "الديون",                   # Debts
        "الخصوم المتداولة",         # Current Liabilities
        "الخصوم غير المتداولة",     # Non-current Liabilities
        "القروض",                   # Loans
        "الدائنون",                 # Creditors
        "الذمم الدائنة",            # Accounts Payable
        "المستحقات",                # Accruals
    ],
    
    # 자본 - Equity
    "equity": [
        "حقوق الملكية",             # Equity/Ownership Rights
        "رأس المال",                # Capital
        "حقوق المساهمين",           # Shareholders' Equity
        "رأس المال المدفوع",        # Paid-up Capital
        "الاحتياطيات",              # Reserves
        "العلاوات",                 # Premiums
    ],
    
    # 통화 및 금액 - Currency & Amounts
    "currency": [
        "ريال",                     # Riyal (Saudi, Qatar, etc.)
        "درهم",                     # Dirham (UAE, Morocco)
        "دينار",                    # Dinar (Kuwait, Jordan, etc.)
        "جنيه",                     # Pound (Egypt, Sudan)
        "ليرة",                     # Lira (Lebanon, Syria)
        "شيكل",                     # Shekel (Palestine/Israel)
        "دولار",                    # Dollar
        "يورو",                     # Euro
    ],
    
    # 금융 비율 - Financial Ratios
    "ratios": [
        "النسب المالية",            # Financial Ratios
        "نسبة السيولة",             # Liquidity Ratio
        "نسبة الربحية",             # Profitability Ratio
        "نسبة المديونية",           # Debt Ratio
        "العائد على الاستثمار",     # Return on Investment (ROI)
        "العائد على الأصول",        # Return on Assets (ROA)
        "العائد على حقوق الملكية",   # Return on Equity (ROE)
    ],
    
    # 회계 계정 - Accounting Accounts
    "accounts": [
        "الحسابات",                 # Accounts
        "دليل الحسابات",            # Chart of Accounts
        "الحساب الجاري",            # Current Account
        "حساب التوفير",             # Savings Account
        "حساب الاستثمار",           # Investment Account
    ],
    
    # 세금 - Taxes
    "taxes": [
        "الضرائب",                  # Taxes
        "ضريبة الدخل",              # Income Tax
        "ضريبة القيمة المضافة",     # Value Added Tax (VAT)
        "الزكاة",                   # Zakat (Islamic tax)
        "الرسوم",                   # Fees
    ],
    
    # 감사 - Audit
    "audit": [
        "المراجعة",                 # Audit/Review
        "التدقيق",                  # Auditing
        "مراجع الحسابات",           # Auditor
        "المراجعة الداخلية",        # Internal Audit
        "المراجعة الخارجية",        # External Audit
    ],
    
    # 예산 - Budget
    "budget": [
        "الميزانية",                # Budget
        "التخطيط المالي",           # Financial Planning
        "التنبؤات المالية",         # Financial Forecasts
        "الموازنة",                 # Budget
    ],
    
    # 은행 및 금융기관 - Banks & Financial Institutions
    "banking": [
        "البنك",                    # Bank
        "المصرف",                   # Bank
        "المؤسسة المالية",          # Financial Institution
        "بنك الاستثمار",            # Investment Bank
        "البنك المركزي",            # Central Bank
        "شركة التأمين",             # Insurance Company
    ],
    
    # 주식 및 증권 - Stocks & Securities
    "securities": [
        "الأسهم",                   # Stocks/Shares
        "السندات",                  # Bonds
        "الأوراق المالية",          # Securities
        "البورصة",                  # Stock Exchange
        "السوق المالي",             # Financial Market
        "المحفظة الاستثمارية",       # Investment Portfolio
    ],
    
    # 숫자 및 계산 용어 - Numbers & Calculation Terms
    "numbers": [
        "إجمالي",                   # Total
        "صافي",                     # Net
        "مجموع",                    # Sum
        "متوسط",                    # Average
        "نسبة مئوية",               # Percentage
        "معدل",                     # Rate
        "رصيد",                     # Balance
        "فرق",                      # Difference
        "زيادة",                    # Increase
        "نقص",                      # Decrease
    ],
    
    # 시간 기간 - Time Periods
    "periods": [
        "سنوي",                     # Annual
        "ربعي",                     # Quarterly
        "شهري",                     # Monthly
        "يومي",                     # Daily
        "أسبوعي",                   # Weekly
        "السنة المالية",            # Fiscal Year
        "الربع الأول",              # First Quarter
        "الربع الثاني",             # Second Quarter
        "الربع الثالث",             # Third Quarter
        "الربع الرابع",             # Fourth Quarter
    ]
}

# 모든 용어를 하나의 리스트로 통합
ALL_ARABIC_FINANCIAL_TERMS = []
for category, terms in ARABIC_FINANCIAL_TERMS.items():
    ALL_ARABIC_FINANCIAL_TERMS.extend(terms)

# 중복 제거
ALL_ARABIC_FINANCIAL_TERMS = list(set(ALL_ARABIC_FINANCIAL_TERMS))

# 아랍어 숫자
ARABIC_NUMBERS = {
    "western": ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"],
    "eastern": ["٠", "١", "٢", "٣", "٤", "٥", "٦", "٧", "٨", "٩"]
}

# 아랍어 통화 패턴
ARABIC_CURRENCY_PATTERNS = [
    r'[\d,]+(?:\.\d+)?\s*ريال',      # Riyal
    r'[\d,]+(?:\.\d+)?\s*درهم',      # Dirham
    r'[\d,]+(?:\.\d+)?\s*دينار',     # Dinar
    r'[\d,]+(?:\.\d+)?\s*جنيه',      # Pound
    r'[\d,]+(?:\.\d+)?\s*ليرة',      # Lira
    r'[\d,]+(?:\.\d+)?\s*شيكل',      # Shekel
    r'[\d,]+(?:\.\d+)?\s*دولار',     # Dollar
    r'[\d,]+(?:\.\d+)?\s*يورو',      # Euro
]

def get_arabic_financial_terms_by_category(category: str = None):
    """
    카테고리별 아랍어 재무 용어 반환
    
    Args:
        category: 용어 카테고리 (None이면 모든 카테고리)
    
    Returns:
        list: 해당 카테고리의 용어 리스트
    """
    if category is None:
        return ALL_ARABIC_FINANCIAL_TERMS
    
    return ARABIC_FINANCIAL_TERMS.get(category, [])

def is_arabic_financial_text(text: str) -> tuple:
    """
    텍스트가 아랍어 재무 문서인지 판단
    
    Args:
        text: 분석할 텍스트
    
    Returns:
        tuple: (is_financial: bool, score: float, found_terms: list)
    """
    if not text:
        return False, 0.0, []
    
    found_terms = []
    total_score = 0
    
    # 아랍어 재무 용어 검색
    for term in ALL_ARABIC_FINANCIAL_TERMS:
        if term in text:
            found_terms.append(term)
            # 용어 길이에 따라 점수 부여 (긴 용어일수록 높은 점수)
            total_score += len(term) * 2
    
    # 아랍어 통화 패턴 검색
    import re
    for pattern in ARABIC_CURRENCY_PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            found_terms.extend(matches)
            total_score += len(matches) * 10
    
    # 신뢰도 계산 (0.0 ~ 1.0)
    confidence = min(1.0, total_score / 100.0)
    is_financial = len(found_terms) > 0 and confidence > 0.3
    
    return is_financial, confidence, found_terms

if __name__ == "__main__":
    # 테스트 예제
    test_text = "القوائم المالية للشركة تظهر إيرادات بقيمة 1,000,000 ريال والربح الصافي 250,000 ريال"
    
    is_financial, confidence, terms = is_arabic_financial_text(test_text)
    
    print("=== 아랍어 재무 용어 사전 테스트 ===")
    print(f"텍스트: {test_text}")
    print(f"재무 문서 여부: {is_financial}")
    print(f"신뢰도: {confidence:.2f}")
    print(f"발견된 용어: {terms}")
    print(f"\n전체 아랍어 재무 용어 수: {len(ALL_ARABIC_FINANCIAL_TERMS)}개")
    
    # 카테고리별 용어 수 출력
    print("\n=== 카테고리별 용어 수 ===")
    for category, terms in ARABIC_FINANCIAL_TERMS.items():
        print(f"{category}: {len(terms)}개")