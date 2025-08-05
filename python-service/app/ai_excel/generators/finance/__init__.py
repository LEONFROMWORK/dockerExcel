"""
Finance domain generators
Provides specialized generators for financial Excel files
"""

from typing import Dict, Any
import logging
import pandas as pd
from datetime import datetime

from .income_statement import IncomeStatementGenerator
from ...core.base_generator import BaseExcelGenerator


logger = logging.getLogger(__name__)


class FinanceGenerator(BaseExcelGenerator):
    """Main finance domain generator"""

    def __init__(self):
        super().__init__()
        self.income_statement_gen = IncomeStatementGenerator()
        # Future: Add more specialized generators
        # self.balance_sheet_gen = BalanceSheetGenerator()
        # self.cash_flow_gen = CashFlowGenerator()
        # self.ratio_analysis_gen = RatioAnalysisGenerator()

    async def generate_structure(
        self, request: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate Excel structure for finance domain"""

        # Determine finance type from context
        finance_type = self._determine_finance_type(context)

        structure = {"domain": "finance", "type": finance_type, "sheets": []}

        # Get time context
        periods = self._extract_periods(context)
        company_name = context.get("entities", {}).get("companies", ["기업"])[0]

        # Add appropriate sheets based on type
        if finance_type in ["comprehensive", "financial_statements"]:
            # Add income statement
            income_sheet = self.income_statement_gen.create_income_statement_sheet(
                company_name, periods
            )
            structure["sheets"].append(income_sheet.dict())

            # Add placeholders for other statements
            structure["sheets"].extend(
                [
                    {
                        "name": "재무상태표",
                        "columns": [
                            {"name": "계정과목", "data_type": "text", "width": 25},
                            {"name": periods[-1], "data_type": "currency", "width": 15},
                        ],
                    },
                    {
                        "name": "현금흐름표",
                        "columns": [
                            {"name": "구분", "data_type": "text", "width": 25},
                            {"name": "금액", "data_type": "currency", "width": 15},
                        ],
                    },
                ]
            )

        elif finance_type == "income_statement":
            income_sheet = self.income_statement_gen.create_income_statement_sheet(
                company_name, periods
            )
            structure["sheets"].append(income_sheet.dict())

        elif finance_type == "budget":
            structure["sheets"].append(self._create_budget_sheet(periods))

        else:
            # Default financial report
            structure["sheets"].append(self._create_default_finance_sheet())

        return structure

    async def generate_data(
        self, structure: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, pd.DataFrame]:
        """Generate data for each sheet"""

        data = {}
        company_name = context.get("entities", {}).get("companies", ["기업"])[0]

        for sheet_spec in structure.get("sheets", []):
            sheet_name = sheet_spec.get("name")

            if sheet_name == "손익계산서":
                # Generate income statement data
                periods = [
                    col["name"]
                    for col in sheet_spec["columns"]
                    if col["name"] not in ["계정과목", "증감액", "증감률(%)"]
                ]

                df = await self.income_statement_gen.generate_income_statement(
                    company_name, periods, context
                )
                data[sheet_name] = df

            elif sheet_name == "재무상태표":
                # Generate balance sheet data (placeholder)
                data[sheet_name] = self._generate_balance_sheet_data(
                    sheet_spec, context
                )

            elif sheet_name == "현금흐름표":
                # Generate cash flow data (placeholder)
                data[sheet_name] = self._generate_cash_flow_data(sheet_spec, context)

            else:
                # Generate generic financial data
                data[sheet_name] = self._generate_generic_finance_data(
                    sheet_spec, context
                )

        return data

    async def apply_formulas(self, worksheet, structure: Dict[str, Any]) -> None:
        """Apply finance-specific formulas"""

        # Formulas are already calculated in the data generation phase
        # This method can be used for additional Excel-specific formulas

    async def create_visualizations(self, worksheet, structure: Dict[str, Any]) -> None:
        """Create finance-specific charts"""

        # TODO: Implement chart creation
        # - Trend charts for multi-period data
        # - Composition charts for expense breakdown
        # - Waterfall charts for profit analysis

    def _determine_finance_type(self, context: Dict[str, Any]) -> str:
        """Determine specific type of financial document needed"""

        request_text = context.get("original_text", "").lower()

        if "재무제표" in request_text:
            return "financial_statements"
        elif "손익" in request_text:
            return "income_statement"
        elif "대차대조표" in request_text or "재무상태표" in request_text:
            return "balance_sheet"
        elif "현금흐름" in request_text:
            return "cash_flow"
        elif "예산" in request_text:
            return "budget"
        elif "재무분석" in request_text:
            return "financial_analysis"
        else:
            return "comprehensive"

    def _extract_periods(self, context: Dict[str, Any]) -> List[str]:
        """Extract period information from context"""

        time_context = context.get("time_context", {})
        specific_dates = time_context.get("specific_dates", [])

        periods = []

        # Check for years
        years = [d["value"] for d in specific_dates if d["type"] == "year"]
        if years:
            # Generate period labels
            if len(years) == 1:
                # Single year - add current and previous
                year = years[0]
                periods = [f"{year-1}년", f"{year}년"]
            else:
                # Multiple years
                periods = [f"{year}년" for year in sorted(years)]
        else:
            # Default to current and previous year
            current_year = datetime.now().year
            periods = [f"{current_year-1}년", f"{current_year}년"]

        return periods

    def _create_budget_sheet(self, periods: List[str]) -> Dict[str, Any]:
        """Create budget sheet structure"""

        return {
            "name": "예산계획",
            "columns": [
                {"name": "항목", "data_type": "text", "width": 25},
                {"name": "예산", "data_type": "currency", "width": 15},
                {"name": "실적", "data_type": "currency", "width": 15},
                {"name": "차이", "data_type": "currency", "width": 15},
                {"name": "달성률", "data_type": "percentage", "width": 12},
            ],
            "row_count": 20,
            "has_totals": True,
        }

    def _create_default_finance_sheet(self) -> Dict[str, Any]:
        """Create default finance sheet structure"""

        return {
            "name": "재무데이터",
            "columns": [
                {"name": "항목", "data_type": "text", "width": 25},
                {"name": "금액", "data_type": "currency", "width": 15},
                {"name": "비율", "data_type": "percentage", "width": 12},
                {"name": "비고", "data_type": "text", "width": 30},
            ],
            "row_count": 30,
        }

    def _generate_balance_sheet_data(
        self, sheet_spec: Dict[str, Any], context: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate balance sheet data (placeholder)"""

        # Basic balance sheet structure
        data = [
            {"계정과목": "자산", "금액": 50000000},
            {"계정과목": "  유동자산", "금액": 20000000},
            {"계정과목": "  비유동자산", "금액": 30000000},
            {"계정과목": "부채", "금액": 20000000},
            {"계정과목": "  유동부채", "금액": 10000000},
            {"계정과목": "  비유동부채", "금액": 10000000},
            {"계정과목": "자본", "금액": 30000000},
            {"계정과목": "  자본금", "금액": 10000000},
            {"계정과목": "  이익잉여금", "금액": 20000000},
        ]

        return pd.DataFrame(data)

    def _generate_cash_flow_data(
        self, sheet_spec: Dict[str, Any], context: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate cash flow data (placeholder)"""

        data = [
            {"구분": "영업활동 현금흐름", "금액": 15000000},
            {"구분": "  당기순이익", "금액": 10000000},
            {"구분": "  감가상각비", "금액": 5000000},
            {"구분": "투자활동 현금흐름", "금액": -8000000},
            {"구분": "  유형자산 취득", "금액": -8000000},
            {"구분": "재무활동 현금흐름", "금액": -3000000},
            {"구분": "  차입금 상환", "금액": -3000000},
            {"구분": "현금의 증가", "금액": 4000000},
        ]

        return pd.DataFrame(data)

    def _generate_generic_finance_data(
        self, sheet_spec: Dict[str, Any], context: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate generic financial data"""

        # Create sample data based on columns
        columns = [col["name"] for col in sheet_spec.get("columns", [])]
        row_count = sheet_spec.get("row_count", 10)

        data = []
        for i in range(row_count):
            row = {}
            for col in columns:
                if "항목" in col or "구분" in col:
                    row[col] = f"항목 {i+1}"
                elif "금액" in col or "액" in col:
                    row[col] = 1000000 * (i + 1)
                elif "비율" in col or "률" in col:
                    row[col] = 0.1 * (i + 1)
                else:
                    row[col] = f"데이터 {i+1}"
            data.append(row)

        return pd.DataFrame(data)
