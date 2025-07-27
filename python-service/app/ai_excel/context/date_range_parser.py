"""
Date range parser - Extracted from ContextBuilder
Handles date parsing and range determination
"""

from typing import Dict, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import logging

logger = logging.getLogger(__name__)


class DateRangeParser:
    """Parses and determines date ranges from context"""
    
    def __init__(self, time_context: Dict[str, Any]):
        self.time_context = time_context
        self.now = datetime.now()
        self._parser_strategy = self._determine_parser_strategy()
    
    def parse(self) -> Dict[str, Any]:
        """Main parsing method - only public method"""
        return self._parser_strategy()
    
    def _determine_parser_strategy(self):
        """Determine which parsing strategy to use"""
        if self._has_specific_dates():
            return self._parse_specific_dates
        elif self._has_relative_dates():
            return self._parse_relative_dates
        elif self._has_duration():
            return self._parse_duration_based
        else:
            return self._get_default_range
    
    def _has_specific_dates(self) -> bool:
        """Check if context has specific dates"""
        return bool(self.time_context.get("specific_dates"))
    
    def _has_relative_dates(self) -> bool:
        """Check if context has relative dates"""
        return bool(self.time_context.get("relative_time"))
    
    def _has_duration(self) -> bool:
        """Check if context has duration"""
        return bool(self.time_context.get("duration"))
    
    def _parse_specific_dates(self) -> Dict[str, Any]:
        """Parse specific dates from context"""
        dates = self.time_context.get("specific_dates", [])
        years = [d["value"] for d in dates if d["type"] == "year"]
        months = [d["value"] for d in dates if d["type"] == "month"]
        quarters = [d["value"] for d in dates if d["type"] == "quarter"]
        
        if quarters:
            return self._parse_quarterly_dates(quarters[0], years[0] if years else self.now.year)
        elif years and months:
            return self._parse_monthly_dates(years[0], months[0])
        elif years:
            return self._parse_yearly_dates(years)
        else:
            return self._get_default_range()
    
    def _parse_relative_dates(self) -> Dict[str, Any]:
        """Parse relative dates from context"""
        relative = self.time_context.get("relative_time", {})
        
        if "year" in relative:
            return self._create_year_range(relative["year"])
        
        period = relative.get("period")
        if period == "current":
            return self._get_current_period_range()
        elif period == "previous":
            return self._get_previous_period_range()
        elif period == "next":
            return self._get_next_period_range()
        
        return self._get_default_range()
    
    def _parse_duration_based(self) -> Dict[str, Any]:
        """Parse duration-based date range"""
        duration = self.time_context.get("duration", {})
        value = duration.get("value", 1)
        unit = duration.get("unit", "months")
        
        start_date = date(self.now.year, self.now.month, 1)
        
        if unit == "months":
            end_date = start_date + relativedelta(months=value) - timedelta(days=1)
        elif unit == "days":
            end_date = start_date + timedelta(days=value)
        elif unit == "years":
            end_date = start_date + relativedelta(years=value) - timedelta(days=1)
        else:
            end_date = start_date + timedelta(days=30)
        
        return self._create_range_dict(start_date, end_date)
    
    def _get_default_range(self) -> Dict[str, Any]:
        """Get default date range (current month)"""
        start_date = date(self.now.year, self.now.month, 1)
        end_date = start_date + relativedelta(months=1) - timedelta(days=1)
        return self._create_range_dict(start_date, end_date)
    
    def _parse_quarterly_dates(self, quarter: int, year: int) -> Dict[str, Any]:
        """Parse quarterly date range"""
        quarter_starts = {1: 1, 2: 4, 3: 7, 4: 10}
        start_month = quarter_starts.get(quarter, 1)
        start_date = date(year, start_month, 1)
        end_date = start_date + relativedelta(months=3) - timedelta(days=1)
        return self._create_range_dict(start_date, end_date)
    
    def _parse_monthly_dates(self, year: int, month: int) -> Dict[str, Any]:
        """Parse monthly date range"""
        start_date = date(year, month, 1)
        end_date = start_date + relativedelta(months=1) - timedelta(days=1)
        return self._create_range_dict(start_date, end_date)
    
    def _parse_yearly_dates(self, years: list) -> Dict[str, Any]:
        """Parse yearly date range"""
        if len(years) == 1:
            year = years[0]
            start_date = date(year, 1, 1)
            end_date = date(year, 12, 31)
        else:
            # Multiple years - use range
            start_date = date(min(years), 1, 1)
            end_date = date(max(years), 12, 31)
        
        return self._create_range_dict(start_date, end_date)
    
    def _create_year_range(self, year: int) -> Dict[str, Any]:
        """Create range for entire year"""
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        return self._create_range_dict(start_date, end_date)
    
    def _get_current_period_range(self) -> Dict[str, Any]:
        """Get current period range based on context"""
        # Default to current month
        return self.get_default_range()
    
    def _get_previous_period_range(self) -> Dict[str, Any]:
        """Get previous period range"""
        current_start = date(self.now.year, self.now.month, 1)
        start_date = current_start - relativedelta(months=1)
        end_date = current_start - timedelta(days=1)
        return self._create_range_dict(start_date, end_date)
    
    def _get_next_period_range(self) -> Dict[str, Any]:
        """Get next period range"""
        current_start = date(self.now.year, self.now.month, 1)
        start_date = current_start + relativedelta(months=1)
        end_date = start_date + relativedelta(months=1) - timedelta(days=1)
        return self._create_range_dict(start_date, end_date)
    
    def _create_range_dict(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Create standardized range dictionary"""
        return {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "period_type": self._determine_period_type(start_date, end_date),
            "days": (end_date - start_date).days + 1
        }
    
    def _determine_period_type(self, start_date: date, end_date: date) -> str:
        """Determine the period type based on date range"""
        days = (end_date - start_date).days + 1
        
        if days <= 31:
            return "monthly"
        elif days <= 93:
            return "quarterly"
        elif days <= 366:
            return "annual"
        else:
            return "multi_year"