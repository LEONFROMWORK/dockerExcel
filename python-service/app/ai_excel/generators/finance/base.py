"""
Base finance generator module
Provides core functionality for financial Excel generation
"""

from typing import Dict, List, Optional
import pandas as pd

from ...core.base_generator import BaseExcelGenerator


class BaseFinanceGenerator(BaseExcelGenerator):
    """Base class for finance-related Excel generators"""

    def __init__(self):
        super().__init__()
        self.accounting_standards = ["K-GAAP", "IFRS"]
        self.fiscal_periods = ["annual", "quarterly", "monthly"]

    def generate_financial_data(
        self,
        accounts: List[str],
        periods: List[str],
        base_amounts: Optional[Dict[str, float]] = None,
    ) -> pd.DataFrame:
        """Generate financial data with realistic patterns"""

        if not base_amounts:
            base_amounts = self._generate_base_amounts(accounts)

        data = []
        for account in accounts:
            row = {"계정과목": account}
            base = base_amounts.get(account, 100000)

            for i, period in enumerate(periods):
                # Apply realistic variations
                variation = self._calculate_variation(account, i)
                amount = base * variation
                row[period] = round(amount, 0)

            data.append(row)

        return pd.DataFrame(data)

    def _generate_base_amounts(self, accounts: List[str]) -> Dict[str, float]:
        """Generate base amounts for accounts"""

        # Common account patterns
        patterns = {
            "매출": 10000000,
            "매출원가": 6000000,
            "판관비": 2000000,
            "영업이익": 2000000,
            "자산": 50000000,
            "부채": 20000000,
            "자본": 30000000,
        }

        amounts = {}
        for account in accounts:
            # Find matching pattern
            for pattern, amount in patterns.items():
                if pattern in account:
                    amounts[account] = amount
                    break
            else:
                # Default amount
                amounts[account] = 1000000

        return amounts

    def _calculate_variation(self, account: str, period_index: int) -> float:
        """Calculate realistic variation for account over time"""

        # Growth patterns for different account types
        if "매출" in account:
            # Revenue typically grows
            return 1.0 + (period_index * 0.05)
        elif "비용" in account or "원가" in account:
            # Costs may increase slightly
            return 1.0 + (period_index * 0.03)
        elif "자산" in account:
            # Assets grow moderately
            return 1.0 + (period_index * 0.04)
        else:
            # Default: slight variation
            return 1.0 + (period_index * 0.02)

    def calculate_financial_ratios(self, data: pd.DataFrame) -> Dict[str, float]:
        """Calculate common financial ratios"""

        ratios = {}

        # Extract key values
        revenue = self._get_account_value(data, "매출")
        net_income = self._get_account_value(data, "당기순이익")
        assets = self._get_account_value(data, "자산총계")
        liabilities = self._get_account_value(data, "부채총계")
        equity = self._get_account_value(data, "자본총계")

        # Calculate ratios
        if revenue > 0:
            ratios["순이익률"] = (net_income / revenue) * 100

        if assets > 0:
            ratios["ROA"] = (net_income / assets) * 100
            ratios["부채비율"] = (liabilities / assets) * 100

        if equity > 0:
            ratios["ROE"] = (net_income / equity) * 100

        return ratios

    def _get_account_value(self, data: pd.DataFrame, account_name: str) -> float:
        """Get value for specific account"""

        matching_rows = data[data.iloc[:, 0].str.contains(account_name, na=False)]
        if not matching_rows.empty:
            # Return the most recent period value
            return float(matching_rows.iloc[0, -1])
        return 0.0

    def format_currency(self, value: float, currency: str = "KRW") -> str:
        """Format value as currency"""

        if currency == "KRW":
            return f"{value:,.0f}원"
        elif currency == "USD":
            return f"${value:,.2f}"
        else:
            return f"{value:,.2f}"

    def apply_accounting_rules(
        self, data: pd.DataFrame, standard: str = "K-GAAP"
    ) -> pd.DataFrame:
        """Apply accounting standard rules to data"""

        # This is a placeholder for actual accounting rules
        # In production, this would implement specific rules for each standard

        if standard == "K-GAAP":
            # Apply K-GAAP specific rules
            pass
        elif standard == "IFRS":
            # Apply IFRS specific rules
            pass

        return data
