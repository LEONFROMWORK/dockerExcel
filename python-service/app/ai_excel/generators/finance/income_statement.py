"""
Income statement generator for financial Excel files
Generates profit and loss statements with AI-driven data
"""

from typing import Dict, List, Any
import pandas as pd

from .base import BaseFinanceGenerator
from ...structure.excel_schema import SheetSchema, ColumnDefinition, DataType


class IncomeStatementGenerator(BaseFinanceGenerator):
    """Generates income statements with realistic financial data"""

    def __init__(self):
        super().__init__()
        self.statement_structure = self._define_statement_structure()

    def _define_statement_structure(self) -> List[Dict[str, Any]]:
        """Define standard income statement structure"""

        return [
            {"account": "매출액", "level": 1, "formula": None},
            {"account": "매출원가", "level": 2, "formula": None},
            {"account": "매출총이익", "level": 1, "formula": "매출액 - 매출원가"},
            {"account": "판매비", "level": 2, "formula": None},
            {"account": "관리비", "level": 2, "formula": None},
            {"account": "판매관리비 계", "level": 2, "formula": "판매비 + 관리비"},
            {
                "account": "영업이익",
                "level": 1,
                "formula": "매출총이익 - 판매관리비 계",
            },
            {"account": "영업외수익", "level": 2, "formula": None},
            {"account": "영업외비용", "level": 2, "formula": None},
            {
                "account": "법인세차감전순이익",
                "level": 1,
                "formula": "영업이익 + 영업외수익 - 영업외비용",
            },
            {"account": "법인세비용", "level": 2, "formula": None},
            {
                "account": "당기순이익",
                "level": 1,
                "formula": "법인세차감전순이익 - 법인세비용",
            },
        ]

    async def generate_income_statement(
        self, company_name: str, periods: List[str], context: Dict[str, Any]
    ) -> pd.DataFrame:
        """Generate complete income statement"""

        # Extract context information
        industry = context.get("industry", "general")
        size = context.get("company_size", "medium")
        context.get("growth_rate", 0.05)

        # Generate base data
        accounts = [item["account"] for item in self.statement_structure]
        base_amounts = self._generate_industry_specific_amounts(industry, size)

        # Generate period data
        data = self.generate_financial_data(accounts, periods, base_amounts)

        # Apply formulas
        data = self._apply_statement_formulas(data, periods)

        # Add analysis columns
        if len(periods) > 1:
            data = self._add_variance_analysis(data, periods)

        return data

    def _generate_industry_specific_amounts(
        self, industry: str, size: str
    ) -> Dict[str, float]:
        """Generate base amounts based on industry and company size"""

        # Base amounts by company size
        size_multipliers = {
            "small": 0.1,
            "medium": 1.0,
            "large": 10.0,
            "enterprise": 100.0,
        }

        multiplier = size_multipliers.get(size, 1.0)

        # Industry-specific patterns
        industry_patterns = {
            "manufacturing": {
                "매출액": 50000000,
                "매출원가": 35000000,  # 70% of revenue
                "판매비": 5000000,
                "관리비": 3000000,
                "영업외수익": 500000,
                "영업외비용": 1000000,
                "법인세비용": 1500000,
            },
            "retail": {
                "매출액": 30000000,
                "매출원가": 21000000,  # 70% of revenue
                "판매비": 3000000,
                "관리비": 2000000,
                "영업외수익": 200000,
                "영업외비용": 500000,
                "법인세비용": 800000,
            },
            "service": {
                "매출액": 20000000,
                "매출원가": 8000000,  # 40% of revenue
                "판매비": 3000000,
                "관리비": 4000000,
                "영업외수익": 300000,
                "영업외비용": 400000,
                "법인세비용": 1000000,
            },
            "general": {
                "매출액": 30000000,
                "매출원가": 18000000,  # 60% of revenue
                "판매비": 3000000,
                "관리비": 3000000,
                "영업외수익": 300000,
                "영업외비용": 600000,
                "법인세비용": 1200000,
            },
        }

        base_amounts = industry_patterns.get(industry, industry_patterns["general"])

        # Apply size multiplier
        return {k: v * multiplier for k, v in base_amounts.items()}

    def _apply_statement_formulas(
        self, data: pd.DataFrame, periods: List[str]
    ) -> pd.DataFrame:
        """Apply formulas to calculate derived values"""

        # Convert to dictionary for easier manipulation
        data_dict = data.set_index("계정과목").to_dict()

        # Apply formulas based on structure
        for item in self.statement_structure:
            if item["formula"]:
                account = item["account"]
                item["formula"]

                for period in periods:
                    if account == "매출총이익":
                        data_dict[period][account] = (
                            data_dict[period]["매출액"] - data_dict[period]["매출원가"]
                        )
                    elif account == "판매관리비 계":
                        data_dict[period][account] = (
                            data_dict[period]["판매비"] + data_dict[period]["관리비"]
                        )
                    elif account == "영업이익":
                        data_dict[period][account] = (
                            data_dict[period]["매출총이익"]
                            - data_dict[period]["판매관리비 계"]
                        )
                    elif account == "법인세차감전순이익":
                        data_dict[period][account] = (
                            data_dict[period]["영업이익"]
                            + data_dict[period]["영업외수익"]
                            - data_dict[period]["영업외비용"]
                        )
                    elif account == "당기순이익":
                        data_dict[period][account] = (
                            data_dict[period]["법인세차감전순이익"]
                            - data_dict[period]["법인세비용"]
                        )

        # Convert back to DataFrame
        result_df = pd.DataFrame.from_dict(data_dict)
        result_df.reset_index(inplace=True)
        result_df.rename(columns={"index": "계정과목"}, inplace=True)

        # Reorder based on original structure
        account_order = [item["account"] for item in self.statement_structure]
        result_df = result_df.set_index("계정과목").reindex(account_order).reset_index()

        return result_df

    def _add_variance_analysis(
        self, data: pd.DataFrame, periods: List[str]
    ) -> pd.DataFrame:
        """Add variance analysis columns"""

        if len(periods) >= 2:
            current_period = periods[-1]
            previous_period = periods[-2]

            # Calculate absolute change
            data["증감액"] = data[current_period] - data[previous_period]

            # Calculate percentage change
            data["증감률(%)"] = data.apply(
                lambda row: (
                    (
                        (row[current_period] - row[previous_period])
                        / abs(row[previous_period])
                        * 100
                    )
                    if row[previous_period] != 0
                    else 0
                ),
                axis=1,
            ).round(1)

        return data

    def create_income_statement_sheet(
        self, company_name: str, periods: List[str], include_charts: bool = True
    ) -> SheetSchema:
        """Create income statement sheet schema"""

        # Define columns
        columns = [ColumnDefinition(name="계정과목", data_type=DataType.TEXT, width=25)]

        # Add period columns
        for period in periods:
            columns.append(
                ColumnDefinition(name=period, data_type=DataType.CURRENCY, width=15)
            )

        # Add variance columns if multiple periods
        if len(periods) > 1:
            columns.extend(
                [
                    ColumnDefinition(
                        name="증감액", data_type=DataType.CURRENCY, width=15
                    ),
                    ColumnDefinition(
                        name="증감률(%)", data_type=DataType.PERCENTAGE, width=12
                    ),
                ]
            )

        # Create sheet schema
        sheet = SheetSchema(
            name="손익계산서",
            columns=columns,
            row_count=len(self.statement_structure),
            has_totals=False,
            freeze_panes="B2",
            description=f"{company_name} 손익계산서",
        )

        return sheet
